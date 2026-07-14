"""
[4] Per-Drug Enrichment — entry point for one parallel Send() branch.

Design note: the fan-out happens at the *drug* level (via LangGraph's Send
API — see route_to_enrichment() in builder.py), so N drugs on a prescription
become N parallel graph branches. Within each branch, the four sub-lookups
(dosage, side effects, generics, e-commerce links) are independent I/O calls,
so they run concurrently via threads rather than as four more graph nodes —
simpler to build and debug than nested fan-out, while still being real
parallelism where it matters (the per-drug branching, and the network calls).
"""
import logging
from concurrent.futures import ThreadPoolExecutor

from app.graph.nodes.enrichment.dosage import lookup_dosage
from app.graph.nodes.enrichment.ecommerce_links import build_ecommerce_links
from app.graph.nodes.enrichment.generics import lookup_generics
from app.graph.nodes.enrichment.side_effects import lookup_side_effects
from app.graph.state import EnrichDrugState
from app.schemas.enrichment import EnrichedDrug, DosageInfo, SafetyInfo
from app.clients.openmed import get_drug_image_from_rxcui

logger = logging.getLogger(__name__)


def _safe_result(future, label: str):
    try:
        return future.result()
    except Exception:
        logger.warning("Enrichment sub-lookup %r failed", label, exc_info=True)
        return None


def enrich_drug_node(state: EnrichDrugState) -> dict:
    drug = state["drug"]

    try:
        with ThreadPoolExecutor(max_workers=5) as pool:
            image_future = pool.submit(get_drug_image_from_rxcui, drug.rxcui)
            dosage_future = pool.submit(lookup_dosage, drug)
            safety_future = pool.submit(lookup_side_effects, drug)
            generics_future = pool.submit(lookup_generics, drug)
            links_future = pool.submit(build_ecommerce_links, drug)

            package_image_url = _safe_result(image_future, "package_image")
            dosage = _safe_result(dosage_future, "dosage") or DosageInfo(
                as_written=drug.dosage_as_written,
                frequency_as_written=drug.frequency_as_written,
            )
            safety = _safe_result(safety_future, "side_effects") or SafetyInfo()
            generics = _safe_result(generics_future, "generics") or []
            links = _safe_result(links_future, "ecommerce_links")

        enriched = EnrichedDrug(
            raw_name=drug.raw_name,
            canonical_name=drug.canonical_name,
            rxcui=drug.rxcui,
            package_image_url=package_image_url,
            needs_verification=drug.needs_verification,
            verification_reason=drug.verification_reason,
            dosage=dosage,
            safety=safety,
            generic_alternatives=generics,
            purchase_links=links,
        )
    except Exception:
        # This branch runs concurrently with the others (LangGraph Send
        # fan-out) — an unhandled exception here would propagate up through
        # graph.invoke() and blank out every other drug's results too.
        # Isolate it: this drug just gets a minimal, flagged-for-review card.
        logger.exception("Enrichment failed entirely for drug %r; falling back to minimal card", drug.raw_name)
        enriched = EnrichedDrug(
            raw_name=drug.raw_name,
            canonical_name=drug.canonical_name,
            rxcui=drug.rxcui,
            package_image_url=None,
            needs_verification=True,
            verification_reason="We couldn't fully enrich this medicine's details. Please check the original prescription.",
            dosage=DosageInfo(
                as_written=drug.dosage_as_written,
                frequency_as_written=drug.frequency_as_written,
            ),
            safety=SafetyInfo(),
            generic_alternatives=[],
            purchase_links=None,
        )

    # single-item list — this branch's contribution, merged by the
    # `operator.add` reducer on MediScanState.enriched_drugs
    return {"enriched_drugs": [enriched]}
