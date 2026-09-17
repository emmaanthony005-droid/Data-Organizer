"""
parser.py — deterministic, regex/pattern-based ICP results parser.

No external AI/LLM is used to interpret results (per spec). Everything is
rule-based so behaviour is reproducible and auditable.

Two layouts are auto-detected and supported out of the box:

  * "block"  — a sample header line ("Sample: S001" / "SAMPLE ID: S003"),
               optionally followed by metadata (Method/Date/Batch/...),
               then stacked "<Element> <Result> [<Unit>]" lines, repeated
               per sample. This is the layout required by Phase 1's test
               fixture and is the common case for simple pasted results.

  * "wide"   — a wide, tab-separated instrument export: one header row of
               "<Element> <Wavelength> (<Channel>)" columns, a units row,
               then per-sample blocks of rows (replicate 1/2/3, Min/Max
               Calibration Range, Reported, Mean, SD, RSD) — the format
               produced by many ICP-OES/ICP-MS control software packages
               (this is the layout of the real export used as this
               project's second demo dataset).

Anything that cannot be confidently classified is sent to the review list
with its original text and line number — nothing is silently dropped or
guessed at.

CONFIDENCE RULE (documented, adjustable threshold — see CONFIDENT_MIN_PARTS
and the regexes below):
  A block-layout line is "confident" when it has an element-like token
  AND a result-like token (qualifier/number, «bracketed», or ND/N.D.).
  A unit token is optional for confidence but captured when present.
  A line matching only the element-like OR only the result-like part
  (not both) is flagged for review, as is any line that does not fit
  either pattern shape at all.
"""
import re
from typing import Dict, List, Optional, Tuple

from models import ParseResult, ResultRecord, SampleMeta, ReviewItem

# ---------------------------------------------------------------------------
# Shared regexes / constants
# ---------------------------------------------------------------------------

QUALIFIER_CHARS = ("<", ">", "\u2264", "\u2265")  # <, >, ≤, ≥
ND_RE = re.compile(r"^(N\.?D\.?|ND)$", re.IGNORECASE)
NUMISH_RE = re.compile(
    r"^[<>\u2264\u2265]?\s*\u00ab?\s*-?\d[\d,]*\.?\d*(?:[eE][+-]?\d+)?\s*\u00bb?$"
)
ELEMENT_TOKEN_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]{0,6}$")
HEADER_WORDS = {"element", "result", "unit", "units", "analyte", "value", "wavelength"}

SAMPLE_HEADER_RE = re.compile(
    r"^\s*(SAMPLE\s*ID|SAMPLE)\s*[:#]?\s*(\S+)", re.IGNORECASE
)
META_KEY_RE = re.compile(
    r"\b(Method|Date|Batch|Project|Instrument|Dilution(?:\s*Factor)?|Sequence(?:\s*Name)?|"
    r"Measurement\s*Date|Calculation\s*Date|Sample\s*Type)\s*:\s*"
    r"([^\t]+?)(?=\s{2,}[A-Za-z][A-Za-z \-/]{1,20}?\s*:|$)",
    re.IGNORECASE,
)

CONFIDENT_MIN_PARTS = 2  # element token + result token = confident (unit optional)

WIDE_ELEMENT_COL_RE = re.compile(r"^([A-Za-z]{1,3})\s+([\d.]+)\s*\(([A-Za-z])\)\s*$")
WIDE_HEADER_HINT_RE = re.compile(r"value\s*type", re.IGNORECASE)
WIDE_ELEM_ANYWHERE_RE = re.compile(r"\b[A-Za-z]{1,2}\s+\d{2,3}\.\d{2,3}\s*\(")


# ---------------------------------------------------------------------------
# Helpers used by both layouts
# ---------------------------------------------------------------------------

def extract_qualifier(value: str) -> str:
    v = value.strip()
    if ND_RE.match(v):
        return v.upper() if v.upper() == "ND" else v
    if v.startswith("\u00ab") or v.endswith("\u00bb"):
        return "\u00ab\u00bb"
    for ch in QUALIFIER_CHARS:
        if v.startswith(ch):
            return ch
    return ""


