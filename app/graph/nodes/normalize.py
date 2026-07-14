"""
[2] Drug Name Normalization Agent

Resolves each raw OCR'd drug name to a real medicine via RxNorm's
approximateTerm endpoint, after an LLM pass that corrects obvious OCR
misspellings or surfaces generic composition (never hallucinated — see
app.services.drug_name_resolver). This node is the reason the rest of the
pipeline works: every later lookup (side effects, generics, e-commerce
links) keys off canonical_name/rxcui, not the raw OCR guess.
"""
import logging

from app.clients.rxnorm_client import RxNormClient
from app.graph.state import MediScanState
from app.schemas.normalization import NormalizedDrug
from app.services.drug_name_resolver import resolve_drug_name

logger = logging.getLogger(__name__)

_rxnorm = RxNormClient()


def normalize_node(state: MediScanState) -> dict:
    normalized: list[NormalizedDrug] = []

    for drug in state.get("parsed_drugs", []) or []:
        try:
            normalized.append(_normalize_single_drug(drug))
        except Exception:
            # Isolated per-drug failure — don't discard the rest of the
            # prescription because one entry blew up.
            logger.exception("Normalization failed for drug %r; using raw name only", getattr(drug, "raw_name", None))
            normalized.append(
                NormalizedDrug(
                    raw_name=drug.raw_name,
                    dosage_as_written=drug.dosage_as_written,
                    frequency_as_written=drug.frequency_as_written,
                    ocr_confidence=drug.ocr_confidence,
                    canonical_name=None,
                    rxcui=None,
                    match_confidence=0.0,
                )
            )

    return {"normalized_drugs": normalized}


def _normalize_single_drug(drug) -> NormalizedDrug:
    resolution = resolve_drug_name(drug.raw_name)

    # Try the LLM's corrected name first, then its generic name, then fall
    # back to the raw OCR string — first one that yields candidates wins.
    search_terms = [
        term
        for term in (resolution.corrected_name, resolution.generic_name, drug.raw_name)
        if term
    ]

    candidates: list[dict] = []
    for term in search_terms:
        try:
            candidates = _rxnorm.approximate_term(term)
        except Exception:
            candidates = []
        if candidates:
            break

    top = candidates[0] if candidates else None

    return NormalizedDrug(
        raw_name=drug.raw_name,
        dosage_as_written=drug.dosage_as_written,
        frequency_as_written=drug.frequency_as_written,
        ocr_confidence=drug.ocr_confidence,
        canonical_name=top.get("name") if top else None,
        rxcui=top.get("rxcui") if top else None,
        match_confidence=top.get("score", 0.0) if top else 0.0,
        llm_corrected_name=resolution.corrected_name,
        llm_generic_name=resolution.generic_name,
    )