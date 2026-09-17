"""
file_input.py — turns an uploaded file into raw text for parser.parse().

Per spec: Excel/CSV/TXT are read as structured data directly (not OCR'd).
PDF and images fall back to text/table extraction and OCR respectively.
These are optional conveniences — pasting text is always the primary path
and never required to go through a file.
"""
import io
from typing import Tuple

import pandas as pd


def _df_to_text(df: pd.DataFrame) -> str:
    """Render a dataframe back into tab-separated text so it flows through
    the same deterministic parser as pasted text (no values are altered —
    pandas reads cells as strings where possible via dtype=str)."""
    return df.to_csv(sep="\t", index=False)


def extract_text(filename: str, file_bytes: bytes) -> Tuple[str, str]:
    """Returns (raw_text, method_used). Raises ValueError with a clear
    message on unsupported/unreadable files rather than crashing."""
    name = filename.lower()

    if name.endswith(".txt"):
        return file_bytes.decode("utf-8", errors="replace"), "text file"

    if name.endswith(".csv"):
        df = pd.read_csv(io.BytesIO(file_bytes), dtype=str, keep_default_na=False)
        return _df_to_text(df), "CSV (read directly)"

    if name.endswith((".xlsx", ".xls")):
        df = pd.read_excel(io.BytesIO(file_bytes), dtype=str, engine=None)
        df = df.fillna("")
        return _df_to_text(df), "Excel (read directly)"

    if name.endswith(".pdf"):
        try:
            import pdfplumber
        except ImportError as e:
            raise ValueError(
                "PDF support requires the 'pdfplumber' package (see requirements.txt)."
            ) from e
        text_parts = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text_parts.append(page_text)
                for table in page.extract_tables() or []:
                    for row in table:
                        text_parts.append("\t".join(c or "" for c in row))
        return "\n".join(text_parts), "PDF text/table extraction"

    if name.endswith((".jpg", ".jpeg", ".png")):
        try:
            import pytesseract
            from PIL import Image
        except ImportError as e:
            raise ValueError(
                "Image support requires 'pytesseract' + 'Pillow' and a system "
                "Tesseract OCR install (see requirements.txt / README)."
            ) from e
        img = Image.open(io.BytesIO(file_bytes))
        text = pytesseract.image_to_string(img)
        return text, "Image OCR (Tesseract) — verify carefully, OCR can misread digits"

    raise ValueError(
        f"Unsupported file type for '{filename}'. Supported: .txt, .csv, .xlsx, .xls, .pdf, .jpg, .jpeg, .png"
    )
