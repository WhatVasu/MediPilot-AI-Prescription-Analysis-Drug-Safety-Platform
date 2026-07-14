import logging
import os
import sys
import tempfile
from pathlib import Path

from flask import Flask, render_template, request

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

from app.graph.builder import build_graph
from app.schemas.report import DOSAGE_DISCLAIMER, STANDARD_DISCLAIMER
from app.sample_report import SAMPLE_REPORT

app = Flask(
    __name__,
    template_folder=str(PROJECT_ROOT / "templates"),
    static_folder=str(PROJECT_ROOT / "static"),
)

_graph = build_graph()

_ALLOWED_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
}

# Prevents a single huge upload from exhausting memory.
_MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MB
app.config["MAX_CONTENT_LENGTH"] = _MAX_UPLOAD_BYTES

_DEFAULT_DISCLAIMERS = [STANDARD_DISCLAIMER, DOSAGE_DISCLAIMER]


def _card_completeness(card: dict) -> tuple[int, int]:
    """How many of the 'nice to have' fields are populated for this card,
    out of the max possible. Used purely for display ordering — every card
    is shown regardless of score."""
    dosage = card.get("dosage") or {}
    fields = [
        bool(card.get("package_image_url")),
        bool(card.get("what_its_for")),
        bool(dosage.get("general_reference")),
        bool(card.get("side_effects")),
        bool(card.get("generic_alternatives")),
        bool(card.get("purchase_links")),
    ]
    return sum(fields), len(fields)


def _prepare_report(report: dict | None) -> dict | None:
    if not report or not report.get("cards"):
        return report
    scored = []
    for card in report["cards"]:
        score, max_score = _card_completeness(card)
        card = dict(card)
        card["_score"] = score
        card["_max_score"] = max_score
        scored.append(card)
    scored.sort(key=lambda c: c["_score"], reverse=True)
    report = dict(report)
    report["cards"] = scored
    return report


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def index():
    return render_template("index.html", report=None, error=None)


@app.get("/sample")
def sample():
    return render_template("index.html", report=_prepare_report(SAMPLE_REPORT), error=None, is_sample=True)


@app.post("/analyze")
def analyze_prescription():
    file = request.files.get("file")
    if file is None or file.filename == "":
        return render_template("index.html", report=None, error="Choose a prescription photo first.")

    suffix = _ALLOWED_CONTENT_TYPES.get(file.mimetype)
    if suffix is None:
        return render_template("index.html", report=None, error="Upload a JPEG or PNG image.")

    tmp_path = None
    try:
        try:
            contents = file.read()
        except Exception:
            logger.exception("Failed to read uploaded file")
            return render_template("index.html", report=None, error="Could not read the uploaded file.")

        if not contents:
            return render_template("index.html", report=None, error="Uploaded file is empty.")
        if len(contents) > _MAX_UPLOAD_BYTES:
            return render_template(
                "index.html",
                report=None,
                error=f"Uploaded file is too large (max {_MAX_UPLOAD_BYTES // (1024 * 1024)}MB).",
            )

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(contents)
                tmp_path = tmp.name
        except OSError:
            logger.exception("Failed to write uploaded file to a temp path")
            return render_template("index.html", report=None, error="Server could not process the uploaded file.")

        try:
            result = _graph.invoke({"image_path": tmp_path})
        except Exception:
            logger.exception("Pipeline failed for uploaded prescription")
            report = {
                "cards": [],
                "disclaimers": _DEFAULT_DISCLAIMERS,
                "status": "partial",
                "warning": "We couldn't fully analyze this prescription. Please try again or use a clearer photo.",
            }
            return render_template("index.html", report=_prepare_report(report), error=None)

        report = result.get("final_report") if isinstance(result, dict) else None
        if not isinstance(report, dict):
            report = {"cards": [], "disclaimers": _DEFAULT_DISCLAIMERS}

        report.setdefault("disclaimers", _DEFAULT_DISCLAIMERS)
        report.setdefault("warning", None)
        if not report.get("cards"):
            report.setdefault("status", "no_medicines_found")
            if not report.get("warning"):
                report["warning"] = "We couldn't identify any medicines in this photo. Try a clearer, well-lit image."
        else:
            report.setdefault("status", "complete")

        return render_template("index.html", report=_prepare_report(report), error=None)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8000)), debug=False)
