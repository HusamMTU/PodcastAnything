"""Extract text from uploaded document files."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile
from types import SimpleNamespace

try:
    import docx2txt
except ModuleNotFoundError:  # pragma: no cover - exercised via runtime error path
    docx2txt = SimpleNamespace(process=None)

try:
    from pypdf import PdfReader
except ModuleNotFoundError:  # pragma: no cover - exercised via runtime error path
    PdfReader = None


class DocumentError(RuntimeError):
    """Raised when an uploaded document cannot be processed."""


_SUPPORTED_EXTENSIONS = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".txt": "txt",
}


def detect_document_type(filename: str) -> str:
    extension = Path(filename).suffix.lower()
    document_type = _SUPPORTED_EXTENSIONS.get(extension)
    if not document_type:
        supported = ", ".join(sorted(_SUPPORTED_EXTENSIONS))
        raise DocumentError(
            f"Unsupported document type '{extension or filename}'. Use: {supported}"
        )
    return document_type


def _extract_pdf_text(file_bytes: bytes) -> str:
    if PdfReader is None:
        raise DocumentError("PDF support requires the `pypdf` package to be installed.")

    try:
        reader = PdfReader(BytesIO(file_bytes))
    except Exception as exc:  # pragma: no cover - library-specific failures
        raise DocumentError(f"Failed to parse PDF document: {exc}") from exc

    extracted = []
    for page in reader.pages:
        page_text = (page.extract_text() or "").strip()
        if page_text:
            extracted.append(page_text)
    return "\n\n".join(extracted).strip()


def _extract_docx_text(file_bytes: bytes) -> str:
    if docx2txt.process is None:
        raise DocumentError("DOCX support requires the `docx2txt` package to be installed.")

    with NamedTemporaryFile(suffix=".docx") as temp_file:
        temp_file.write(file_bytes)
        temp_file.flush()
        try:
            raw_text = docx2txt.process(temp_file.name) or ""
        except Exception as exc:  # pragma: no cover - library-specific failures
            raise DocumentError(f"Failed to parse DOCX document: {exc}") from exc

    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    return "\n\n".join(lines).strip()


def _extract_txt_text(file_bytes: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            return file_bytes.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    raise DocumentError("Failed to decode TXT document with supported encodings.")


def extract_text_from_bytes(file_bytes: bytes, filename: str) -> tuple[str, str]:
    if not file_bytes:
        raise DocumentError("Uploaded document is empty.")

    document_type = detect_document_type(filename)
    if document_type == "pdf":
        text = _extract_pdf_text(file_bytes)
    elif document_type == "docx":
        text = _extract_docx_text(file_bytes)
    else:
        text = _extract_txt_text(file_bytes)

    if not text:
        raise DocumentError(f"No readable text found in uploaded {document_type.upper()} document.")
    return text, document_type
