"""REST providers and a file-based handoff to the current Codex conversation."""

import base64
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field

from cad_agent.domain.inputs import VisualInput


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


def post_json(url, headers, payload, timeout):
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except HTTPError as exc:
        raise ProviderError(
            f"Provider HTTP {exc.code}; check credentials, model access, limits and configuration."
        ) from None
    except (URLError, TimeoutError, OSError) as exc:
        raise ProviderError(f"Provider connection failed ({type(exc).__name__}).") from None
    except (ValueError, UnicodeError):
        raise ProviderError("Provider returned invalid JSON.") from None


class APIProvider:
    def __init__(self, name, config, transport=post_json):
        if name not in ("openai", "anthropic", "openrouter"):
            raise ValueError(f"Unknown API provider: {name}")
        self.name, self.config, self.transport = name, config, transport

    def generate(self, system, prompt, *, images: list[VisualInput] | None = None):
        try:
            return GeneratedCode.model_validate_json(self.complete(system, prompt, images=images))
        except (ValueError, TypeError):
            raise ProviderError(
                "Expected complete JSON with summary and code strings; response rejected."
            ) from None

    def complete(self, system, prompt, *, images: list[VisualInput] | None = None) -> str:
        """Common protocol boundary for script generation and conversational decisions."""
        config = self.config
        images = images or []
        if images and not config.supports_images:
            raise ProviderError(
                f"Visual attachments require a vision-capable model and providers.{self.name}.supports_images=true."
            )
        if len(images) > 16:
            raise ProviderError("At most 16 visual inputs per generation request.")
        if not config.model.strip():
            raise ProviderError(f"Set providers.{self.name}.model in providers.toml.")
        key = os.environ.get(config.api_key_env, "")
        if not key:
            raise ProviderError(f"Set environment variable {config.api_key_env or 'for the API key'}.")
        encoded = [(item, base64.b64encode(item.path.read_bytes()).decode("ascii")) for item in images]
        if self.name == "openai":
            url = "https://api.openai.com/v1/responses"
            headers = {"Authorization": f"Bearer {key}"}
            payload = dict(
                model=config.model,
                instructions=system,
                input=prompt,
                max_output_tokens=config.max_output_tokens,
                store=False,
            )
            if encoded:
                content = [{"type": "input_text", "text": prompt}]
                for item, data in encoded:
                    content.extend(
                        [
                            {"type": "input_text", "text": item.label},
                            {"type": "input_image", "image_url": f"data:{item.media_type};base64,{data}"},
                        ]
                    )
                payload["input"] = [{"role": "user", "content": content}]
        elif self.name == "anthropic":
            url = "https://api.anthropic.com/v1/messages"
            headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
            payload = dict(
                model=config.model,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=config.max_output_tokens,
            )
            if encoded:
                content = [{"type": "text", "text": prompt}]
                for item, data in encoded:
                    content.extend(
                        [
                            {"type": "text", "text": item.label},
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": item.media_type,
                                    "data": data,
                                },
                            },
                        ]
                    )
                payload["messages"][0]["content"] = content
        else:
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {"Authorization": f"Bearer {key}"}
            payload = dict(
                model=config.model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                max_tokens=config.max_output_tokens,
            )
            if encoded:
                content = [{"type": "text", "text": prompt}]
                for item, data in encoded:
                    content.extend(
                        [
                            {"type": "text", "text": item.label},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{item.media_type};base64,{data}"},
                            },
                        ]
                    )
                payload["messages"][1]["content"] = content
        data = self.transport(url, headers, payload, config.timeout_seconds)
        try:
            if self.name == "openai":
                if data.get("status") != "completed":
                    raise ProviderError("OpenAI generation did not complete; script rejected.")
                text = "".join(
                    b["text"]
                    for item in data.get("output", [])
                    if item.get("type") == "message"
                    for b in item.get("content", [])
                    if b.get("type") == "output_text"
                )
            elif self.name == "anthropic":
                if data.get("stop_reason") != "end_turn":
                    raise ProviderError("Claude generation did not complete normally; script rejected.")
                text = "".join(b["text"] for b in data["content"] if b.get("type") == "text")
            else:
                choice = data["choices"][0]
                if choice.get("finish_reason") != "stop":
                    raise ProviderError("OpenRouter generation did not complete normally; script rejected.")
                text = choice["message"]["content"]
            if not isinstance(text, str) or not text.strip():
                raise ProviderError("Provider returned an empty response.")
            return text
        except (ValueError, KeyError, IndexError, TypeError):
            raise ProviderError(
                "Expected complete JSON with summary and code strings; response rejected."
            ) from None


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
