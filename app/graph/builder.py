"""
Builds the full MediScan+ LangGraph.

Pipeline: OCR -> normalize -> confidence check -> [fan out one branch per
drug] -> enrich_drug -> [fan back in] -> synthesizer -> END.

The fan-out uses LangGraph's Send API: route_to_enrichment() returns one
Send("enrich_drug", {...}) per normalized drug, so a 3-medicine prescription
runs 3 parallel enrichment branches. Each branch writes a single-item list to
enriched_drugs; the operator.add reducer on MediScanState concatenates them
back together before synthesizer_node runs.
"""
from langgraph.graph import END, StateGraph
from langgraph.types import Send

from app.graph.nodes.confidence_check import confidence_check_node
from app.graph.nodes.enrich_drug import enrich_drug_node
from app.graph.nodes.normalize import normalize_node
from app.graph.nodes.ocr_parse import ocr_parse_node
from app.graph.nodes.synthesizer import synthesizer_node
from app.graph.state import MediScanState


def route_to_enrichment(state: MediScanState):
    """
    Conditional edge that fans out from confidence_check into one parallel
    enrich_drug branch per normalized drug. Drugs flagged needs_verification
    still get enriched (a low-confidence match may still be correct) — the
    flag travels with the drug and is shown on its card regardless.

    If no drugs were found (blank/unreadable prescription), there's nothing
    to fan out to. Send()-based fan-out only triggers downstream nodes that
    are reached via its own branches, so returning an empty list here would
    mean synthesizer_node (only otherwise reachable via the enrich_drug ->
    synthesizer edge) never runs and `final_report` is never set. Routing
    directly to "synthesizer" in that case keeps the pipeline output shape
    consistent (an empty-but-valid report) instead of relying on the API
    layer's fallback.
    """
    normalized_drugs = state.get("normalized_drugs") or []
    if not normalized_drugs:
        return ["synthesizer"]
    return [Send("enrich_drug", {"drug": drug}) for drug in normalized_drugs]


def build_graph():
    graph = StateGraph(MediScanState)

    graph.add_node("ocr_parse", ocr_parse_node)
    graph.add_node("normalize", normalize_node)
    graph.add_node("confidence_check", confidence_check_node)
    graph.add_node("enrich_drug", enrich_drug_node)
    graph.add_node("synthesizer", synthesizer_node)

    graph.set_entry_point("ocr_parse")
    graph.add_edge("ocr_parse", "normalize")
    graph.add_edge("normalize", "confidence_check")

    graph.add_conditional_edges("confidence_check", route_to_enrichment, ["enrich_drug", "synthesizer"])
    graph.add_edge("enrich_drug", "synthesizer")
    graph.add_edge("synthesizer", END)

    return graph.compile()
