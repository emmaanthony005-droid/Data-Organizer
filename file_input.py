"""
file_input.py - turns an uploaded file into raw text for parser.parse().

Excel/CSV/TXT are read as structured data directly.
PDF and images use text/table extraction and OCR respectively.
"""
import io
from typing import Tuple

import pandas as pd


def _df_to_text(df: pd.DataFrame) -> str:
    return df.to_csv(sep="\t", index=False)


def extract_text(filename: str, file_bytes: bytes) -> Tuple[str, str]:
    """Returns (raw_text, method_used). Raises ValueError on
    unsupported/unreadable files."""
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
        except ImportError:
            raise ValueError(
                "PDF support requires the 'pdfplumber' package. "
                "Install it with: pip install pdfplumber"
            )
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
        except ImportError:
            raise ValueError(
                "Image OCR requires 'pytesseract' + 'Pillow' and a system "
                "Tesseract OCR install. See README for instructions."
            )
        img = Image.open(io.BytesIO(file_bytes))
        text = pytesseract.image_to_string(img)
        return text, "Image OCR (Tesseract) -- verify carefully, OCR can misread digits"

    raise ValueError(
        f"Unsupported file type for '{filename}'. "
        "Supported: .txt, .csv, .xlsx, .xls, .pdf, .jpg, .jpeg, .png"
    )
