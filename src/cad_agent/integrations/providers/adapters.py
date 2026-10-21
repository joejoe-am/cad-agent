"""Official provider SDKs and a file-based handoff to the current Codex conversation."""

import base64
import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from cad_agent.domain.inputs import VisualInput

API_PROVIDERS = ("openai", "anthropic", "openrouter")
MAX_IMAGES = 16
PACKAGES = {"openai": "openai", "anthropic": "anthropic", "openrouter": "openrouter"}


class ProviderError(RuntimeError):
    pass


class GeneratedCode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(min_length=1)
    code: str = Field(min_length=1)


class ProviderConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str = ""
    api_key_env: str = ""
    max_output_tokens: int = Field(default=12000, gt=0)
    timeout_seconds: float = Field(default=120, gt=0)
    mode: str | None = None
    supports_images: bool = False


def sdk(name: str):
    """Import a provider's official SDK, reporting the install command rather than a traceback."""
    package = PACKAGES[name]
    try:
        return __import__(package)
    except ImportError:
        raise ProviderError(
            f"The {name} provider needs its official SDK. "
            'Install the API extra: python -m pip install -e ".[api]"'
        ) from None


def build_client(name: str, config: ProviderConfig, key: str):
    """Construct an official client with no automatic retries and a finite timeout.

    Generated code is reviewed before execution, so a silently retried request would
    hide a refused or truncated generation rather than surface it for repair.
    """
    module = sdk(name)
    if name == "anthropic":
        return module.Anthropic(api_key=key, timeout=config.timeout_seconds, max_retries=0)
    if name == "openai":
        return module.OpenAI(api_key=key, timeout=config.timeout_seconds, max_retries=0)
    from openrouter.utils.retries import BackoffStrategy, RetryConfig

    # The generated OpenRouter client takes milliseconds and its own retry strategy.
    return module.OpenRouter(
        api_key=key,
        timeout_ms=int(config.timeout_seconds * 1000),
        retry_config=RetryConfig("none", BackoffStrategy(1, 1, 1.0, 1), False),
    )


def error_groups(name: str):
    """Exception groups for one SDK, ordered connection -> malformed -> HTTP status.

    OpenRouter's generated SDK has its own hierarchy, so the groups differ by vendor.
    """
    module = sdk(name)
    if name == "openrouter":
        import httpx

        return (
            (module.errors.NoResponseError, httpx.HTTPError),
            (module.errors.ResponseValidationError,),
            (module.errors.OpenRouterError,),
        )
    return ((module.APIConnectionError,), (), (module.APIStatusError, module.APIError))


def http_status(error: Exception):
    """Read a status code from either SDK's error shape; None when the failure is not HTTP."""
    return getattr(error, "status_code", None) or getattr(
        getattr(error, "raw_response", None), "status_code", None
    )


