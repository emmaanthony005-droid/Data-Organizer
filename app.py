"""
app.py — ICP Results Organizer (Streamlit UI)

Single continuous page, matching the original workflow: paste/upload -> click
"Organize Results" -> quick preview -> confirm -> Excel-style results grid,
with the other views (Samples, Elements, Search, Data Quality, Analytics,
Comparison, Export) as tabs right below the grid — no sidebar page-hopping.

Data integrity: this file never touches `result` strings — it only ever
displays them, sorts/filters using the pre-derived `numeric_value`, and
hands the exact text to exporter.py unchanged.
"""
import streamlit as st
import pandas as pd

from parser import parse
from demo_data import DEMO_BLOCK, DEMO_WIDE, DEMO_LABEL
from file_input import extract_text
from exporter import (
    organized_dataframe, pivot_dataframe, review_dataframe, samples_dataframe,
    to_csv_bytes, to_clipboard_text, to_excel_bytes,
)

st.set_page_config(page_title="ICP Results Organizer", layout="wide")

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
defaults = {
    "raw_text": "",
    "pr": None,
    "confirmed": False,
    "forced_layout": "Auto-detect",
}
for k, v in defaults.items():
    st.session_state.setdefault(k, v)

LAYOUT_OPTIONS = [
    "Auto-detect",
    "Block-style (Sample: ... / Element Result Unit)",
    "Wide wavelength-export (tab-separated)",
]


def reset_all():
    st.session_state.raw_text = ""
    st.session_state.pr = None
    st.session_state.confirmed = False


# ---------------------------------------------------------------------------
# Sidebar: identity + dataset status only (NOT page navigation)
# ---------------------------------------------------------------------------
st.sidebar.title("🧪 ICP Results Organizer")
st.sidebar.caption("Paste → Organize → Review → Export. Everything happens on one page.")
if st.session_state.pr is not None:
    stats = st.session_state.pr.stats()
    st.sidebar.markdown("---")
    st.sidebar.caption("Current dataset")
    st.sidebar.write(f"Samples: **{stats['samples']}**")
    st.sidebar.write(f"Elements: **{stats['elements']}**")
    st.sidebar.write(f"Results: **{stats['results']}**")
    st.sidebar.write(f"Needs review: **{stats['needs_review']}**")
    st.sidebar.markdown("---")
    if st.sidebar.button("🗑️ New Analysis (clear everything)"):
        st.session_state["_confirm_clear"] = True
    if st.session_state.get("_confirm_clear"):
        st.sidebar.warning("This clears the current data. Are you sure?")
        c1, c2 = st.sidebar.columns(2)
        if c1.button("Yes, clear"):
            reset_all()
            st.session_state["_confirm_clear"] = False
            st.rerun()
        if c2.button("Cancel"):
            st.session_state["_confirm_clear"] = False

st.title("ICP Results Organizer")

# ===========================================================================
# STEP 1 — Import
# ===========================================================================
st.header("1. Paste or upload raw results")

tab_paste, tab_upload = st.tabs(["📋 Paste text", "📁 Upload file"])

with tab_paste:
    c1, c2, c3 = st.columns(3)
    if c1.button("Load block-style example"):
        st.session_state.raw_text = DEMO_BLOCK
    if c2.button("Load wide/wavelength-export example"):
        st.session_state.raw_text = DEMO_WIDE
    if c3.button("Clear text"):
        st.session_state.raw_text = ""

    st.session_state.raw_text = st.text_area(
        "Raw ICP results",
        value=st.session_state.raw_text,
        height=280,
        placeholder="Paste raw, messy ICP results here...",
        label_visibility="collapsed",
    )

with tab_upload:
    up = st.file_uploader(
        "Upload a .txt, .csv, .xlsx, .xls, .pdf, .jpg, .jpeg, or .png file",
        type=["txt", "csv", "xlsx", "xls", "pdf", "jpg", "jpeg", "png"],
    )
    if up is not None:
        try:
            text, method = extract_text(up.name, up.read())
            st.success(f"Read '{up.name}' via {method}.")
            if "OCR" in method:
                st.warning(
                    "OCR was used to read this file — double-check the numbers "
                    "against the original image before trusting them."
                )
            st.session_state.raw_text = text
            with st.expander("Preview extracted text"):
                st.text(text[:3000] + ("..." if len(text) > 3000 else ""))
        except ValueError as e:
            st.error(str(e))

