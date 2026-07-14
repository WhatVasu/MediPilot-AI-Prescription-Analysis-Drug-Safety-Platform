"""
The full LangGraph state for the MediScan+ pipeline.

Keep this flat and serializable — every node reads/writes a slice of this dict.
`enriched_drugs` uses an `operator.add` reducer because node [4] runs as one
parallel branch per drug (via LangGraph's Send API) — each branch returns a
single-item list, and the reducer concatenates them back into one list
instead of the later branches overwriting the earlier ones.
"""
import operator
from typing import Annotated, TypedDict

from app.schemas.enrichment import EnrichedDrug
from app.schemas.normalization import NormalizedDrug
from app.schemas.ocr import ParsedDrug


class MediScanState(TypedDict, total=False):
    # input
    image_path: str

    # [1] OCR & Parse Agent
    raw_ocr_text: str
    parsed_drugs: list[ParsedDrug]

    # [2] Drug Name Normalization Agent + [3] Confidence Check
    normalized_drugs: list[NormalizedDrug]

    # [4] Per-Drug Enrichment — fan-out/fan-in, hence the reducer
    enriched_drugs: Annotated[list[EnrichedDrug], operator.add]

    # [5] Report Synthesizer
    final_report: dict


class EnrichDrugState(TypedDict):
    """Sub-state passed to each parallel enrichment branch via Send() — just one drug, not the whole pipeline."""

    drug: NormalizedDrug

