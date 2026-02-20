"""Unit tests for Polly TTS helper chunking behavior."""
from __future__ import annotations

from io import BytesIO
import unittest
from unittest.mock import Mock, patch

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


if __name__ == "__main__":
    unittest.main()
