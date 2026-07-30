"""
Text extraction service — handles PDF, DOCX, and plain TXT files.
"""
import io
from pathlib import Path


def extract_text(file_path: str) -> str:
    """
    Extract raw text from a document file.
    Supports: .pdf, .docx, .txt
    Returns empty string on failure (caller handles gracefully).
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    try:
        if suffix == ".pdf":
            return _extract_pdf(file_path)
        elif suffix == ".docx":
            return _extract_docx(file_path)
        elif suffix == ".txt":
            return _extract_txt(file_path)
        else:
            return ""
    except Exception as e:
        print(f"[Extractor] Failed to extract {file_path}: {e}")
        return ""


def _extract_pdf(file_path: str) -> str:
    try:
        from pypdf import PdfReader
        reader = PdfReader(file_path)
        text_parts = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(text_parts).strip()
    except Exception:
        try:
            import fitz  # PyMuPDF fallback
            doc = fitz.open(file_path)
            text_parts = [page.get_text() for page in doc]
            doc.close()
            return "\n".join(text_parts).strip()
        except Exception as e:
            print(f"[Extractor] PDF extraction error: {e}")
            return ""


def _extract_docx(file_path: str) -> str:
    from docx import Document
    doc = Document(file_path)
    paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
    return "\n".join(paragraphs).strip()


def _extract_txt(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        return f.read().strip()
