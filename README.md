# ICP Results Organizer

Paste raw ICP results → click **Organize Results** → get a clean, structured,
exportable table. Excel is never required as input — it's an optional output
format only.

## Run it

```bash
pip install -r requirements.txt
streamlit run app.py
```

(The `pdfplumber` / `pytesseract` / `Pillow` lines in `requirements.txt` are
only needed if you want to upload PDFs or photos of results — paste, `.txt`,
`.csv`, and `.xlsx` all work without them. `pytesseract` also needs the
Tesseract OCR system binary installed separately if you want image OCR.)

## What this project is

Built from `ICP_result_organizer_prompt_v2 (improved).md`'s phased spec
(Phase 1 MVP → Phase 2 depth → Phase 3 polish), with two additions:

1. **A second, real-world layout is fully supported**, modeled on
   `New_app_project.txt` — a wide, tab-separated instrument export
   (`Type / Name / Measurement Date / Value Type` + one column per
   `Element Wavelength (Channel)`, with replicate/Min-Max-Calibration/
   Reported/Mean/SD/RSD rows per sample block). The app auto-detects
   whether pasted/uploaded text is this "wide" layout or the simple
   "block" layout (`Sample: S001` + stacked `Element Result Unit` lines)
   and parses accordingly — you can also force one manually on the Input
   page. It was tested end-to-end against your full uploaded file
   (46 samples, 30 elements/58 channels, 3,068 reported results,
   **0 lines needing review**).
2. **Improvements folded in from the second prompt** (`New_app_project.txt`'s
   own instructions): file upload for `.txt/.csv/.xlsx/.xls` (read directly,
   no OCR needed), optional PDF text/table extraction and image OCR,
   richer sample metadata (method, date, batch, dilution, sequence, etc.),
   element+wavelength kept as separate analytical channels, broader
   filtering/search, and multi-sheet Excel export as the main structured
   output format alongside CSV/clipboard.

## Project structure

- `app.py` — Streamlit UI (Input, Parse Preview, Organized Results, Samples,
  Elements, Search, Data Quality, Analytics, Sample Comparison, Export, Help)
- `parser.py` — deterministic, regex/pattern-based parser for both layouts
  (no external AI/LLM is used to interpret results)
- `models.py` — `ResultRecord` / `SampleMeta` / `ParseResult` data structures
- `exporter.py` — CSV / clipboard-text / multi-sheet Excel export
- `file_input.py` — turns an uploaded file into raw text for the parser
- `demo_data.py` — two labeled `DEMO DATA` datasets, one per layout

## Data integrity (non-negotiable, and tested)

Every result is stored and displayed as the **exact original string** —
`125.430` never becomes `125.43`, `<0.01` keeps its qualifier, `«100»` keeps
its brackets, `ND`/`N.D.` are never turned into `0`, and scientific notation
like `1.2E-04` is never converted to decimal. A separate numeric value is
derived only for sorting/analytics and never overwrites what's displayed.
Anything the parser isn't confident about is flagged in **Data Quality**
with its original text and line number — nothing is silently dropped.

## What's intentionally not built yet

Phase 3 items — pagination/virtualization for very large tables, a full
automated `pytest` suite, and persistent storage (SQLite) — are left as
extension points (see comments in `parser.py`/`models.py`) rather than
built now, per the spec's "build in order, each phase fully working before
the next" instruction. Phase 1 and the core of Phase 2 (filtering, sorting,
analytics, comparison, Excel export, processing log, "New Analysis" confirm)
are implemented and working.
