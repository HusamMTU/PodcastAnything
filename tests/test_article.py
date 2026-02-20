"""Unit tests for article fetching and extraction."""
from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

import requests

from podcast_anything.article import ArticleError, extract_text, fetch_html


class FetchHtmlTests(unittest.TestCase):
    def test_rejects_non_http_urls(self) -> None:
        with self.assertRaisesRegex(ArticleError, "source_url must start"):
            fetch_html("ftp://example.com/post")

    @patch("podcast_anything.article.requests.get")
    def test_wraps_request_errors(self, mock_get: Mock) -> None:
        mock_get.side_effect = requests.RequestException("connection failed")

        with self.assertRaisesRegex(ArticleError, "Failed to fetch article"):
            fetch_html("https://example.com/post")


class ExtractTextTests(unittest.TestCase):
    def test_prefers_article_tag_content(self) -> None:
        html = """
        <html><body>
          <article><p>Intro section.</p><p>Main details.</p></article>
          <p>Fallback paragraph.</p>
        </body></html>
        """

        self.assertEqual("Intro section.\nMain details.", extract_text(html))

    def test_falls_back_to_page_paragraphs(self) -> None:
        html = "<html><body><p>One.</p><p>Two.</p></body></html>"

        self.assertEqual("One.\nTwo.", extract_text(html))

    def test_raises_if_no_readable_paragraphs(self) -> None:
        html = "<html><body><div>No paragraphs here.</div></body></html>"

        with self.assertRaisesRegex(ArticleError, "No readable text"):
            extract_text(html)


if __name__ == "__main__":
    unittest.main()
