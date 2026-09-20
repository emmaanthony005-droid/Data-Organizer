"""
exporter.py - turns a ParseResult into export-ready artifacts.
Every exported value is the exact `result` string.
"""
import io
import pandas as pd
from models import ParseResult


def organized_dataframe(pr: ParseResult, reported_only: bool = True) -> pd.DataFrame:
    rows = []
    for r in pr.records:
        if reported_only and not r.is_reportable:
            continue
        row = {"Sample": r.sample_id, "Element": r.element}
        if r.layout == "wide":
            row["Wavelength"] = r.wavelength
            row["Channel"] = r.channel_type
            row["Value Type"] = r.value_type
        row["Result"] = r.result
        row["Unit"] = r.unit
        row["Qualifier"] = r.qualifier
        row["Source Line"] = r.source_line
        rows.append(row)
    return pd.DataFrame(rows)


def pivot_dataframe(pr: ParseResult, reported_only: bool = True) -> pd.DataFrame:
    recs = [r for r in pr.records if (r.is_reportable if reported_only else True)]
    if not recs:
        return pd.DataFrame()

    elem_wavelengths = {}
    for r in recs:
        elem_wavelengths.setdefault(r.element, set()).add(r.wavelength)

    def col_label(r):
        if len(elem_wavelengths.get(r.element, set())) > 1 and r.wavelength:
            return f"{r.element} {r.wavelength}"
        return r.element

    col_units = {}
    for r in recs:
        c = col_label(r)
        col_units.setdefault(c, set()).add(r.unit)

    def col_header(c):
        units = col_units.get(c, set())
        if len(units) == 1:
            u = next(iter(units))
            if u:
                return f"{c} ({u})"
        return c

    rows = {}
    for r in recs:
        c = col_header(col_label(r))
        rows.setdefault(r.sample_id, {})[c] = r.result

    df = pd.DataFrame.from_dict(rows, orient="index")
    df.index.name = "Sample"
    df = df.reindex(sorted(df.columns), axis=1)
    df = df.sort_index()
    df = df.fillna("")
    return df.reset_index()


def review_dataframe(pr: ParseResult) -> pd.DataFrame:
    return pd.DataFrame(
        [{"Line": rv.line, "Text": rv.text, "Reason": rv.reason} for rv in pr.review_items]
    )


def samples_dataframe(pr: ParseResult) -> pd.DataFrame:
    rows = []
    for sid, meta in pr.samples.items():
        row = {"Sample": sid, "Result Count": len(meta.source_lines)}
        row.update(meta.metadata)
        rows.append(row)
    return pd.DataFrame(rows)


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")


def to_clipboard_text(df: pd.DataFrame) -> str:
    return df.to_csv(sep="\t", index=False)


def to_excel_bytes(pr: ParseResult) -> bytes:
    buf = io.BytesIO()
    organized = organized_dataframe(pr, reported_only=True)
    all_records = organized_dataframe(pr, reported_only=False)
    samples = samples_dataframe(pr)
    review = review_dataframe(pr)

    stats = pr.stats()
    summary = pd.DataFrame(
        [{"Metric": k.replace("_", " ").title(), "Value": v} for k, v in stats.items()]
    )

    elements_rows = []
    for elem in sorted({r.element for r in pr.records}):
        recs = [r for r in pr.records if r.element == elem and r.is_reportable]
        elements_rows.append({
            "Element": elem,
            "Result Count": len(recs),
            "Samples": len({r.sample_id for r in recs}),
        })
    elements_df = pd.DataFrame(elements_rows)

    log_rows = [
        {"Line": r.source_line, "Sample": r.sample_id, "Element": r.element,
         "Value Type": r.value_type, "Result": r.result, "Status": "Organized"}
        for r in pr.records
    ] + [
        {"Line": rv.line, "Sample": "", "Element": "", "Value Type": "",
         "Result": rv.text, "Status": f"Review: {rv.reason}"}
        for rv in pr.review_items
    ]
    log_df = (
        pd.DataFrame(log_rows).sort_values("Line")
        if log_rows
        else pd.DataFrame(columns=["Line", "Sample", "Element", "Value Type", "Result", "Status"])
    )

    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Summary", index=False)
        organized.to_excel(writer, sheet_name="Organized Results", index=False)
        samples.to_excel(writer, sheet_name="Samples", index=False)
        elements_df.to_excel(writer, sheet_name="Elements", index=False)
        review.to_excel(writer, sheet_name="Data Quality - Review", index=False)
        log_df.to_excel(writer, sheet_name="Processing Log", index=False)
        if pr.layout_detected == "wide":
            all_records.to_excel(writer, sheet_name="All Value Types (QC)", index=False)

    buf.seek(0)
    return buf.read()
