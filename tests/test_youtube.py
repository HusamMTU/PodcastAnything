"""Unit tests for YouTube transcript URL parsing helpers."""
from __future__ import annotations

import unittest

from podcast_anything.youtube import YouTubeTranscriptError, extract_video_id, is_youtube_url


class YouTubeUrlTests(unittest.TestCase):
    def test_detects_supported_youtube_hosts(self) -> None:
        self.assertTrue(is_youtube_url("https://www.youtube.com/watch?v=abc123"))
        self.assertTrue(is_youtube_url("https://youtu.be/abc123"))
        self.assertFalse(is_youtube_url("https://example.com/video"))

    def test_extracts_video_id_from_common_formats(self) -> None:
        cases = [
            ("https://www.youtube.com/watch?v=abc123XYZ00", "abc123XYZ00"),
            ("https://youtu.be/abc123XYZ00", "abc123XYZ00"),
            ("https://www.youtube.com/shorts/abc123XYZ00", "abc123XYZ00"),
            ("https://www.youtube.com/embed/abc123XYZ00", "abc123XYZ00"),
        ]
        for url, expected in cases:
            with self.subTest(url=url):
                self.assertEqual(expected, extract_video_id(url))

    def test_raises_when_video_id_cannot_be_extracted(self) -> None:
        with self.assertRaisesRegex(YouTubeTranscriptError, "extract video id"):
            extract_video_id("https://www.youtube.com/watch")


if __name__ == "__main__":
    unittest.main()

