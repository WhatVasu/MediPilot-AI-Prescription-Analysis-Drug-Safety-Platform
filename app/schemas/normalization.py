"""Schemas for what comes out of node [2] Drug Name Normalization Agent
and node [3] Confidence Check."""
from pydantic import BaseModel, Field


class NormalizedDrug(BaseModel):
    """A drug after attempting to resolve raw_name to a real, canonical medicine."""

    raw_name: str
    dosage_as_written: str | None = None
    frequency_as_written: str | None = None
    ocr_confidence: float
    llm_corrected_name: str | None = None
    llm_generic_name: str | None = None

    canonical_name: str | None = Field(
        default=None, description="Best-matched real drug name from RxNorm. Null if no acceptable match was found."
    )
    rxcui: str | None = Field(
        default=None, description="RxNorm concept unique identifier for canonical_name — used by every downstream lookup."
    )
    match_confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="RxNorm approximateTerm score, normalized to 0-1."
    )
    needs_verification: bool = Field(
        default=False, description="Set by the confidence-check node. True if OCR or name-match confidence is too low to trust."
    )
    verification_reason: str | None = Field(
        default=None, description="Human-readable reason shown to the user, e.g. 'Could not confidently match this medicine name.'"
    )
