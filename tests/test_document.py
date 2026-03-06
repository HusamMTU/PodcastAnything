"""Unit tests for uploaded document parsing helpers."""

from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from podcast_anything.document import DocumentError, detect_document_type, extract_text_from_bytes


class DocumentTests(unittest.TestCase):
    def test_detects_supported_document_types(self) -> None:
        self.assertEqual("pdf", detect_document_type("report.PDF"))
        self.assertEqual("docx", detect_document_type("notes.docx"))
        self.assertEqual("txt", detect_document_type("transcript.txt"))

    def test_extracts_text_from_txt_bytes(self) -> None:
        text, document_type = extract_text_from_bytes("hello world".encode("utf-8"), "notes.txt")

        self.assertEqual("hello world", text)
        self.assertEqual("txt", document_type)

    @patch("podcast_anything.document.PdfReader")
    def test_extracts_text_from_pdf_pages(self, mock_pdf_reader: Mock) -> None:
        page_one = Mock()
        page_one.extract_text.return_value = "First page"
        page_two = Mock()
        page_two.extract_text.return_value = "  "
        page_three = Mock()
        page_three.extract_text.return_value = "Second page"
        reader = Mock()
        reader.pages = [page_one, page_two, page_three]
        mock_pdf_reader.return_value = reader

        text, document_type = extract_text_from_bytes(b"%PDF-1.7", "report.pdf")

        self.assertEqual("First page\n\nSecond page", text)
        self.assertEqual("pdf", document_type)
        mock_pdf_reader.assert_called_once()

    @patch("podcast_anything.document.docx2txt.process", return_value="Intro\n\nConclusion\n")
    def test_extracts_text_from_docx_paragraphs(self, mock_process: Mock) -> None:
        text, document_type = extract_text_from_bytes(b"fake-docx-bytes", "notes.docx")

        self.assertEqual("Intro\n\nConclusion", text)
        self.assertEqual("docx", document_type)
        mock_process.assert_called_once()

    def test_rejects_unsupported_document_type(self) -> None:
        with self.assertRaisesRegex(DocumentError, "Unsupported document type"):
            extract_text_from_bytes(b"hello", "notes.md")

    def test_rejects_empty_document(self) -> None:
        with self.assertRaisesRegex(DocumentError, "Uploaded document is empty"):
            extract_text_from_bytes(b"", "notes.txt")

    def test_rejects_document_without_readable_text(self) -> None:
        with self.assertRaisesRegex(DocumentError, "No readable text found"):
            extract_text_from_bytes(b"   ", "notes.txt")


if __name__ == "__main__":
    unittest.main()
