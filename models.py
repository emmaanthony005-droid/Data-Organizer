"""
models.py
Data structures for the ICP Results Organizer.

DATA INTEGRITY RULE (non-negotiable):
`result` always holds the EXACT substring found in the raw input (or the
exact cell value from an uploaded table). It is never rounded, truncated,
reformatted, or unit-converted. `numeric_value` is a best-effort derived
number used ONLY for sorting/analytics and must never be displayed in place
of `result`.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ResultRecord:
    sample_id: str
    element: str
    result: str                     # EXACT raw text of the value — never altered
    unit: str = ""                  # best-effort, cosmetic only
    wavelength: str = ""            # wide/wavelength layout only, e.g. "189.042"
    channel_type: str = ""          # e.g. "A" (analyte) / "M" (internal std/monitor)
    value_type: str = "Result"      # "Result" (block layout) or "Reported"/"Mean"/
                                     # "SD"/"RSD"/"Replicate 1"/"Min Calibration Range"/... (wide layout)
    qualifier: str = ""             # '<' '>' '≤' '≥' '«»' 'ND' 'N.D.' if detected — cosmetic tag only
    numeric_value: Optional[float] = None   # derived, sorting/analytics ONLY
    source_line: int = 0
    source_text: str = ""
    layout: str = "block"           # "block" | "wide"
    confidence: str = "confident"   # "confident" | "review"
    review_reason: str = ""

    @property
    def is_reportable(self) -> bool:
        """True for the row(s) that represent the lab's quoted/reported value
        for this sample+element (as opposed to raw replicates, Mean/SD/RSD,
        or calibration-range QC rows in the wide layout)."""
        if self.layout == "block":
            return True
        return self.value_type == "Reported"


@dataclass
class SampleMeta:
    sample_id: str
    metadata: Dict[str, str] = field(default_factory=dict)
    source_lines: List[int] = field(default_factory=list)


@dataclass
class ReviewItem:
    line: int
    text: str
    reason: str


@dataclass
class ParseResult:
    raw_text: str
    layout_detected: str
    records: List[ResultRecord] = field(default_factory=list)
    samples: Dict[str, SampleMeta] = field(default_factory=dict)
    review_items: List[ReviewItem] = field(default_factory=list)

    def stats(self) -> Dict[str, int]:
        elements = {r.element for r in self.records}
        reported = [r for r in self.records if r.is_reportable]
        return {
            "samples": len(self.samples),
            "elements": len(elements),
            "results": len(reported),
            "all_records": len(self.records),
            "needs_review": len(self.review_items),
        }
