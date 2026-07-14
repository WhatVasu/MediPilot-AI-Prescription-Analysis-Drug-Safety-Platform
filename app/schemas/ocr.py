"""Schemas for what comes out of node [1] OCR & Parse Agent."""
from pydantic import BaseModel, Field


class ParsedDrug(BaseModel):
    """One medicine as read off the prescription, before any correction."""

    raw_name: str = Field(description="Drug name exactly as the OCR/vision model read it, misspellings included")
    dosage_as_written: str | None = Field(
        default=None, description="Dosage text if legible on the prescription, e.g. '500mg'. Null if not written or illegible."
    )
    frequency_as_written: str | None = Field(
        default=None, description="Frequency/timing text if legible, e.g. 'twice daily'. Null if not written or illegible."
    )
    ocr_confidence: float = Field(
        ge=0.0, le=1.0, description="Model's own confidence that raw_name was read correctly from the image"
    )


class ParsedPrescription(BaseModel):
    """Full structured output of node [1] for one prescription image."""

    drugs: list[ParsedDrug]
