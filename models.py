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
    result: str                     # EXACT raw text of the value
    unit: str = ""
    wavelength: str = ""
    channel_type: str = ""
    value_type: str = "Result"
    qualifier: str = ""
    numeric_value: Optional[float] = None
    source_line: int = 0
    source_text: str = ""
    layout: str = "block"
    confidence: str = "confident"
    review_reason: str = ""

    @property
    def is_reportable(self) -> bool:
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
