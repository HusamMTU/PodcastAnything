"""Unit tests for the local start_execution helper script."""

from __future__ import annotations

import argparse
import base64
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from podcast_anything.youtube import YouTubeTranscriptError


def _load_start_execution_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "start_execution.py"
    spec = importlib.util.spec_from_file_location("start_execution_script", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load scripts/start_execution.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


start_execution_script = _load_start_execution_module()


class SourceInputTests(unittest.TestCase):
    def test_read_source_file_payload_encodes_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = Path(temp_dir) / "brief.txt"
            source_path.write_bytes(b"hello from file")

            file_name, encoded = start_execution_script._read_source_file_payload(str(source_path))

        self.assertEqual("brief.txt", file_name)
        self.assertEqual(base64.b64encode(b"hello from file").decode("ascii"), encoded)

    def test_resolve_source_input_requires_exactly_one_source(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "exactly one"):
            start_execution_script._resolve_source_input(source=None, source_file=None)

        with self.assertRaisesRegex(RuntimeError, "exactly one"):
            start_execution_script._resolve_source_input(
                source="https://example.com/article",
                source_file="./brief.txt",
            )

    @patch(
        "start_execution_script._read_source_file_payload",
        return_value=("brief.txt", "aGVsbG8="),
    )
    def test_resolve_source_input_returns_file_payload(self, mock_read_source_file: Mock) -> None:
        source_url, source_file_payload = start_execution_script._resolve_source_input(
            source=None,
            source_file="./brief.txt",
        )

        self.assertIsNone(source_url)
        self.assertEqual(("brief.txt", "aGVsbG8="), source_file_payload)
        mock_read_source_file.assert_called_once_with("./brief.txt")


class ResolveSourceTextTests(unittest.TestCase):
    @patch("start_execution_script._read_transcript_file")
    def test_ignores_transcript_file_without_source_url(self, mock_read_file: Mock) -> None:
        result = start_execution_script._resolve_source_text(
            source_url=None,
            transcript_file="transcript.txt",
        )

        self.assertIsNone(result)
        mock_read_file.assert_not_called()

    @patch("start_execution_script.fetch_transcript_text")
    @patch("start_execution_script.is_youtube_url", return_value=False)
    @patch("start_execution_script._read_transcript_file", return_value=None)
    def test_returns_none_for_non_youtube_without_transcript_file(
        self,
        mock_read_file: Mock,
        mock_is_youtube_url: Mock,
        mock_fetch_transcript: Mock,
    ) -> None:
        result = start_execution_script._resolve_source_text(
            source_url="https://example.com/article",
            transcript_file=None,
        )

        self.assertIsNone(result)
        mock_read_file.assert_called_once_with(None)
        mock_is_youtube_url.assert_called_once_with("https://example.com/article")
        mock_fetch_transcript.assert_not_called()

    @patch("start_execution_script.fetch_transcript_text")
    @patch("start_execution_script.is_youtube_url")
    @patch("start_execution_script._read_transcript_file", return_value="provided transcript")
    def test_uses_transcript_file_before_youtube_fetch(
        self,
        mock_read_file: Mock,
        mock_is_youtube_url: Mock,
        mock_fetch_transcript: Mock,
    ) -> None:
        result = start_execution_script._resolve_source_text(
            source_url="https://www.youtube.com/watch?v=abc123XYZ00",
            transcript_file="transcript.txt",
        )

        self.assertEqual("provided transcript", result)
        mock_read_file.assert_called_once_with("transcript.txt")
        mock_is_youtube_url.assert_not_called()
        mock_fetch_transcript.assert_not_called()

    @patch("start_execution_script.fetch_transcript_text", return_value="auto fetched transcript")
    @patch("start_execution_script.is_youtube_url", return_value=True)
    @patch("start_execution_script._read_transcript_file", return_value=None)
    def test_auto_fetches_youtube_transcript_locally(
        self,
        mock_read_file: Mock,
        mock_is_youtube_url: Mock,
        mock_fetch_transcript: Mock,
    ) -> None:
        source_url = "https://www.youtube.com/watch?v=abc123XYZ00"

        result = start_execution_script._resolve_source_text(
            source_url=source_url,
            transcript_file=None,
        )

        self.assertEqual("auto fetched transcript", result)
        mock_read_file.assert_called_once_with(None)
        mock_is_youtube_url.assert_called_once_with(source_url)
        mock_fetch_transcript.assert_called_once_with(source_url)

    @patch("start_execution_script.fetch_transcript_text")
    @patch("start_execution_script.is_youtube_url", return_value=True)
    @patch("start_execution_script._read_transcript_file", return_value=None)
    def test_returns_clear_error_when_local_youtube_fetch_fails(
        self,
        _mock_read_file: Mock,
        _mock_is_youtube_url: Mock,
        mock_fetch_transcript: Mock,
    ) -> None:
        mock_fetch_transcript.side_effect = YouTubeTranscriptError("captions unavailable")

        with self.assertRaisesRegex(
            RuntimeError,
            "Could not fetch YouTube captions locally",
        ) as exc_info:
            start_execution_script._resolve_source_text(
                source_url="https://www.youtube.com/watch?v=abc123XYZ00",
                transcript_file=None,
            )

        self.assertIn("--transcript-file", str(exc_info.exception))
        self.assertIn("captions unavailable", str(exc_info.exception))


class MainTests(unittest.TestCase):
    @patch("start_execution_script._resolve_source_text")
    @patch(
        "start_execution_script._resolve_source_input",
        return_value=(None, ("brief.txt", "aGVsbG8=")),
    )
    @patch("start_execution_script._parse_args")
    def test_main_rejects_transcript_file_with_source_file(
        self,
        mock_parse_args: Mock,
        _mock_resolve_source_input: Mock,
        mock_resolve_source_text: Mock,
    ) -> None:
        mock_parse_args.return_value = argparse.Namespace(
            source=None,
            source_file="./brief.txt",
            style="podcast",
            script_mode="single",
            voice_id=None,
            voice_id_b=None,
            transcript_file="./transcript.txt",
            mode="api",
            region="us-east-1",
            stack_name="PodcastAnythingStack",
            api_url="https://example.com",
            state_machine_arn=None,
        )

        with self.assertRaisesRegex(
            SystemExit, "--transcript-file can only be used with a source URL"
        ):
            start_execution_script.main()

        mock_resolve_source_text.assert_not_called()


if __name__ == "__main__":
    unittest.main()