lc, bc = st.columns([2, 1])
with lc:
    st.session_state.forced_layout = st.selectbox(
        "Layout", LAYOUT_OPTIONS, index=LAYOUT_OPTIONS.index(st.session_state.forced_layout)
    )
with bc:
    st.write("")
    organize_clicked = st.button(
        "🧮 Organize Results", type="primary", disabled=not st.session_state.raw_text.strip(),
        width="stretch",
    )

if organize_clicked:
    forced = None
    if st.session_state.forced_layout.startswith("Block"):
        forced = "block"
    elif st.session_state.forced_layout.startswith("Wide"):
        forced = "wide"
    st.session_state.pr = parse(st.session_state.raw_text, forced_layout=forced)
    st.session_state.confirmed = False

if st.session_state.raw_text:
    with st.expander("View Raw Input (always recoverable, unedited)"):
        st.text(st.session_state.raw_text)

pr = st.session_state.pr

# ===========================================================================
# STEP 2 — Parse preview (inline, right under Step 1 — not a separate page)
# ===========================================================================
if pr is not None:
    st.header("2. Parse preview")
    stats = pr.stats()
    st.write(f"Detected layout: **{pr.layout_detected}**")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Samples", stats["samples"])
    c2.metric("Elements", stats["elements"])
    c3.metric("Results", stats["results"])
    c4.metric("Total value rows", stats["all_records"])
    c5.metric("Needs review", stats["needs_review"])

    with st.expander("Field mapping the parser inferred", expanded=False):
        if pr.layout_detected == "wide":
            st.markdown(
                "- Columns 1-4: `Type`, `Name` (Sample ID), `Measurement Date`, `Value Type`\n"
                "- Remaining columns: `Element Symbol` `Wavelength` `(Channel)` — one column per analytical channel\n"
                "- Row `Value Type` = `Reported` is treated as the lab's quoted result; "
                "replicate/Mean/SD/RSD/Calibration-range rows are kept as QC detail, viewable under the Samples tab."
            )
        else:
            st.markdown(
                "- A line starting `Sample:` or `SAMPLE ID:` starts a new sample\n"
                "- `Key: Value` pairs on/after that line become sample metadata (Method, Date, Batch, ...)\n"
                "- A line shaped `<element token> <result token> [<unit token>]` becomes one result row"
            )

    if pr.review_items:
        with st.expander(f"⚠️ {len(pr.review_items)} line(s) need review", expanded=True):
            st.dataframe(review_dataframe(pr), width="stretch")
            st.caption(
                "These lines didn't confidently match a known pattern, so nothing was guessed. "
                "They're kept — see the Data Quality tab below — and never silently dropped."
            )

    if not st.session_state.confirmed:
        if st.button("✅ Confirm & Organize", type="primary"):
            st.session_state.confirmed = True
            st.rerun()
    else:
        st.success("Confirmed. Results are organized below.")