def extract_numeric(value: str) -> Optional[float]:
    """Best-effort derived number for sorting/analytics ONLY. Never used to
    change what's displayed."""
    v = value.strip()
    if ND_RE.match(v):
        return None
    v2 = v.strip("\u00ab\u00bb")
    for ch in QUALIFIER_CHARS:
        if v2.startswith(ch):
            v2 = v2[len(ch):].strip()
    v2 = v2.replace(",", "")
    m = re.match(r"^-?\d+(\.\d+)?([eE][+-]?\d+)?", v2)
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def extract_unit_suffix(value: str) -> str:
    """Pulls a trailing non-numeric unit token off a raw cell, e.g.
    '4.214E06 cps' -> 'cps', '72.7 %' -> '%'. Does not alter `result`."""
    v = value.strip()
    m = re.search(r"([A-Za-z%\u00b5][A-Za-z%/\u00b5]*)\s*$", v)
    if m and not ND_RE.match(v):
        return m.group(1)
    return ""


# ---------------------------------------------------------------------------
# Layout detection
# ---------------------------------------------------------------------------

def classify_layout(text: str) -> str:
    lines = [l for l in text.splitlines() if l.strip()]
    if not lines:
        return "block"
    head = "\n".join(lines[:6])
    tab_heavy = any(l.count("\t") >= 4 for l in lines[:6])
    if tab_heavy and (WIDE_HEADER_HINT_RE.search(head) or WIDE_ELEM_ANYWHERE_RE.search(head)):
        return "wide"
    return "block"


# ---------------------------------------------------------------------------
# BLOCK layout parser
# ---------------------------------------------------------------------------

def _try_parse_result_line(parts: List[str], line_no: int, raw: str) -> Tuple[Optional[dict], Optional[str]]:
    """Returns (fields_dict, review_reason). fields_dict is None if the line
    could not be interpreted at all as a result-shaped line."""
    if len(parts) < 2:
        return None, "Line does not have an element + result shape"

    element_tok, result_tok = parts[0], parts[1]
    unit_tok = parts[2] if len(parts) > 2 else ""

    element_ok = bool(ELEMENT_TOKEN_RE.match(element_tok)) and element_tok.lower() not in HEADER_WORDS
    result_ok = bool(NUMISH_RE.match(result_tok)) or bool(ND_RE.match(result_tok))

    if element_ok and result_ok:
        return {
            "element": element_tok,
            "result": result_tok,
            "unit": unit_tok,
        }, None

    if element_ok and not result_ok:
        return None, f"Element-like token '{element_tok}' found but no recognizable result value"
    if result_ok and not element_ok:
        return None, f"Result-like value '{result_tok}' found but no recognizable element token"
    return None, "Line matches neither an element token nor a result value pattern"


def parse_block(text: str) -> ParseResult:
    lines = text.splitlines()
    pr = ParseResult(raw_text=text, layout_detected="block")
    current_sample: Optional[str] = None

    for i, raw in enumerate(lines):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue

        m = SAMPLE_HEADER_RE.match(stripped)
        if m:
            current_sample = m.group(2).strip()
            pr.samples.setdefault(current_sample, SampleMeta(sample_id=current_sample))
            rest = stripped[m.end():]
            for k, v in META_KEY_RE.findall(rest):
                pr.samples[current_sample].metadata[k.strip()] = v.strip()
            continue

        if META_KEY_RE.search(stripped) and current_sample:
            metas = META_KEY_RE.findall(stripped)
            if metas:
                for k, v in metas:
                    pr.samples[current_sample].metadata[k.strip()] = v.strip()
                continue

        # structural table header e.g. "Element Result Unit"
        tokens_lower = re.split(r"\s+", stripped.lower())
        if len(tokens_lower) <= 4 and set(tokens_lower) & HEADER_WORDS:
            continue

        parts = [p for p in re.split(r"\t+|\s{2,}|\s+", stripped) if p != ""]
        fields, reason = _try_parse_result_line(parts, i + 1, raw)

        if fields is None:
            pr.review_items.append(ReviewItem(line=i + 1, text=raw, reason=reason or "Unrecognized line"))
            continue
        if current_sample is None:
            pr.review_items.append(
                ReviewItem(line=i + 1, text=raw, reason="No sample header seen yet — no sample context")
            )
            continue

        rec = ResultRecord(
            sample_id=current_sample,
            element=fields["element"],
            result=fields["result"],
            unit=fields["unit"],
            value_type="Result",
            qualifier=extract_qualifier(fields["result"]),
            numeric_value=extract_numeric(fields["result"]),
            source_line=i + 1,
            source_text=raw,
            layout="block",
            confidence="confident",
        )
        pr.records.append(rec)
        pr.samples[current_sample].source_lines.append(i + 1)

    return pr