class APIProvider:
    def __init__(self, name, config, client_factory=build_client):
        if name not in API_PROVIDERS:
            raise ValueError(f"Unknown API provider: {name}")
        self.name, self.config, self.client_factory = name, config, client_factory

    def generate(self, system, prompt, *, images: list[VisualInput] | None = None):
        try:
            return GeneratedCode.model_validate_json(self.complete(system, prompt, images=images))
        except ProviderError:
            raise
        except (ValueError, TypeError):
            raise ProviderError(
                "Expected complete JSON with summary and code strings; response rejected."
            ) from None

    def complete(self, system, prompt, *, images: list[VisualInput] | None = None) -> str:
        """Common protocol boundary for script generation and conversational decisions."""
        encoded = self.encoded_images(images or [])
        if not self.config.model.strip():
            raise ProviderError(f"Set providers.{self.name}.model in providers.toml.")
        key = os.environ.get(self.config.api_key_env, "")
        if not key:
            raise ProviderError(f"Set environment variable {self.config.api_key_env or 'for the API key'}.")
        rejected = "Expected complete JSON with summary and code strings; response rejected."
        connection_errors, malformed_errors, status_errors = error_groups(self.name)
        client = self.client_factory(self.name, self.config, key)
        try:
            if self.name == "openai":
                text = self.from_openai(client, system, prompt, encoded)
            elif self.name == "anthropic":
                text = self.from_anthropic(client, system, prompt, encoded)
            else:
                text = self.from_openrouter(client, system, prompt, encoded)
        except ProviderError:
            raise
        except connection_errors as exc:
            raise ProviderError(f"Provider connection failed ({type(exc).__name__}).") from None
        except malformed_errors:
            raise ProviderError(rejected) from None
        except status_errors as exc:
            code = http_status(exc)
            raise ProviderError(
                f"Provider HTTP {code}; check credentials, model access, limits and configuration."
                if code
                else rejected
            ) from None
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            raise ProviderError(rejected) from None
        if not isinstance(text, str) or not text.strip():
            raise ProviderError("Provider returned an empty response.")
        return text

    def encoded_images(self, images: list[VisualInput]) -> list[tuple[VisualInput, str]]:
        if images and not self.config.supports_images:
            raise ProviderError(
                f"Visual attachments require a vision-capable model and providers.{self.name}.supports_images=true."
            )
        if len(images) > MAX_IMAGES:
            raise ProviderError(f"At most {MAX_IMAGES} visual inputs per generation request.")
        return [(item, base64.b64encode(item.path.read_bytes()).decode("ascii")) for item in images]

    def from_openai(self, client, system, prompt, encoded) -> str:
        payload = prompt
        if encoded:
            content = [{"type": "input_text", "text": prompt}]
            for item, data in encoded:
                content.append({"type": "input_text", "text": item.label})
                content.append({"type": "input_image", "image_url": f"data:{item.media_type};base64,{data}"})
            payload = [{"role": "user", "content": content}]
        response = client.responses.create(
            model=self.config.model,
            instructions=system,
            input=payload,
            max_output_tokens=self.config.max_output_tokens,
            store=False,
        )
        if response.status != "completed":
            raise ProviderError("OpenAI generation did not complete; script rejected.")
        return response.output_text

    def from_anthropic(self, client, system, prompt, encoded) -> str:
        content = prompt
        if encoded:
            content = [{"type": "text", "text": prompt}]
            for item, data in encoded:
                content.append({"type": "text", "text": item.label})
                content.append(
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": item.media_type, "data": data},
                    }
                )
        message = client.messages.create(
            model=self.config.model,
            system=system,
            messages=[{"role": "user", "content": content}],
            max_tokens=self.config.max_output_tokens,
        )
        if message.stop_reason == "refusal":
            raise ProviderError("Claude declined this request; script rejected.")
        if message.stop_reason != "end_turn":
            raise ProviderError("Claude generation did not complete normally; script rejected.")
        return "".join(block.text for block in message.content if block.type == "text")

    def from_openrouter(self, client, system, prompt, encoded) -> str:
        content = prompt
        if encoded:
            content = [{"type": "text", "text": prompt}]
            for item, data in encoded:
                content.append({"type": "text", "text": item.label})
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{item.media_type};base64,{data}"},
                    }
                )
        result = client.chat.send(
            model=self.config.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
            max_tokens=self.config.max_output_tokens,
        )
        choice = result.choices[0]
        if choice.finish_reason != "stop":
            raise ProviderError("OpenRouter generation did not complete normally; script rejected.")
        return choice.message.content


class CodexWorkspaceProvider:
    """No API call: the existing Codex conversation consumes this task file."""

    def prepare(self, attempt: Path, system: str, prompt: str):
        path = attempt / "CODEX_TASK.md"
        path.write_text(
            "# Codex workspace task\n\n"
            + system
            + "\n\n"
            + prompt
            + "\n\nWrite response.json here using the required JSON format. "
            "Then use `cad-agent accept <job-directory>` to stage the script. "
            "A successful exit does not verify the geometry.\n",
            encoding="utf-8",
        )
        return path
