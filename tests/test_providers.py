import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import anthropic
import httpx
import httpx2
import openai
import openrouter
from anthropic.types import Message
from openai.types.responses import Response
from openrouter.components.chatresult import ChatResult

from cad_agent.integrations.providers.adapters import (
    APIProvider,
    ProviderConfig,
    ProviderError,
    build_client,
)

TEXT = json.dumps(dict(summary="demo", code="print(42)"))


def anthropic_message(text=TEXT, stop_reason="end_turn"):
    return Message.model_validate(
        dict(
            id="msg_1",
            type="message",
            role="assistant",
            model="fixture",
            stop_reason=stop_reason,
            content=[dict(type="text", text=text)],
            usage=dict(input_tokens=1, output_tokens=1),
        )
    )


def openai_response(text=TEXT, status="completed"):
    output = (
        [
            dict(
                type="message",
                id="out_1",
                role="assistant",
                status="completed",
                content=[dict(type="output_text", text=text, annotations=[])],
            )
        ]
        if text is not None
        else []
    )
    return Response.model_validate(
        dict(
            id="resp_1",
            object="response",
            created_at=0,
            model="fixture",
            status=status,
            output=output,
            parallel_tool_calls=False,
            tool_choice="auto",
            tools=[],
        )
    )


def openrouter_completion(text=TEXT, finish_reason="stop"):
    return ChatResult.model_validate(
        dict(
            id="chat_1",
            object="chat.completion",
            created=0,
            model="fixture",
            system_fingerprint=None,
            choices=[
                dict(
                    index=0,
                    finish_reason=finish_reason,
                    message=dict(role="assistant", content=text),
                )
            ],
        )
    )


class Recorder:
    """Stands in for an official SDK client, recording the request it is given."""

    def __init__(self, result):
        self.result, self.calls = result, []

    def send(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result

    @property
    def responses(self):
        return SimpleNamespace(create=self.send)

    @property
    def messages(self):
        return SimpleNamespace(create=self.send)

    @property
    def chat(self):
        return SimpleNamespace(send=self.send)


def provider(name, result, **config):
    client = Recorder(result)
    settings = dict(model="fixture", api_key_env="TEST_KEY")
    settings.update(config)
    return APIProvider(name, ProviderConfig(**settings), lambda *args: client), client


class ProviderTests(unittest.TestCase):
    def test_provider_contracts(self):
        results = {
            "openai": openai_response(),
            "anthropic": anthropic_message(),
            "openrouter": openrouter_completion(),
        }
        for name, result in results.items():
            with self.subTest(name=name), patch.dict(os.environ, {"TEST_KEY": "fake"}):
                api, client = provider(name, result)
                self.assertEqual(api.generate("system", "task").code, "print(42)")
                request = client.calls[0]
                self.assertEqual(request["model"], "fixture")
                if name == "openai":
                    self.assertFalse(request["store"])
                    self.assertEqual(request["instructions"], "system")
                    self.assertEqual(request["input"], "task")
                elif name == "anthropic":
                    self.assertEqual(request["system"], "system")
                    self.assertEqual(request["messages"][0]["content"], "task")
                else:
                    self.assertEqual(request["messages"][0]["role"], "system")

    def test_truncated_or_refused_rejected(self):
        cases = [
            ("openai", openai_response(status="incomplete")),
            ("openai", openai_response(text=None)),
            ("anthropic", anthropic_message(stop_reason="max_tokens")),
            ("anthropic", anthropic_message(stop_reason="refusal")),
            ("openrouter", openrouter_completion(finish_reason="length")),
        ]
        for name, result in cases:
            with (
                self.subTest(name=name),
                patch.dict(os.environ, {"TEST_KEY": "fake"}),
                self.assertRaises(ProviderError),
            ):
                provider(name, result)[0].generate("", "")

    def test_sdk_errors_become_provider_errors_without_leaking_bodies(self):
        request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
        cases = [
            (
                anthropic.APIStatusError(
                    "secret body", response=httpx2.Response(429, request=request), body=None
                ),
                "Provider HTTP 429",
            ),
            (anthropic.APIConnectionError(request=request), "Provider connection failed"),
            (anthropic.APITimeoutError(request=request), "Provider connection failed"),
        ]
        for error, expected in cases:
            with self.subTest(error=type(error).__name__), patch.dict(os.environ, {"TEST_KEY": "fake"}):
                api, _ = provider("anthropic", error)
                with self.assertRaises(ProviderError) as caught:
                    api.generate("", "")
                self.assertIn(expected, str(caught.exception))
                self.assertNotIn("secret body", str(caught.exception))

    def test_openrouter_error_hierarchy_is_normalised(self):
        """The generated OpenRouter SDK does not share the openai/anthropic exception shapes."""
        response = httpx.Response(
            503, request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
        )
        cases = [
            (
                openrouter.errors.OpenRouterDefaultError("secret body", response, None),
                "Provider HTTP 503",
            ),
            (openrouter.errors.NoResponseError("no response"), "Provider connection failed"),
        ]
        for error, expected in cases:
            with self.subTest(error=type(error).__name__), patch.dict(os.environ, {"TEST_KEY": "fake"}):
                api, _ = provider("openrouter", error)
                with self.assertRaises(ProviderError) as caught:
                    api.generate("", "")
                self.assertIn(expected, str(caught.exception))
                self.assertNotIn("secret body", str(caught.exception))

    def test_missing_key_no_network(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(ProviderError):
            APIProvider(
                "openai",
                ProviderConfig(model="test", api_key_env="TEST_KEY"),
                lambda *args: self.fail("Unexpected client construction"),
            ).generate("", "")

    def test_invalid_json_rejected(self):
        with patch.dict(os.environ, {"TEST_KEY": "fake"}), self.assertRaises(ProviderError):
            provider("anthropic", anthropic_message(text="not JSON"))[0].generate("", "")

    def test_clients_use_finite_timeout_and_no_retries(self):
        config = ProviderConfig(model="fixture", api_key_env="TEST_KEY", timeout_seconds=30)
        claude = build_client("anthropic", config, "fake")
        self.assertIsInstance(claude, anthropic.Anthropic)
        self.assertEqual(claude.max_retries, 0)
        self.assertEqual(claude.timeout, 30)
        chat = build_client("openai", config, "fake")
        self.assertIsInstance(chat, openai.OpenAI)
        self.assertEqual(chat.max_retries, 0)
        self.assertEqual(chat.timeout, 30)
        self.assertIn("api.openai.com", str(chat.base_url))
        router = build_client("openrouter", config, "fake")
        self.assertIsInstance(router, openrouter.OpenRouter)
        self.assertEqual(router.sdk_configuration.retry_config.strategy, "none")
        self.assertEqual(router.sdk_configuration.timeout_ms, 30_000)

    def test_missing_sdk_reports_install_command(self):
        with (
            patch.dict("sys.modules", {"anthropic": None}),
            self.assertRaisesRegex(ProviderError, r"\[api\]"),
        ):
            build_client("anthropic", ProviderConfig(), "fake")


if __name__ == "__main__":
    unittest.main()
