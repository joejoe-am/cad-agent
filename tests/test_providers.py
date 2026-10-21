import json
import os
import unittest
from unittest.mock import patch

from cad_agent.integrations.providers.adapters import APIProvider, ProviderConfig, ProviderError


class ProviderTests(unittest.TestCase):
    def test_provider_contracts(self):
        text = json.dumps(dict(summary="demo", code="print(42)"))
        cases = {
            "openai": {
                "status": "completed",
                "output": [{"type": "message", "content": [{"type": "output_text", "text": text}]}],
            },
            "anthropic": {"stop_reason": "end_turn", "content": [{"type": "text", "text": text}]},
            "openrouter": {"choices": [{"finish_reason": "stop", "message": {"content": text}}]},
        }
        endpoints = {
            "openai": "https://api.openai.com/v1/responses",
            "anthropic": "https://api.anthropic.com/v1/messages",
            "openrouter": "https://openrouter.ai/api/v1/chat/completions",
        }
        for name, data in cases.items():
            calls = []

            def transport(*args):
                calls.append(args)
                return data

            with self.subTest(name=name), patch.dict(os.environ, {"TEST_KEY": "fake"}):
                result = APIProvider(
                    name, ProviderConfig(model="test", api_key_env="TEST_KEY"), transport
                ).generate("system", "task")
                self.assertEqual(result.code, "print(42)")
                self.assertEqual(calls[0][0], endpoints[name])
                payload = calls[0][2]
                if name == "openai":
                    self.assertFalse(payload["store"])
                    self.assertEqual(payload["input"], "task")
                elif name == "anthropic":
                    self.assertEqual(payload["system"], "system")
                    self.assertEqual(calls[0][1]["anthropic-version"], "2023-06-01")
                else:
                    self.assertEqual(payload["messages"][0]["role"], "system")

    def test_truncated_or_refused_rejected(self):
        cases = [
            ("openai", {"status": "incomplete"}),
            ("anthropic", {"stop_reason": "max_tokens"}),
            ("openrouter", {"choices": [{"finish_reason": "length"}]}),
            ("openai", {"status": "completed", "output": []}),
        ]
        for name, data in cases:
            with (
                self.subTest(name=name),
                patch.dict(os.environ, {"TEST_KEY": "fake"}),
                self.assertRaises(ProviderError),
            ):
                APIProvider(
                    name, ProviderConfig(model="test", api_key_env="TEST_KEY"), lambda *args: data
                ).generate("", "")

    def test_missing_key_no_network(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(ProviderError):
            APIProvider(
                "openai",
                ProviderConfig(model="test", api_key_env="TEST_KEY"),
                lambda *args: self.fail("Unexpected network"),
            ).generate("", "")

    def test_invalid_json_rejected(self):
        with patch.dict(os.environ, {"TEST_KEY": "fake"}), self.assertRaises(ProviderError):
            APIProvider(
                "anthropic",
                ProviderConfig(model="test", api_key_env="TEST_KEY"),
                lambda *args: {"stop_reason": "end_turn", "content": [{"type": "text", "text": "not JSON"}]},
            ).generate("", "")
