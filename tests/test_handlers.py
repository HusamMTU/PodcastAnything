"""Unit tests for Lambda handlers."""

from __future__ import annotations

import base64
import unittest
from unittest.mock import Mock, patch

from podcast_anything.config import Settings
from podcast_anything.handlers import fetch_article, generate_audio, rewrite_script


class FetchArticleHandlerTests(unittest.TestCase):
    def test_requires_job_id_and_one_source_input(self) -> None:
        with self.assertRaisesRegex(ValueError, "job_id"):
            fetch_article.handler({}, None)

        with self.assertRaisesRegex(ValueError, "exactly one of source_url or source_file_base64"):
            fetch_article.handler(
                {
                    "job_id": "job-1",
                    "source_url": "https://example.com/post",
                    "source_file_name": "notes.txt",
                    "source_file_base64": "aGVsbG8=",
                },
                None,
            )

    @patch("podcast_anything.handlers.fetch_article.put_text")
    @patch("podcast_anything.handlers.fetch_article.youtube.is_youtube_url", return_value=False)
    @patch(
        "podcast_anything.handlers.fetch_article.article.extract_text",
        return_value="clean article text",
    )
    @patch(
        "podcast_anything.handlers.fetch_article.article.fetch_html",
        return_value="<html>...</html>",
    )
    @patch("podcast_anything.handlers.fetch_article.load_settings")
    def test_fetches_extracts_and_stores_article(
        self,
        mock_settings: Mock,
        _mock_fetch_html: Mock,
        _mock_extract_text: Mock,
        _mock_is_youtube_url: Mock,
        mock_put_text: Mock,
    ) -> None:
        mock_settings.return_value = Settings(
            bucket="default-bucket",
            region="us-east-1",
            bedrock_model_id="amazon.nova-lite-v1:0",
            polly_voice_id="Joanna",
        )
        event = {
            "job_id": "job-123",
            "source_url": "https://example.com/post",
        }

        result = fetch_article.handler(event, None)

        expected_key = "jobs/job-123/source.txt"
        mock_put_text.assert_called_once_with("default-bucket", expected_key, "clean article text")
        self.assertEqual("default-bucket", result["bucket"])
        self.assertEqual("article", result["source_type"])
        self.assertEqual(expected_key, result["article_s3_key"])
        self.assertEqual(len("clean article text"), result["article_char_count"])

    @patch("podcast_anything.handlers.fetch_article.put_text")
    @patch(
        "podcast_anything.handlers.fetch_article.document.extract_text_from_bytes",
        return_value=("uploaded document text", "pdf"),
    )
    @patch("podcast_anything.handlers.fetch_article.article.fetch_html")
    @patch("podcast_anything.handlers.fetch_article.load_settings")
    def test_extracts_and_stores_uploaded_document(
        self,
        mock_settings: Mock,
        mock_fetch_html: Mock,
        mock_extract_document: Mock,
        mock_put_text: Mock,
    ) -> None:
        mock_settings.return_value = Settings(
            bucket="default-bucket",
            region="us-east-1",
            bedrock_model_id="amazon.nova-lite-v1:0",
            polly_voice_id="Joanna",
        )
        encoded_file = base64.b64encode(b"fake-pdf-bytes").decode("ascii")
        event = {
            "job_id": "job-doc-1",
            "source_file_name": "brief.pdf",
            "source_file_base64": encoded_file,
        }

        result = fetch_article.handler(event, None)

        mock_extract_document.assert_called_once_with(b"fake-pdf-bytes", "brief.pdf")
        mock_fetch_html.assert_not_called()
        mock_put_text.assert_called_once_with(
            "default-bucket",
            "jobs/job-doc-1/source.txt",
            "uploaded document text",
        )
        self.assertEqual("pdf", result["source_type"])
        self.assertEqual("jobs/job-doc-1/source.txt", result["article_s3_key"])
        self.assertNotIn("source_file_base64", result)

    @patch("podcast_anything.handlers.fetch_article.youtube.is_youtube_url", return_value=True)
    @patch("podcast_anything.handlers.fetch_article.load_settings")
    def test_rejects_youtube_url_without_provided_transcript(
        self,
        mock_settings: Mock,
        mock_is_youtube_url: Mock,
    ) -> None:
        mock_settings.return_value = Settings(
            bucket="default-bucket",
            region="us-east-1",
            bedrock_model_id="amazon.nova-lite-v1:0",
            polly_voice_id="Joanna",
        )
        event = {
            "job_id": "job-yt-1",
            "source_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        }

        with self.assertRaisesRegex(ValueError, "AWS-side YouTube transcript fetch is disabled"):
            fetch_article.handler(event, None)

        mock_is_youtube_url.assert_called_once_with(event["source_url"])

    @patch("podcast_anything.handlers.fetch_article.put_text")
    @patch("podcast_anything.handlers.fetch_article.youtube.fetch_transcript_text")
    @patch("podcast_anything.handlers.fetch_article.article.fetch_html")
    @patch("podcast_anything.handlers.fetch_article.load_settings")
    def test_uses_provided_source_text_and_skips_remote_fetch(
        self,
        mock_settings: Mock,
        mock_fetch_html: Mock,
        mock_fetch_transcript: Mock,
        mock_put_text: Mock,
    ) -> None:
        mock_settings.return_value = Settings(
            bucket="default-bucket",
            region="us-east-1",
            bedrock_model_id="amazon.nova-lite-v1:0",
            polly_voice_id="Joanna",
        )
        event = {
            "job_id": "job-yt-2",
            "source_url": "https://www.youtube.com/watch?v=7eNey0TN2pw",
            "source_text": "provided transcript text",
        }

        result = fetch_article.handler(event, None)

        mock_fetch_html.assert_not_called()
        mock_fetch_transcript.assert_not_called()
        mock_put_text.assert_called_once_with(
            "default-bucket",
            "jobs/job-yt-2/source.txt",
            "provided transcript text",
        )
        self.assertEqual("youtube", result["source_type"])
        self.assertNotIn("source_text", result)

    @patch("podcast_anything.handlers.fetch_article.load_settings")
    def test_rejects_invalid_uploaded_document_base64(self, mock_settings: Mock) -> None:
        mock_settings.return_value = Settings(
            bucket="default-bucket",
            region="us-east-1",
            bedrock_model_id="amazon.nova-lite-v1:0",
            polly_voice_id="Joanna",
        )
        event = {
            "job_id": "job-doc-2",
            "source_file_name": "brief.pdf",
            "source_file_base64": "not valid base64",
        }

        with self.assertRaisesRegex(ValueError, "source_file_base64 is not valid base64"):
            fetch_article.handler(event, None)


class RewriteScriptHandlerTests(unittest.TestCase):
    def test_requires_job_id_and_article_s3_key(self) -> None:
        with self.assertRaisesRegex(ValueError, "job_id and article_s3_key"):
            rewrite_script.handler({"job_id": "job-123"}, None)

    @patch("podcast_anything.handlers.rewrite_script.put_json")
    @patch("podcast_anything.handlers.rewrite_script.put_text")
    @patch("podcast_anything.handlers.rewrite_script.call_bedrock", return_value="podcast script")
    @patch(
        "podcast_anything.handlers.rewrite_script.build_podcast_prompt", return_value="prompt text"
    )
    @patch("podcast_anything.handlers.rewrite_script.get_text", return_value="article text")
    @patch("podcast_anything.handlers.rewrite_script.load_settings")
    def test_reads_article_rewrites_and_stores_outputs(
        self,
        mock_settings: Mock,
        mock_get_text: Mock,
        mock_build_prompt: Mock,
        mock_call_bedrock: Mock,
        mock_put_text: Mock,
        mock_put_json: Mock,
    ) -> None:
        mock_settings.return_value = Settings(
            bucket="default-bucket",
            region="us-east-1",
            bedrock_model_id="us.amazon.nova-lite-v1:0",
            polly_voice_id="Joanna",
        )
        event = {
            "job_id": "job-456",
            "source_url": "https://example.com/article",
            "source_type": "youtube",
            "title": "Sample Title",
            "style": "podcast",
            "script_mode": "duo",
            "article_s3_key": "jobs/job-456/source.txt",
        }

        result = rewrite_script.handler(event, None)

        script_key = "jobs/job-456/script.txt"
        metadata_key = "jobs/job-456/script.json"

        mock_get_text.assert_called_once_with("default-bucket", "jobs/job-456/source.txt")
        mock_build_prompt.assert_called_once_with(
            article_text="article text",
            title="Sample Title",
            style="podcast",
            source_type="youtube",
            script_mode="duo",
        )
        mock_call_bedrock.assert_called_once_with("us.amazon.nova-lite-v1:0", "prompt text")
        mock_put_text.assert_called_once_with("default-bucket", script_key, "podcast script")

        mock_put_json.assert_called_once()
        put_json_args = mock_put_json.call_args.args
        self.assertEqual("default-bucket", put_json_args[0])
        self.assertEqual(metadata_key, put_json_args[1])
        self.assertEqual(script_key, put_json_args[2]["script_s3_key"])
        self.assertEqual("us.amazon.nova-lite-v1:0", put_json_args[2]["model_id"])
        self.assertEqual("youtube", put_json_args[2]["source_type"])
        self.assertEqual("duo", put_json_args[2]["script_mode"])

        self.assertEqual(script_key, result["script_s3_key"])
        self.assertEqual(metadata_key, result["script_metadata_s3_key"])


class GenerateAudioHandlerTests(unittest.TestCase):
    def test_requires_job_id_and_script_s3_key(self) -> None:
        with self.assertRaisesRegex(ValueError, "job_id and script_s3_key"):
            generate_audio.handler({"job_id": "job-789"}, None)

    @patch("podcast_anything.handlers.generate_audio.put_bytes")
    @patch(
        "podcast_anything.handlers.generate_audio.synthesize_speech", return_value=b"audio-bytes"
    )
    @patch(
        "podcast_anything.handlers.generate_audio.get_text", return_value="one two three four five"
    )
    @patch("podcast_anything.handlers.generate_audio.load_settings")
    def test_reads_script_synthesizes_audio_and_stores_mp3(
        self,
        mock_settings: Mock,
        mock_get_text: Mock,
        mock_synthesize: Mock,
        mock_put_bytes: Mock,
    ) -> None:
        mock_settings.return_value = Settings(
            bucket="default-bucket",
            region="us-east-1",
            bedrock_model_id="us.amazon.nova-lite-v1:0",
            polly_voice_id="Amy",
        )
        event = {
            "job_id": "job-789",
            "script_s3_key": "jobs/job-789/script.txt",
        }

        result = generate_audio.handler(event, None)

        expected_audio_key = "jobs/job-789/audio.mp3"
        mock_get_text.assert_called_once_with("default-bucket", "jobs/job-789/script.txt")
        mock_synthesize.assert_called_once_with(
            "one two three four five",
            voice_id="Amy",
            provider="polly",
            output_format="mp3",
            text_type="ssml",
            max_text_chars=1800,
            elevenlabs_api_key=None,
            elevenlabs_model_id="eleven_multilingual_v2",
        )
        mock_put_bytes.assert_called_once_with(
            "default-bucket",
            expected_audio_key,
            b"audio-bytes",
            content_type="audio/mpeg",
        )

        self.assertEqual(expected_audio_key, result["audio_s3_key"])
        self.assertEqual(2, result["audio_estimated_duration_sec"])

    @patch("podcast_anything.handlers.generate_audio.put_bytes")
    @patch(
        "podcast_anything.handlers.generate_audio.synthesize_speech", return_value=b"audio-bytes"
    )
    @patch("podcast_anything.handlers.generate_audio.get_text", return_value="script")
    @patch("podcast_anything.handlers.generate_audio.load_settings")
    def test_uses_event_voice_override(
        self,
        mock_settings: Mock,
        _mock_get_text: Mock,
        mock_synthesize: Mock,
        _mock_put_bytes: Mock,
    ) -> None:
        mock_settings.return_value = Settings(
            bucket="default-bucket",
            region="us-east-1",
            bedrock_model_id="us.amazon.nova-lite-v1:0",
            polly_voice_id="Amy",
        )
        event = {
            "job_id": "job-101",
            "script_s3_key": "jobs/job-101/script.txt",
            "voice_id": "Joanna",
        }

        generate_audio.handler(event, None)
        mock_synthesize.assert_called_once_with(
            "script",
            voice_id="Joanna",
            provider="polly",
            output_format="mp3",
            text_type="ssml",
            max_text_chars=1800,
            elevenlabs_api_key=None,
            elevenlabs_model_id="eleven_multilingual_v2",
        )

    @patch("podcast_anything.handlers.generate_audio.put_bytes")
    @patch(
        "podcast_anything.handlers.generate_audio.synthesize_speech", return_value=b"audio-bytes"
    )
    @patch("podcast_anything.handlers.generate_audio.get_text", return_value="script")
    @patch("podcast_anything.handlers.generate_audio.load_settings")
    def test_uses_elevenlabs_defaults_when_provider_selected(
        self,
        mock_settings: Mock,
        _mock_get_text: Mock,
        mock_synthesize: Mock,
        _mock_put_bytes: Mock,
    ) -> None:
        mock_settings.return_value = Settings(
            bucket="default-bucket",
            region="us-east-1",
            bedrock_model_id="us.amazon.nova-lite-v1:0",
            tts_provider="elevenlabs",
            elevenlabs_api_key="test-elevenlabs-key",
            elevenlabs_voice_id="voice-from-settings",
            elevenlabs_model_id="eleven_multilingual_v2",
            elevenlabs_output_format="mp3_44100_128",
        )
        event = {
            "job_id": "job-102",
            "script_s3_key": "jobs/job-102/script.txt",
        }

        generate_audio.handler(event, None)
        mock_synthesize.assert_called_once_with(
            "script",
            voice_id="voice-from-settings",
            provider="elevenlabs",
            output_format="mp3_44100_128",
            text_type="text",
            max_text_chars=1800,
            elevenlabs_api_key="test-elevenlabs-key",
            elevenlabs_model_id="eleven_multilingual_v2",
        )

    @patch("podcast_anything.handlers.generate_audio.put_bytes")
    @patch("podcast_anything.handlers.generate_audio.synthesize_speech")
    @patch(
        "podcast_anything.handlers.generate_audio.get_text",
        return_value="HOST_A: hello there\nHOST_B: hi back",
    )
    @patch("podcast_anything.handlers.generate_audio.load_settings")
    def test_duo_script_mode_synthesizes_with_two_voices(
        self,
        mock_settings: Mock,
        _mock_get_text: Mock,
        mock_synthesize: Mock,
        mock_put_bytes: Mock,
    ) -> None:
        mock_settings.return_value = Settings(
            bucket="default-bucket",
            region="us-east-1",
            bedrock_model_id="us.amazon.nova-lite-v1:0",
            polly_voice_id="Amy",
            polly_duo_voice_id="Matthew",
        )
        mock_synthesize.side_effect = [b"voice-a", b"voice-b"]
        event = {
            "job_id": "job-103",
            "script_s3_key": "jobs/job-103/script.txt",
            "script_mode": "duo",
        }

        result = generate_audio.handler(event, None)

        self.assertEqual(2, mock_synthesize.call_count)
        first_call = mock_synthesize.call_args_list[0].kwargs
        second_call = mock_synthesize.call_args_list[1].kwargs
        self.assertEqual("Amy", first_call["voice_id"])
        self.assertEqual("Matthew", second_call["voice_id"])
        self.assertEqual("polly", first_call["provider"])
        mock_put_bytes.assert_called_once_with(
            "default-bucket",
            "jobs/job-103/audio.mp3",
            b"voice-avoice-b",
            content_type="audio/mpeg",
        )
        self.assertEqual("jobs/job-103/audio.mp3", result["audio_s3_key"])

    @patch("podcast_anything.handlers.generate_audio.put_bytes")
    @patch("podcast_anything.handlers.generate_audio.synthesize_speech")
    @patch(
        "podcast_anything.handlers.generate_audio.get_text",
        return_value="HOST_A: hello there\nHOST_B: hi back",
    )
    @patch("podcast_anything.handlers.generate_audio.load_settings")
    def test_duo_script_mode_uses_event_voice_overrides(
        self,
        mock_settings: Mock,
        _mock_get_text: Mock,
        mock_synthesize: Mock,
        _mock_put_bytes: Mock,
    ) -> None:
        mock_settings.return_value = Settings(
            bucket="default-bucket",
            region="us-east-1",
            bedrock_model_id="us.amazon.nova-lite-v1:0",
            polly_voice_id="Amy",
            polly_duo_voice_id="Matthew",
        )
        mock_synthesize.side_effect = [b"voice-a", b"voice-b"]
        event = {
            "job_id": "job-104",
            "script_s3_key": "jobs/job-104/script.txt",
            "script_mode": "duo",
            "voice_id": "Joanna",
            "voice_id_b": "Ruth",
        }

        generate_audio.handler(event, None)

        first_call = mock_synthesize.call_args_list[0].kwargs
        second_call = mock_synthesize.call_args_list[1].kwargs
        self.assertEqual("Joanna", first_call["voice_id"])
        self.assertEqual("Ruth", second_call["voice_id"])

    @patch("podcast_anything.handlers.generate_audio.put_bytes")
    @patch("podcast_anything.handlers.generate_audio.synthesize_speech")
    @patch(
        "podcast_anything.handlers.generate_audio.get_text",
        return_value="No speaker labels here",
    )
    @patch("podcast_anything.handlers.generate_audio.load_settings")
    def test_duo_script_mode_requires_host_labels(
        self,
        mock_settings: Mock,
        _mock_get_text: Mock,
        _mock_synthesize: Mock,
        _mock_put_bytes: Mock,
    ) -> None:
        mock_settings.return_value = Settings(
            bucket="default-bucket",
            region="us-east-1",
            bedrock_model_id="us.amazon.nova-lite-v1:0",
            polly_voice_id="Amy",
            polly_duo_voice_id="Matthew",
        )
        event = {
            "job_id": "job-105",
            "script_s3_key": "jobs/job-105/script.txt",
            "script_mode": "duo",
        }

        with self.assertRaisesRegex(ValueError, "script_mode=duo requires script lines"):
            generate_audio.handler(event, None)


if __name__ == "__main__":
    unittest.main()
