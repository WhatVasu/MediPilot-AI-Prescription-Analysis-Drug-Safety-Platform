"""
[4b] Side Effects / Safety

Grounded entirely in the FDA label via OpenFDA — never generated from LLM
memory. The label text itself is often a dense wall of legalese, so an LLM
call turns it into a short, scannable list of the side effects it actually
names. This is extraction, not authorship: the model is instructed to only
surface terms that are explicitly present in the label text it's given, and
if that extraction fails or comes back empty, the raw label paragraphs are
used as a fallback rather than showing nothing. If no label data exists for
a drug, this returns available=False rather than letting anything
downstream guess.
"""
import logging

from langchain_core.messages import HumanMessage

from app.clients.llm_client import get_chat_model
from app.clients.openfda_client import OpenFDAClient
from app.schemas.enrichment import SafetyInfo, SideEffectsExtraction
from app.schemas.normalization import NormalizedDrug

logger = logging.getLogger(__name__)

_openfda = OpenFDAClient()

# Label text blocks can be enormous (full paragraphs of legalese). Cap what
# gets sent to the LLM / used as a display fallback.
_MAX_BLOCK_CHARS = 600
_MAX_ITEMS = 10

_EXTRACTION_PROMPT = """Below is verbatim adverse-reactions text from an FDA drug label.

List the specific side effects / adverse reactions that are explicitly named in this text,
as short phrases (2-4 words each, e.g. "Nausea", "Dry mouth", "Elevated liver enzymes").

Rules:
- Only include something if it is explicitly stated in the text below. Do not add anything from general knowledge.
- Do not include dosage information, warnings headers, study names, or boilerplate like "see full prescribing information".
- Deduplicate near-identical items.
- If the text names no specific side effects, return an empty list.

Label text:
{text}
"""


def _extract_with_llm(raw_text: str) -> list[str]:
    try:
        model = get_chat_model().with_structured_output(SideEffectsExtraction)
        message = HumanMessage(content=_EXTRACTION_PROMPT.format(text=raw_text[:4000]))
        result: SideEffectsExtraction = model.invoke([message])
        items = getattr(result, "side_effects", None) or []
        # Extraction only — dedupe, strip, cap length. No new content added.
        seen, cleaned = set(), []
        for item in items:
            item = item.strip().strip(".")
            key = item.lower()
            if item and key not in seen:
                seen.add(key)
                cleaned.append(item)
        return cleaned[:_MAX_ITEMS]
    except Exception:
        logger.exception("Side-effect extraction failed; falling back to raw label text")
        return []


def lookup_side_effects(drug: NormalizedDrug) -> SafetyInfo:
    if not drug.canonical_name:
        return SafetyInfo(side_effects=[], source=None, available=False)

    raw_blocks = _openfda.get_side_effects(drug.canonical_name)
    if not raw_blocks:
        return SafetyInfo(side_effects=[], source=None, available=False)

    combined_text = " ".join(raw_blocks)
    extracted = _extract_with_llm(combined_text)

    if extracted:
        side_effects = extracted
    else:
        # Fallback: same behavior as before — trimmed raw paragraphs, still
        # sourced and cited, just less scannable.
        side_effects = [b[:_MAX_BLOCK_CHARS] + ("..." if len(b) > _MAX_BLOCK_CHARS else "") for b in raw_blocks]

    return SafetyInfo(
        side_effects=side_effects,
        source=_openfda.get_source_url(drug.canonical_name),
        available=True,
    )
