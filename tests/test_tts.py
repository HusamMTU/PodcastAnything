"""Unit tests for TTS helper behavior across providers."""

from __future__ import annotations

import unittest
from io import BytesIO
from unittest.mock import Mock, patch

import requests

from podcast_anything.tts import TTSError, synthesize_speech


class SynthesizeSpeechTests(unittest.TestCase):
    @patch("podcast_anything.tts.boto3.client")
    def test_short_text_makes_single_request(self, mock_boto_client: Mock) -> None:
        mock_polly = Mock()
        mock_polly.synthesize_speech.return_value = {"AudioStream": BytesIO(b"audio-1")}
        mock_boto_client.return_value = mock_polly

        audio = synthesize_speech("short text", voice_id="Joanna", max_text_chars=500)

        self.assertEqual(b"audio-1", audio)
        mock_polly.synthesize_speech.assert_called_once()
        self.assertEqual("text", mock_polly.synthesize_speech.call_args.kwargs["TextType"])

    @patch("podcast_anything.tts.boto3.client")
    def test_long_text_is_split_into_multiple_requests(self, mock_boto_client: Mock) -> None:
        mock_polly = Mock()
        mock_polly.synthesize_speech.side_effect = [
            {"AudioStream": BytesIO(b"part-1")},
            {"AudioStream": BytesIO(b"part-2")},
            {"AudioStream": BytesIO(b"part-3")},
        ]
        mock_boto_client.return_value = mock_polly
        text = "Sentence. " * 500

        audio = synthesize_speech(text, voice_id="Joanna", max_text_chars=2000)

        self.assertEqual(b"part-1part-2part-3", audio)
        self.assertEqual(3, mock_polly.synthesize_speech.call_count)
        for call in mock_polly.synthesize_speech.call_args_list:
            self.assertLessEqual(len(call.kwargs["Text"]), 2000)
            self.assertEqual("text", call.kwargs["TextType"])

    @patch("podcast_anything.tts.boto3.client")
    def test_raises_when_audio_stream_missing(self, mock_boto_client: Mock) -> None:
        mock_polly = Mock()
        mock_polly.synthesize_speech.return_value = {}
        mock_boto_client.return_value = mock_polly

        with self.assertRaisesRegex(TTSError, "AudioStream"):
            synthesize_speech("short text", voice_id="Joanna", max_text_chars=500)

    def test_raises_when_text_is_empty(self) -> None:
        with self.assertRaisesRegex(TTSError, "empty"):
            synthesize_speech("   ", voice_id="Joanna")

    @patch("podcast_anything.tts.boto3.client")
    def test_ssml_mode_wraps_speak_and_sets_text_type(self, mock_boto_client: Mock) -> None:
        mock_polly = Mock()
        mock_polly.synthesize_speech.return_value = {"AudioStream": BytesIO(b"audio-ssml")}
        mock_boto_client.return_value = mock_polly

        audio = synthesize_speech(
            "Line one.\n\nLine two.",
            voice_id="Joanna",
            text_type="ssml",
            max_text_chars=500,
        )

        self.assertEqual(b"audio-ssml", audio)
        call_kwargs = mock_polly.synthesize_speech.call_args.kwargs
        self.assertEqual("ssml", call_kwargs["TextType"])
        self.assertIn("<speak>", call_kwargs["Text"])
        self.assertIn("<break time=", call_kwargs["Text"])

    def test_rejects_invalid_text_type(self) -> None:
        with self.assertRaisesRegex(TTSError, "text_type must be either"):
            synthesize_speech("hello", voice_id="Joanna", text_type="invalid")

    def test_rejects_unknown_provider(self) -> None:
        with self.assertRaisesRegex(TTSError, "Unsupported TTS provider"):
            synthesize_speech("hello", voice_id="Joanna", provider="unknown")

    @patch("podcast_anything.tts.requests.post")
    def test_elevenlabs_mode_calls_http_api(self, mock_post: Mock) -> None:
        response = Mock(status_code=200, content=b"chunk", text="")
        mock_post.return_value = response
        text = "Sentence one. " * 20

        audio = synthesize_speech(
            text,
            voice_id="voice-id",
            provider="elevenlabs",
            max_text_chars=100,
            text_type="text",
            elevenlabs_api_key="test-key",
            elevenlabs_model_id="eleven_multilingual_v2",
        )

        self.assertGreater(mock_post.call_count, 1)
        self.assertEqual(b"chunk" * mock_post.call_count, audio)
        call_kwargs = mock_post.call_args.kwargs
        self.assertEqual("mp3_44100_128", call_kwargs["params"]["output_format"])
        self.assertEqual("test-key", call_kwargs["headers"]["xi-api-key"])
        self.assertEqual("eleven_multilingual_v2", call_kwargs["json"]["model_id"])

    @patch("podcast_anything.tts.requests.post")
    def test_elevenlabs_wraps_request_exceptions(self, mock_post: Mock) -> None:
        mock_post.side_effect = requests.RequestException("network issue")

        with self.assertRaisesRegex(TTSError, "network issue"):
            synthesize_speech(
                "hello world",
                voice_id="voice-id",
                provider="elevenlabs",
                elevenlabs_api_key="test-key",
            )

    def test_elevenlabs_requires_api_key(self) -> None:
        with self.assertRaisesRegex(TTSError, "API key is required"):
            synthesize_speech(
                "hello",
                voice_id="voice-id",
                provider="elevenlabs",
            )

    def test_elevenlabs_rejects_ssml_mode(self) -> None:
        with self.assertRaisesRegex(TTSError, "supports only text input"):
            synthesize_speech(
                "hello",
                voice_id="voice-id",
                provider="elevenlabs",
                text_type="ssml",
                elevenlabs_api_key="test-key",
            )


if __name__ == "__main__":
    unittest.main()
