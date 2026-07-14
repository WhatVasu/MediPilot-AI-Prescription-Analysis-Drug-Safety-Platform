"""Schema for what comes out of node [5] Report Synthesizer — the final UI-ready output."""
from pydantic import BaseModel, Field

from app.schemas.enrichment import EnrichedDrug

STANDARD_DISCLAIMER = (
    "This is informational only. Confirm dosage and interactions with your pharmacist or doctor before use."
)

DOSAGE_DISCLAIMER = (
    "General dosing shown is standard reference information, not a personal recommendation — "
    "your actual prescribed dose may differ."
)


class MedicineCard(BaseModel):
    """One rendered card per medicine — what the UI actually loops over."""

    display_name: str
    raw_text: str
    package_image_url: str | None = None
    what_its_for: str | None = Field(default=None, description="Plain-language summary, grounded in label data.")
    dosage: dict
    side_effects: list[str]
    safety_source: str | None
    generic_alternatives: list[str]
    purchase_links: dict | None
    needs_verification: bool
    verification_reason: str | None


class FinalReport(BaseModel):
    cards: list[MedicineCard]
    disclaimers: list[str] = Field(default_factory=lambda: [STANDARD_DISCLAIMER, DOSAGE_DISCLAIMER])
