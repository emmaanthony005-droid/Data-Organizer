"""
app.py - Flask server for the ICP Results Organizer.

Serves the frontend and provides API endpoints for:
  - File upload and text extraction (PDF, images, Excel, CSV, TXT)
  - Parsing raw text into organized results
  - Exporting to CSV and multi-sheet Excel

Run with:
  python app.py
  python app.py --host 0.0.0.0 --port 5000
"""
import argparse
import io
import json

from flask import Flask, render_template, request, jsonify, send_file

from parser import parse
from file_input import extract_text
from exporter import (
    organized_dataframe,
    pivot_dataframe,
    samples_dataframe,
    review_dataframe,
    to_csv_bytes,
    to_excel_bytes,
)
from demo_data import DEMO_BLOCK, DEMO_WIDE

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB upload limit


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/upload", methods=["POST"])
def upload_file():
    """Accept a file upload, extract text, return it to the frontend."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "Empty filename"}), 400

    try:
        file_bytes = f.read()
        text, method = extract_text(f.filename, file_bytes)
        return jsonify({
            "text": text,
            "method": method,
            "filename": f.filename,
            "size": len(file_bytes),
        })
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Failed to process file: {str(e)}"}), 500


@app.route("/api/parse", methods=["POST"])
def parse_text():
    """Parse raw text and return the structured result as JSON."""
    data = request.get_json()
    if not data or "text" not in data:
        return jsonify({"error": "No text provided"}), 400

    text = data["text"]
    forced_layout = data.get("layout")
    if forced_layout == "auto":
        forced_layout = None

    pr = parse(text, forced_layout=forced_layout)
    stats = pr.stats()

    records = []
    for r in pr.records:
        records.append({
            "sampleId": r.sample_id,
            "element": r.element,
            "result": r.result,
            "unit": r.unit,
            "wavelength": r.wavelength,
            "channelType": r.channel_type,
            "valueType": r.value_type,
            "qualifier": r.qualifier,
            "numericValue": r.numeric_value,
            "sourceLine": r.source_line,
            "sourceText": r.source_text,
            "layout": r.layout,
            "confidence": r.confidence,
            "isReportable": r.is_reportable,
        })

    samples = {}
    for sid, meta in pr.samples.items():
        samples[sid] = {
            "sampleId": meta.sample_id,
            "metadata": meta.metadata,
            "sourceLines": meta.source_lines,
        }

    review_items = [
        {"line": rv.line, "text": rv.text, "reason": rv.reason}
        for rv in pr.review_items
    ]

    return jsonify({
        "layout": pr.layout_detected,
        "stats": stats,
        "records": records,
        "samples": samples,
        "reviewItems": review_items,
    })


@app.route("/api/export/csv", methods=["POST"])
def export_csv():
    """Parse and export as CSV."""
    data = request.get_json()
    pr = _parse_from_request(data)
    df = organized_dataframe(pr, reported_only=True)
    csv_bytes = to_csv_bytes(df)
    return send_file(
        io.BytesIO(csv_bytes),
        mimetype="text/csv",
        as_attachment=True,
        download_name="icp_organized_results.csv",
    )


@app.route("/api/export/excel", methods=["POST"])
def export_excel():
    """Parse and export as multi-sheet Excel workbook."""
    data = request.get_json()
    pr = _parse_from_request(data)
    excel_bytes = to_excel_bytes(pr)
    return send_file(
        io.BytesIO(excel_bytes),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="icp_organized_results.xlsx",
    )


@app.route("/api/demo/<layout>")
def demo_data(layout):
    """Return demo text for testing."""
    if layout == "block":
        return jsonify({"text": DEMO_BLOCK})
    elif layout == "wide":
        return jsonify({"text": DEMO_WIDE})
    return jsonify({"error": "Unknown layout"}), 404


def _parse_from_request(data):
    text = data.get("text", "")
    forced_layout = data.get("layout")
    if forced_layout == "auto":
        forced_layout = None
    return parse(text, forced_layout=forced_layout)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="ICP Results Organizer")
    ap.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    ap.add_argument("--port", type=int, default=5000, help="Port (default: 5000)")
    ap.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = ap.parse_args()

    print(f"\n  ICP Results Organizer")
    print(f"  Running at http://{args.host}:{args.port}")
    print(f"  Press Ctrl+C to stop\n")

    app.run(host=args.host, port=args.port, debug=args.debug)
