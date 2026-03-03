"""Unit tests for runtime settings loading."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from podcast_anything.config import ConfigError, load_settings


class LoadSettingsTests(unittest.TestCase):
    def test_defaults_to_polly_provider(self) -> None:
        with patch.dict(
            os.environ,
            {
                "MP_BUCKET": "bucket-name",
                "BEDROCK_MODEL_ID": "us.amazon.nova-lite-v1:0",
            },
            clear=True,
        ):
            settings = load_settings()

        self.assertEqual("polly", settings.tts_provider)
        self.assertEqual("Joanna", settings.polly_voice_id)
        self.assertEqual("Joanna", settings.polly_duo_voice_id)
        self.assertIsNone(settings.elevenlabs_api_key)

    def test_rejects_unknown_tts_provider(self) -> None:
        with patch.dict(
            os.environ,
            {
                "MP_BUCKET": "bucket-name",
                "BEDROCK_MODEL_ID": "us.amazon.nova-lite-v1:0",
                "TTS_PROVIDER": "invalid-provider",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(ConfigError, "TTS_PROVIDER"):
                load_settings()

    def test_requires_elevenlabs_api_key_when_provider_selected(self) -> None:
        with patch.dict(
            os.environ,
            {
                "MP_BUCKET": "bucket-name",
                "BEDROCK_MODEL_ID": "us.amazon.nova-lite-v1:0",
                "TTS_PROVIDER": "elevenlabs",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(ConfigError, "ELEVENLABS_API_KEY"):
                load_settings()

    def test_loads_elevenlabs_settings(self) -> None:
        with patch.dict(
            os.environ,
            {
                "MP_BUCKET": "bucket-name",
                "BEDROCK_MODEL_ID": "us.amazon.nova-lite-v1:0",
                "TTS_PROVIDER": "elevenlabs",
                "ELEVENLABS_API_KEY": "test-key",
                "ELEVENLABS_VOICE_ID": "voice-id",
                "ELEVENLABS_DUO_VOICE_ID": "voice-id-b",
                "ELEVENLABS_MODEL_ID": "eleven_multilingual_v2",
                "ELEVENLABS_OUTPUT_FORMAT": "mp3_44100_128",
            },
            clear=True,
        ):
            settings = load_settings()

        self.assertEqual("elevenlabs", settings.tts_provider)
        self.assertEqual("test-key", settings.elevenlabs_api_key)
        self.assertEqual("voice-id", settings.elevenlabs_voice_id)
        self.assertEqual("voice-id-b", settings.elevenlabs_duo_voice_id)
        self.assertEqual("eleven_multilingual_v2", settings.elevenlabs_model_id)
        self.assertEqual("mp3_44100_128", settings.elevenlabs_output_format)


if __name__ == "__main__":
    unittest.main()
