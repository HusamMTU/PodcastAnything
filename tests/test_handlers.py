"""Unit tests for Lambda handlers."""
from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from ml_publication.config import Settings
from ml_publication.handlers import fetch_article, generate_audio, rewrite_script


class FetchArticleHandlerTests(unittest.TestCase):
    def test_requires_job_id_and_source_url(self) -> None:
        with self.assertRaisesRegex(ValueError, "job_id and source_url"):
            fetch_article.handler({}, None)

    @patch("ml_publication.handlers.fetch_article.put_text")
    @patch("ml_publication.handlers.fetch_article.article.extract_text", return_value="clean article text")
    @patch("ml_publication.handlers.fetch_article.article.fetch_html", return_value="<html>...</html>")
    @patch("ml_publication.handlers.fetch_article.load_settings")
    def test_fetches_extracts_and_stores_article(
        self,
        mock_settings: Mock,
        _mock_fetch_html: Mock,
        _mock_extract_text: Mock,
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

        expected_key = "jobs/job-123/article.txt"
        mock_put_text.assert_called_once_with("default-bucket", expected_key, "clean article text")
        self.assertEqual("default-bucket", result["bucket"])
        self.assertEqual(expected_key, result["article_s3_key"])
        self.assertEqual(len("clean article text"), result["article_char_count"])


class RewriteScriptHandlerTests(unittest.TestCase):
    def test_requires_job_id_and_article_s3_key(self) -> None:
        with self.assertRaisesRegex(ValueError, "job_id and article_s3_key"):
            rewrite_script.handler({"job_id": "job-123"}, None)

    @patch("ml_publication.handlers.rewrite_script.put_json")
    @patch("ml_publication.handlers.rewrite_script.put_text")
    @patch("ml_publication.handlers.rewrite_script.call_bedrock", return_value="podcast script")
    @patch("ml_publication.handlers.rewrite_script.build_podcast_prompt", return_value="prompt text")
    @patch("ml_publication.handlers.rewrite_script.get_text", return_value="article text")
    @patch("ml_publication.handlers.rewrite_script.load_settings")
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
            "title": "Sample Title",
            "style": "podcast",
            "article_s3_key": "jobs/job-456/article.txt",
        }

        result = rewrite_script.handler(event, None)

        script_key = "jobs/job-456/script.txt"
        metadata_key = "jobs/job-456/script.json"

        mock_get_text.assert_called_once_with("default-bucket", "jobs/job-456/article.txt")
        mock_build_prompt.assert_called_once_with(
            article_text="article text",
            title="Sample Title",
            style="podcast",
        )
        mock_call_bedrock.assert_called_once_with("us.amazon.nova-lite-v1:0", "prompt text")
        mock_put_text.assert_called_once_with("default-bucket", script_key, "podcast script")

        mock_put_json.assert_called_once()
        put_json_args = mock_put_json.call_args.args
        self.assertEqual("default-bucket", put_json_args[0])
        self.assertEqual(metadata_key, put_json_args[1])
        self.assertEqual(script_key, put_json_args[2]["script_s3_key"])
        self.assertEqual("us.amazon.nova-lite-v1:0", put_json_args[2]["model_id"])

        self.assertEqual(script_key, result["script_s3_key"])
        self.assertEqual(metadata_key, result["script_metadata_s3_key"])


class GenerateAudioHandlerTests(unittest.TestCase):
    def test_requires_job_id_and_script_s3_key(self) -> None:
        with self.assertRaisesRegex(ValueError, "job_id and script_s3_key"):
            generate_audio.handler({"job_id": "job-789"}, None)

    @patch("ml_publication.handlers.generate_audio.put_bytes")
    @patch("ml_publication.handlers.generate_audio.synthesize_speech", return_value=b"audio-bytes")
    @patch("ml_publication.handlers.generate_audio.get_text", return_value="one two three four five")
    @patch("ml_publication.handlers.generate_audio.load_settings")
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
        mock_synthesize.assert_called_once_with("one two three four five", voice_id="Amy")
        mock_put_bytes.assert_called_once_with(
            "default-bucket",
            expected_audio_key,
            b"audio-bytes",
            content_type="audio/mpeg",
        )

        self.assertEqual(expected_audio_key, result["audio_s3_key"])
        self.assertEqual(2, result["audio_estimated_duration_sec"])

    @patch("ml_publication.handlers.generate_audio.put_bytes")
    @patch("ml_publication.handlers.generate_audio.synthesize_speech", return_value=b"audio-bytes")
    @patch("ml_publication.handlers.generate_audio.get_text", return_value="script")
    @patch("ml_publication.handlers.generate_audio.load_settings")
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
        mock_synthesize.assert_called_once_with("script", voice_id="Joanna")


if __name__ == "__main__":
    unittest.main()
