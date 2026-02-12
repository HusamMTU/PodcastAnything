"""Unit tests for Bedrock model routing."""
from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from ml_publication.llm import LLMError, call_bedrock


class CallBedrockRoutingTests(unittest.TestCase):
    @patch("ml_publication.llm.call_bedrock_anthropic", return_value="anthropic-text")
    def test_routes_anthropic_ids(self, mock_call: Mock) -> None:
        model_ids = [
            "anthropic.claude-3-haiku-20240307-v1:0",
            "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
        ]

        for model_id in model_ids:
            with self.subTest(model_id=model_id):
                result = call_bedrock(model_id, "prompt")
                self.assertEqual("anthropic-text", result)
                mock_call.assert_called_with(
                    model_id,
                    "prompt",
                    max_tokens=1400,
                    temperature=0.5,
                )

    @patch("ml_publication.llm.call_bedrock_nova", return_value="nova-text")
    def test_routes_nova_ids(self, mock_call: Mock) -> None:
        model_ids = [
            "amazon.nova-lite-v1:0",
            "us.amazon.nova-pro-v1:0",
        ]

        for model_id in model_ids:
            with self.subTest(model_id=model_id):
                result = call_bedrock(model_id, "prompt")
                self.assertEqual("nova-text", result)
                mock_call.assert_called_with(
                    model_id,
                    "prompt",
                    max_tokens=1400,
                    temperature=0.5,
                )

    def test_raises_for_unsupported_model_ids(self) -> None:
        with self.assertRaisesRegex(LLMError, "Unsupported Bedrock model_id"):
            call_bedrock("meta.llama3-8b-instruct-v1:0", "prompt")


if __name__ == "__main__":
    unittest.main()
