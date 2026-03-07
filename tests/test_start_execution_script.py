"""Unit tests for the local start_execution helper script."""

from __future__ import annotations

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
    def test_returns_none_without_source_url(self) -> None:
        result = start_execution_script._resolve_source_text(source_url=None)

        self.assertIsNone(result)

    @patch("start_execution_script.fetch_transcript_text")
    @patch("start_execution_script.is_youtube_url", return_value=False)
    def test_returns_none_for_non_youtube_url(
        self,
        mock_is_youtube_url: Mock,
        mock_fetch_transcript: Mock,
    ) -> None:
        result = start_execution_script._resolve_source_text(source_url="https://example.com/article")

        self.assertIsNone(result)
        mock_is_youtube_url.assert_called_once_with("https://example.com/article")
        mock_fetch_transcript.assert_not_called()

    @patch("start_execution_script.fetch_transcript_text", return_value="auto fetched transcript")
    @patch("start_execution_script.is_youtube_url", return_value=True)
    def test_auto_fetches_youtube_transcript_locally(
        self,
        mock_is_youtube_url: Mock,
        mock_fetch_transcript: Mock,
    ) -> None:
        source_url = "https://www.youtube.com/watch?v=abc123XYZ00"

        result = start_execution_script._resolve_source_text(source_url=source_url)

        self.assertEqual("auto fetched transcript", result)
        mock_is_youtube_url.assert_called_once_with(source_url)
        mock_fetch_transcript.assert_called_once_with(source_url)

    @patch("start_execution_script.fetch_transcript_text")
    @patch("start_execution_script.is_youtube_url", return_value=True)
    def test_returns_clear_error_when_local_youtube_fetch_fails(
        self,
        _mock_is_youtube_url: Mock,
        mock_fetch_transcript: Mock,
    ) -> None:
        mock_fetch_transcript.side_effect = YouTubeTranscriptError("captions unavailable")

        with self.assertRaisesRegex(
            RuntimeError,
            "Could not fetch YouTube captions locally",
        ) as exc_info:
            start_execution_script._resolve_source_text(
                source_url="https://www.youtube.com/watch?v=abc123XYZ00"
            )

        self.assertIn("different local network", str(exc_info.exception))
        self.assertIn("captions unavailable", str(exc_info.exception))


if __name__ == "__main__":
    unittest.main()