# ---------------------------------------------------------------------------
# WIDE (wavelength-export) layout parser
# ---------------------------------------------------------------------------

def parse_wide(text: str) -> ParseResult:
    raw_lines = text.splitlines()
    pr = ParseResult(raw_text=text, layout_detected="wide")

    header_idx = None
    for i, l in enumerate(raw_lines):
        if "\t" in l and WIDE_HEADER_HINT_RE.search(l):
            header_idx = i
            break
    if header_idx is None:
        # Fall back: treat as block if we can't even find the header
        return parse_block(text)

    header_cols = raw_lines[header_idx].split("\t")
    unit_idx = header_idx + 1
    unit_cols = raw_lines[unit_idx].split("\t") if unit_idx < len(raw_lines) else []

    elem_headers = []  # (col_index, element, wavelength, channel_type)
    for ci in range(4, len(header_cols)):
        h = header_cols[ci].strip()
        if not h:
            continue
        m = WIDE_ELEMENT_COL_RE.match(h)
        if m:
            elem_headers.append((ci, m.group(1), m.group(2), m.group(3)))
        else:
            elem_headers.append((ci, h, "", ""))

    header_unit_for_col = {}
    for ci, *_ in elem_headers:
        header_unit_for_col[ci] = unit_cols[ci].strip() if ci < len(unit_cols) else ""

    current_sample: Optional[str] = None

    for li in range(unit_idx + 1, len(raw_lines)):
        line = raw_lines[li]
        if not line.strip() or line.strip().startswith("#"):
            continue
        cols = line.split("\t")
        if len(cols) < 5:
            pr.review_items.append(
                ReviewItem(line=li + 1, text=line, reason="Too few tab-separated columns for the wide layout")
            )
            continue

        type_, name, mdate, vtype = (
            cols[0].strip(), cols[1].strip(), cols[2].strip(), cols[3].strip()
        )

        if name:
            current_sample = name
            meta = pr.samples.setdefault(current_sample, SampleMeta(sample_id=current_sample))
            if type_:
                meta.metadata["Type"] = type_
            if mdate:
                meta.metadata["Measurement Date"] = mdate

        if current_sample is None:
            pr.review_items.append(
                ReviewItem(line=li + 1, text=line, reason="No sample name seen yet — no sample context")
            )
            continue

        value_type_label = vtype if vtype else "Unknown"
        if re.match(r"^\d+$", value_type_label):
            value_type_label = f"Replicate {value_type_label}"

        any_value = False
        for ci, elem, wl, ctype in elem_headers:
            if ci >= len(cols):
                continue
            val = cols[ci].strip()
            if val == "":
                continue
            any_value = True
            unit = extract_unit_suffix(val) or header_unit_for_col.get(ci, "")
            rec = ResultRecord(
                sample_id=current_sample,
                element=elem,
                wavelength=wl,
                channel_type=ctype,
                result=val,
                unit=unit,
                value_type=value_type_label,
                qualifier=extract_qualifier(val),
                numeric_value=extract_numeric(val),
                source_line=li + 1,
                source_text=line,
                layout="wide",
                confidence="confident",
            )
            pr.records.append(rec)
            pr.samples[current_sample].source_lines.append(li + 1)

        if not any_value:
            pr.review_items.append(
                ReviewItem(line=li + 1, text=line, reason=f"Row labelled '{value_type_label}' had no values in any element column")
            )

    return pr


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def parse(text: str, forced_layout: Optional[str] = None) -> ParseResult:
    """Parse raw pasted/uploaded ICP text. Auto-detects layout unless
    forced_layout is 'block' or 'wide'."""
    if text is None:
        text = ""
    layout = forced_layout or classify_layout(text)
    if layout == "wide":
        result = parse_wide(text)
    else:
        result = parse_block(text)
    result.raw_text = text
    return result
