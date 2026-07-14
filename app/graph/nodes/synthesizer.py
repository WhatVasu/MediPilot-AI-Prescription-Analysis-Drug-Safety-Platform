"""
[5] Report Synthesizer

Turns enriched_drugs into UI-ready MedicineCards. The only LLM involvement is
a short, grounded "what this medicine is generally used for" rewrite — it is
given the FDA label's own indications text as context and told to summarize
it, not to answer from memory. Side effects and dosage text are passed
through verbatim from the sourced data, never regenerated.
"""
import logging

from langchain_core.messages import HumanMessage

from app.clients.llm_client import get_chat_model
from app.clients.openfda_client import OpenFDAClient
from app.graph.state import MediScanState
from app.schemas.enrichment import EnrichedDrug
from app.schemas.report import FinalReport, MedicineCard

logger = logging.getLogger(__name__)

_openfda = OpenFDAClient()

SUMMARY_PROMPT = """Below is the official FDA label text describing what a medicine is
used for. Summarize it in one plain-language sentence a non-medical person can
understand. Do NOT add any information that isn't in the text below. If the text is
empty or unhelpful, reply with exactly: UNKNOWN

Label text:
{indications_text}"""


def _summarize_indication(canonical_name: str | None) -> str | None:
    if not canonical_name:
        return None
    label = _openfda.get_label(canonical_name)
    if not label:
        return None
    indications = label.get("indications_and_usage")
    if not indications:
        return None

    first_indication = indications[0] if isinstance(indications, list) and indications else None
    if not first_indication:
        return None

    try:
        model = get_chat_model()
        prompt = SUMMARY_PROMPT.format(indications_text=first_indication[:1500])
        response = model.invoke([HumanMessage(content=prompt)])
        summary = (response.content or "").strip()
    except Exception:
        logger.exception("Failed to summarize indication for %r", canonical_name)
        return None

    return None if summary == "UNKNOWN" else summary


def _to_card(drug: EnrichedDrug) -> MedicineCard:
    # canonical_name can legitimately be None (unresolved drug name) — fall
    # back to the raw OCR text so the card always has something to display
    # instead of failing MedicineCard's required `display_name` field.
    display_name = drug.canonical_name or drug.raw_name or "Unknown medicine"

    return MedicineCard(
        display_name=display_name,
        raw_text=drug.raw_name,
        package_image_url=drug.package_image_url,
        what_its_for=_summarize_indication(drug.canonical_name),
        dosage=drug.dosage.model_dump(),
        side_effects=drug.safety.side_effects,
        safety_source=drug.safety.source,
        generic_alternatives=drug.generic_alternatives,
        purchase_links=drug.purchase_links.model_dump() if drug.purchase_links else None,
        needs_verification=drug.needs_verification,
        verification_reason=drug.verification_reason,
    )


def _fallback_card(drug: EnrichedDrug) -> MedicineCard:
    """Used when building a full card fails for one drug — still show
    *something* for it rather than dropping it or failing the whole report."""
    return MedicineCard(
        display_name=drug.raw_name or "Unknown medicine",
        raw_text=drug.raw_name or "",
        package_image_url=None,
        what_its_for=None,
        dosage={},
        side_effects=[],
        safety_source=None,
        generic_alternatives=[],
        purchase_links=None,
        needs_verification=True,
        verification_reason="We couldn't fully process this medicine. Please check the original prescription.",
    )


def synthesizer_node(state: MediScanState) -> dict:
    cards = []
    for drug in state.get("enriched_drugs", []) or []:
        try:
            cards.append(_to_card(drug))
        except Exception:
            # Isolate per-drug failures — one bad card should not wipe out
            # the rest of an otherwise-successful report.
            logger.exception("Failed to build card for %r", getattr(drug, "raw_name", None))
            try:
                cards.append(_fallback_card(drug))
            except Exception:
                logger.exception("Failed to build fallback card as well; skipping this drug")

    report = FinalReport(cards=cards)
    return {"final_report": report.model_dump()}
