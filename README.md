# ICP Results Organizer

A self-hosted web application for organizing, viewing, analyzing, and exporting ICP / ICP-OES / ICP-MS laboratory results.

Paste raw results or upload files (TXT, CSV, XLSX, PDF, images). The parser auto-detects block-style and wide wavelength-export layouts, organizes everything into a clean grid, and lets you filter, search, chart, compare samples, and export to CSV or multi-sheet Excel.

---

## Quick start

### 1. Prerequisites

- **Python 3.9+** (check with `python --version` or `python3 --version`)
- **pip** (comes with Python)

Optional, for PDF and image support:

- **Tesseract OCR** (only needed if you want to upload scanned images)
  - Windows: download from https://github.com/UB-Mannheim/tesseract/wiki
  - macOS: `brew install tesseract`
  - Ubuntu/Debian: `sudo apt install tesseract-ocr`

### 2. Install

```bash
# Clone or copy this folder to your machine, then:
cd icp-organizer

# Create a virtual environment (recommended)
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Run

```bash
python app.py
```

The app starts at **http://127.0.0.1:5000**. Open that URL in any browser.

To make it accessible to other devices on the same network:

```bash
python app.py --host 0.0.0.0 --port 5000
```

Then open `http://<your-ip>:5000` from any device on the network.

### 4. Use

1. Paste raw ICP results into the text area, or upload a file (TXT, CSV, XLSX, PDF, JPG, PNG).
2. Click **Organize results**.
3. Review the parse preview (sample/element/result counts, any lines that need review).
4. Click **Confirm and organize**.
5. Browse the results grid, per-sample and per-element views, search, data quality, analytics charts, sample comparison, and export tabs.
6. Export to CSV or multi-sheet Excel workbook.

---

## Project structure

```
icp-organizer/
  app.py              Flask server + file-processing API
  parser.py           Deterministic regex/pattern-based ICP parser
  models.py           Data structures (ParseResult, ResultRecord, etc.)
  exporter.py         DataFrame builders and Excel/CSV export
  demo_data.py        Synthetic demo datasets (block + wide layouts)
  file_input.py       File reader (TXT, CSV, XLSX, PDF, image OCR)
  requirements.txt    Python dependencies
  README.md           This file
  templates/
    index.html        The full frontend (single-page app)
```

## Data integrity guarantee

The application never rounds, truncates, drops trailing zeros, converts units, converts scientific notation, replaces ND with 0, strips qualifiers, or guesses a value it is not confident about. Every exported cell contains the exact text from the original input. Anything ambiguous is flagged in the Data Quality tab with its original text and line number.

## Supported layouts

- **Block-style**: `Sample: S001` or `SAMPLE ID: S003` headers followed by stacked `Element Result Unit` lines, with optional metadata (Method, Date, Batch, etc.).
- **Wide wavelength-export**: tab-separated instrument output with `Type / Name / Measurement Date / Value Type` columns followed by `Element Wavelength (Channel)` columns. Replicate rows, Reported, Mean, SD, RSD, and calibration-range rows are all captured.

Auto-detection picks the right parser. You can override it with the Layout dropdown.

## License

MIT. Use it however you like.
