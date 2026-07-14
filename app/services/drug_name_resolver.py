"""
Drug Name Spelling/Composition Resolution (LLM-assisted)

Runs before RxNorm's approximateTerm call. Pulls a direct advanced-search
answer from Tavily for extra grounding, then asks an LLM to either:
  - correct an obvious OCR misspelling to the closest real drug name, or
  - surface the generic/chemical composition of a recognized drug,

strictly without inventing a plausible-sounding name it isn't sure about,
and strictly without trusting Tavily's answer blindly — web context is a
hint, not a source of truth to be echoed. If the model isn't confident, it
must return null fields — the pipeline then falls back to RxNorm's own
fuzzy matching on the raw string.
"""
from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from app.clients.llm_client import get_chat_model
from app.clients.tavily_client import TavilyClient

logger = logging.getLogger(__name__)

_tavily = TavilyClient()


class DrugNameResolution(BaseModel):
    """Structured output contract for the LLM correction step.

    Null fields are a valid, expected outcome when the model isn't sure —
    callers must treat that as normal, not as a failure to handle.
    """

    corrected_name: str | None = Field(
        default=None,
        description=(
            "Closest real drug name (brand or generic) if the raw OCR text "
            "is clearly a misspelling of it. Null if not confident."
        ),
    )
    generic_name: str | None = Field(
        default=None,
        description=(
            "Generic/chemical composition of the drug, if known with "
            "confidence. Null if not confident or not applicable."
        ),
    )
    is_confident: bool = Field(
        description=(
            "True only if corrected_name and/or generic_name are populated "
            "with confidence. If False, both name fields must be null."
        )
    )


_SYSTEM_PROMPT = """\
You are a pharmacy assistant cleaning up OCR text from a prescription \
before it is looked up in RxNorm.

You will be given:
1. A raw, possibly-misspelled drug name from OCR.
2. Extra web context: a direct "advanced search answer" from a web search \
tool, plus a few supporting result snippets. This context may be partial, \
off-topic, about a different drug entirely, or wrong. Treat it as a hint \
to check against your own knowledge — never as ground truth to copy from.

Rules you MUST follow:
1. If the raw OCR name is an obvious corruption of a real, well-known \
medicine name (brand or generic), return the correct name in \
`corrected_name`. Use the web context to help confirm spelling, but only \
if it agrees with what you already know — if the web context contradicts \
your own knowledge or looks unreliable, prefer your own knowledge, or \
prefer null over guessing.
2. If you recognize the drug and know its generic/chemical composition \
with confidence, return it in `generic_name`. The web context can support \
this, but you must not repeat a composition from the web context that you \
cannot independently verify against your own knowledge.
3. NEVER invent, guess, or auto-complete a name you are not sure about — \
this includes never adopting a name or composition solely because the web \
context mentioned it. If the web context is empty, irrelevant, or about an \
unrelated drug, ignore it and rely only on your own knowledge.
4. If the text is ambiguous, garbled beyond confident repair, or could \
match several unrelated drugs, set `is_confident` to false and leave both \
name fields null.
5. Prefer returning nothing over returning something wrong — a wrong \
answer here propagates into a medical-safety pipeline.
"""


def _format_web_context(tavily_result: dict) -> str:
    answer = tavily_result.get("answer")
    results = tavily_result.get("results") or []

    if not answer and not results:
        return "No web context available."

    lines = []
    if answer:
        lines.append(f"Advanced search answer: {answer}")
    else:
        lines.append("Advanced search answer: none returned.")

    if results:
        lines.append("Supporting snippets:")
        for r in results[:3]:
            title = r.get("title", "")
            content = (r.get("content") or "")[:300]
            lines.append(f"- {title}: {content}")

    return "\n".join(lines)


def resolve_drug_name(raw_name: str) -> DrugNameResolution:
    """Best-effort LLM enrichment for one raw drug name.

    Never raises — any failure or low-confidence result collapses to an
    all-null resolution so callers can always fall back to `raw_name`.
    """
    tavily_result = _tavily.get_answer(f"{raw_name} medicine drug name composition")
    web_context = _format_web_context(tavily_result)

    try:
        model = get_chat_model()
        structured_model = model.with_structured_output(DrugNameResolution)
        result = structured_model.invoke(
            [
                ("system", _SYSTEM_PROMPT),
                (
                    "user",
                    f"Raw OCR drug name: {raw_name!r}\n\n"
                    f"Web context:\n{web_context}",
                ),
            ]
        )
    except Exception:
        logger.warning("Drug-name resolution LLM call failed for %r", raw_name, exc_info=True)
        return DrugNameResolution(is_confident=False)

    if not isinstance(result, DrugNameResolution):
        try:
            result = DrugNameResolution.model_validate(result)
        except Exception:
            logger.warning("Drug-name resolution returned an unparseable result for %r", raw_name, exc_info=True)
            return DrugNameResolution(is_confident=False)

    if not result.is_confident:
        return DrugNameResolution(is_confident=False)

    return result