"""
demo_data.py
Two DEMO datasets, one per supported layout. All values are synthetic /
illustrative. Neither dataset is real laboratory data.
"""

DEMO_LABEL = "DEMO DATA \u2014 NOT REAL LABORATORY RESULTS"

# ---------------------------------------------------------------------------
# 1) BLOCK layout demo — this is the exact required Phase 1 test fixture,
#    with deliberately inconsistent spacing, mixed "Sample:"/"SAMPLE ID:"
#    headers, metadata mixed into a block, and a mixed table-style block.
# ---------------------------------------------------------------------------
DEMO_BLOCK = f"""# {DEMO_LABEL}
Sample: S001
Method: EPA 200.7          Date: 2024-03-11
Al      12.43   mg/kg
Fe    125.430   mg/kg
Cu       <0.01  mg/kg

Sample: S002
Al   15.20 mg/kg
Fe   98.210    mg/kg
Cu   0.14  mg/kg
Zn   ND    mg/kg

SAMPLE ID: S003
Element  Result   Unit
Al       9.876    mg/kg
Fe       76.320   mg/kg
Cu       «100»    mg/kg
"""

# ---------------------------------------------------------------------------
# 2) WIDE (wavelength-export) layout demo — mirrors the structure of a real
#    ICP-OES/ICP-MS "channel export" (Type / Name / Measurement Date /
#    Value Type, followed by Element+Wavelength(Channel) columns, a units
#    row, then per-sample blocks of Replicate 1-3, Min/Max Calibration
#    Range, Reported, Mean, SD, RSD rows). Values below are synthetic.
# ---------------------------------------------------------------------------
_WIDE_HEADER = (
    "Type\tName\tMeasurement Date\tValue Type\t"
    "As 189.042 (A)\tCu 324.754 (A)\tCd 214.438 (A)\tPb 220.353 (A)\t"
    "Zn 213.856 (A)\tCr 267.716 (A)\tAr 404.442 (M)\t"
)
_WIDE_UNITS = (
    "\t\t\t\tConc in ppm\tConc in ppm\tConc in ppm\tConc in ppm\t"
    "Conc in ppm\tConc in ppm\tConc in -\t"
)


def _demo_wide_block(name: str, date: str, base) -> str:
    reps = [
        [round(v * f, 3) for v in base] for f in (1.00, 0.99, 1.01)
    ]
    mean = [round(sum(col) / 3, 3) for col in zip(*reps)]
    lines = []
    for i, rep in enumerate(reps, start=1):
        row_name = name if i == 1 else ""
        row_date = date if i == 1 else ""
        row_type = "Unknown" if i == 1 else ""
        vals = "\t".join(str(v) for v in rep) + "\t{:.3f}E06 cps".format(4.2 + i * 0.01)
        lines.append(f"{row_type}\t{row_name}\t{row_date}\t{i}\t{vals}\t")
    min_cal = "\t".join(["0.005"] * len(base)) + "\t--\t"
    lines.append(f"\t\t\t{'Min Calibration Range'}\t{min_cal}")
    reported_vals = "\t".join(str(v) for v in mean) + "\t72.5 %\t"
    lines.append(f"\t\t\tReported\t{reported_vals}")
    max_cal = "\t".join(["360"] * len(base)) + "\t--\t"
    lines.append(f"\t\t\tMax Calibration Range\t{max_cal}")
    mean_vals = "\t".join(str(v) for v in mean) + "\t4.25E06 cps\t"
    lines.append(f"\t\t\tMean\t{mean_vals}")
    sd_vals = "\t".join([f"{v*0.01:.4f}" for v in mean]) + "\t5500 cps\t"
    lines.append(f"\t\t\tSD\t{sd_vals}")
    rsd_vals = "\t".join([f"{1.0:.2f} %" for _ in mean]) + "\t1.00 %\t"
    lines.append(f"\t\t\tRSD\t{rsd_vals}")
    return "\n".join(lines)


DEMO_WIDE = (
    f"# {DEMO_LABEL}\n"
    + _WIDE_HEADER + "\n"
    + _WIDE_UNITS + "\n\n"
    + _demo_wide_block("DEMO-01", "1/1/2026 9:00:00 AM", [6.09, 4.25, 3.22, 6.38, 10.90, 6.48])
    + "\n\n"
    + _demo_wide_block("DEMO-02", "1/1/2026 9:15:00 AM", [7.26, 6.94, 3.38, 8.02, 9.11, 11.40])
    + "\n"
)