# ===========================================================================
# STEP 3 — Organized results (Excel-style grid) + tabs for everything else
# ===========================================================================
if pr is not None and st.session_state.confirmed:
    st.header("3. Organized results")

    grid = pivot_dataframe(pr, reported_only=True)

    with st.expander("Filters", expanded=False):
        fc = st.columns(3)
        sample_filter = fc[0].multiselect("Sample", list(grid["Sample"]) if not grid.empty else [])
        col_choices = [c for c in grid.columns if c != "Sample"]
        col_filter = fc[1].multiselect("Columns to show (element/channel)", col_choices)
        search_grid = fc[2].text_input("Quick filter (any text in the grid)")

    view = grid.copy()
    if sample_filter:
        view = view[view["Sample"].isin(sample_filter)]
    if col_filter:
        view = view[["Sample"] + col_filter]
    if search_grid:
        mask = view.apply(lambda row: search_grid.lower() in " ".join(str(v) for v in row.values).lower(), axis=1)
        view = view[mask]

    st.caption(
        "Samples as rows, elements/channels as columns — one screen, laid out like a spreadsheet. "
        "Every cell shows the exact reported text (units/qualifiers preserved); nothing here is rounded or rewritten."
    )
    st.dataframe(view, width="stretch", height=480, hide_index=True)

    tabs = st.tabs([
        "Samples", "Elements", "Search", "Data Quality",
        "Analytics", "Sample Comparison", "Export", "Help",
    ])

    # --- Samples -----------------------------------------------------------
    with tabs[0]:
        sample_ids = sorted(pr.samples.keys())
        if not sample_ids:
            st.warning("No samples detected.")
        else:
            chosen = st.selectbox("Choose a sample", sample_ids, key="samples_tab_select")
            meta = pr.samples[chosen]
            if meta.metadata:
                st.write("**Metadata:**", meta.metadata)
            df = organized_dataframe(pr, reported_only=True)
            st.subheader("Reported results")
            st.dataframe(df[df["Sample"] == chosen], width="stretch")
            if pr.layout_detected == "wide":
                with st.expander("Full QC detail (replicates, Mean, SD, RSD, calibration range)"):
                    qc_df = organized_dataframe(pr, reported_only=False)
                    st.dataframe(qc_df[qc_df["Sample"] == chosen], width="stretch", height=350)

    # --- Elements ------------------------------------------------------------
    with tabs[1]:
        df = organized_dataframe(pr, reported_only=True)
        elements = sorted(df["Element"].unique()) if not df.empty else []
        if not elements:
            st.warning("No elements detected.")
        else:
            chosen = st.selectbox("Choose an element", elements, key="elements_tab_select")
            st.dataframe(df[df["Element"] == chosen], width="stretch")

    # --- Search --------------------------------------------------------------
    with tabs[2]:
        q = st.text_input("Search sample ID, element, or any text (case-insensitive)", key="search_tab_q")
        df = organized_dataframe(pr, reported_only=True)
        if q:
            mask = df.apply(lambda row: q.lower() in " ".join(str(v) for v in row.values).lower(), axis=1)
            st.dataframe(df[mask], width="stretch")
        else:
            st.caption("Type to search across the organized results (list view).")
            st.dataframe(df, width="stretch")

    # --- Data Quality ----------------------------------------------------------
    with tabs[3]:
        stats = pr.stats()
        c1, c2, c3 = st.columns(3)
        c1.metric("✅ Organized", stats["results"])
        c2.metric("⚠️ Unprocessed / Review", stats["needs_review"])
        c3.metric("Total input lines touched", stats["all_records"] + stats["needs_review"])
        st.subheader("Unprocessed / Review")
        if pr.review_items:
            st.dataframe(review_dataframe(pr), width="stretch", height=350)
        else:
            st.success("Nothing needed review — every line was confidently organized.")
        st.subheader("Organized (list view)")
        st.dataframe(organized_dataframe(pr, reported_only=True), width="stretch", height=350)

    # --- Analytics -------------------------------------------------------------
    with tabs[4]:
        st.caption(
            "Computed on the internal numeric layer only — the 'Reported Result' column always shows "
            "the exact original text. ND and qualified (</>) values are EXCLUDED from these statistics "
            "(never treated as 0 or as the threshold value) and are called out separately below."
        )
        reported = [r for r in pr.records if r.is_reportable]
        elements = sorted({r.element for r in reported})
        chosen = st.selectbox("Element", elements, key="analytics_elem") if elements else None
        if chosen:
            recs = [r for r in reported if r.element == chosen]
            numeric = [r.numeric_value for r in recs if r.numeric_value is not None and not r.qualifier]
            excluded = [r for r in recs if r.numeric_value is None or r.qualifier]

            colA, colB = st.columns(2)
            with colA:
                st.write("**Reported Result (exact text)**")
                st.dataframe(
                    pd.DataFrame([{"Sample": r.sample_id, "Result": r.result, "Unit": r.unit} for r in recs]),
                    width="stretch",
                )
            with colB:
                st.write("**Summary statistics** (unqualified numeric values only)")
                if numeric:
                    s = pd.Series(numeric)
                    st.dataframe(pd.DataFrame({
                        "Count": [s.count()], "Min": [s.min()], "Max": [s.max()],
                        "Mean": [round(s.mean(), 6)], "Median": [s.median()],
                        "Std Dev": [round(s.std(), 6) if s.count() > 1 else 0.0],
                    }))
                else:
                    st.info("No unqualified numeric values available for this element.")
                if excluded:
                    st.write(f"**Excluded from stats** ({len(excluded)}): ND / qualified / non-numeric values")
                    st.dataframe(pd.DataFrame([
                        {"Sample": r.sample_id, "Result": r.result, "Reason": "ND/qualified or non-numeric"}
                        for r in excluded
                    ]))

            st.subheader("Highest / Lowest reported result")
            clean = [r for r in recs if r.numeric_value is not None and not r.qualifier]
            if clean:
                hi = max(clean, key=lambda r: r.numeric_value)
                lo = min(clean, key=lambda r: r.numeric_value)
                cc1, cc2 = st.columns(2)
                cc1.metric("Highest", hi.result, f"Sample {hi.sample_id}")
                cc2.metric("Lowest", lo.result, f"Sample {lo.sample_id}")
                st.caption("ND and </≥ qualified values are excluded from Highest/Lowest, never approximated.")
            else:
                st.info("No clean numeric values to rank for this element.")

            if numeric:
                chart_df = pd.DataFrame(
                    {"Sample": [r.sample_id for r in recs if r.numeric_value is not None and not r.qualifier],
                     "Value": numeric}
                ).set_index("Sample")
                st.bar_chart(chart_df)

    # --- Sample Comparison -----------------------------------------------------
    with tabs[5]:
        sample_ids = sorted(pr.samples.keys())
        chosen = st.multiselect("Choose samples to compare", sample_ids, default=sample_ids[:5], key="cmp_select")
        if chosen:
            reported = [r for r in pr.records if r.is_reportable and r.sample_id in chosen]
            df = pd.DataFrame([{"Element": r.element, "Sample": r.sample_id, "Result": r.result} for r in reported])
            if not df.empty:
                matrix = df.pivot_table(index="Element", columns="Sample", values="Result", aggfunc="first")
                st.dataframe(matrix, width="stretch", height=450)
            else:
                st.info("No results for the chosen samples.")
        else:
            st.caption("Pick two or more samples above.")

    # --- Export ------------------------------------------------------------------
    with tabs[6]:
        df = organized_dataframe(pr, reported_only=True)

        st.subheader("Copy to clipboard")
        st.caption("Select the box below and Ctrl/Cmd+C — pastes cleanly into Excel/Word/email.")
        st.text_area("Paste-ready (tab-separated, Excel-style grid)", to_clipboard_text(grid), height=200)

        st.subheader("Download")
        d1, d2 = st.columns(2)
        d1.download_button(
            "⬇️ Download CSV (exact values preserved)",
            data=to_csv_bytes(df),
            file_name="icp_organized_results.csv",
            mime="text/csv",
        )
        d2.download_button(
            "⬇️ Download Excel workbook (multi-sheet)",
            data=to_excel_bytes(pr),
            file_name="icp_organized_results.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        st.caption(
            "Excel workbook includes: Summary, Organized Results, Samples, Elements, "
            "Data Quality - Review, Processing Log" + (", and All Value Types (QC)" if pr.layout_detected == "wide" else "") + "."
        )

    # --- Help ------------------------------------------------------------------
    with tabs[7]:
        st.markdown(f"""
**{DEMO_LABEL}** appears on both example datasets — load one from Step 1 to try the app risk-free.

### How to use this app
1. Paste raw ICP results, or upload a `.txt`, `.csv`, `.xlsx`, `.pdf`, or image file, then click **Organize Results**.
2. Check the parse preview counts and confirm with **Confirm & Organize**.
3. Your results appear as an Excel-style grid (samples × elements). Use the tabs above for
   per-sample/per-element views, search, data-quality review, analytics, comparison, and export.

### What this app will never do
It will never round, truncate, drop trailing zeros, convert units, convert scientific notation,
replace ND with 0, strip qualifiers (`<`, `>`, `«»`), or guess a value it isn't confident about.
Anything ambiguous is flagged in Data Quality with its original text and line number instead.

### Supported layouts (auto-detected)
- **Block-style**: `Sample: S001` / `SAMPLE ID: S003` headers followed by stacked `Element Result Unit` lines.
- **Wide wavelength-export**: a tab-separated instrument export with `Type / Name / Measurement Date / Value Type`
  columns followed by `Element Wavelength (Channel)` columns, replicate rows, and Reported/Mean/SD/RSD/Calibration rows.
""")
