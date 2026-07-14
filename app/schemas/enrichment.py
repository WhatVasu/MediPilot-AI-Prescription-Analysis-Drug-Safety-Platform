"""Schemas for what comes out of node [4] Per-Drug Enrichment."""
from pydantic import BaseModel, Field


class DosageInfo(BaseModel):
    as_written: str | None = Field(default=None, description="Dosage as legible on the prescription, if any.")
    frequency_as_written: str | None = Field(default=None, description="Frequency as legible on the prescription, if any.")
    general_reference: str | None = Field(
        default=None,
        description="Standard dosing guideline from the drug's official label (OpenFDA). "
        "General information, NOT a personalized recommendation.",
    )
    source: str | None = Field(default=None, description="Citation URL for general_reference.")


class SideEffectsExtraction(BaseModel):
    """Structured-output target for turning raw FDA label paragraphs into a
    short, citeable list. Extraction only — the model may not add anything
    not already present in the source text."""

    side_effects: list[str] = Field(
        default_factory=list,
        description="Short phrases (2-4 words each), each a side effect explicitly named in the source text.",
    )


class SafetyInfo(BaseModel):
    side_effects: list[str] = Field(default_factory=list, description="Text blocks pulled verbatim from the FDA label.")
    source: str | None = Field(default=None, description="Citation URL.")
    available: bool = Field(default=False, description="False if no label data was found for this drug.")


class EcommerceLinks(BaseModel):
    tata_1mg: str
    pharmeasy: str
    netmeds: str


class EnrichedDrug(BaseModel):
    """Everything gathered for one medicine, ready for the report synthesizer."""

    raw_name: str
    canonical_name: str | None
    rxcui: str | None
    needs_verification: bool
    verification_reason: str | None
    package_image_url: str | None
    dosage: DosageInfo
    safety: SafetyInfo
    generic_alternatives: list[str] = Field(default_factory=list)
    purchase_links: EcommerceLinks | None = None
