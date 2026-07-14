"""
Thin wrapper around OpenFDA's drug label endpoint (free, no key required for
low-volume use). Docs: https://open.fda.gov/apis/drug/label/

This is the client that keeps side-effect and dosage claims grounded in a
real, citable source instead of LLM memory. If OpenFDA has nothing for a
drug, callers should show "not available" rather than let an LLM fill the
gap — an absent fact is safer than an invented one.
"""
import logging
from functools import lru_cache

import requests

logger = logging.getLogger(__name__)

OPENFDA_BASE_URL = "https://api.fda.gov/drug/label.json"


@lru_cache(maxsize=256)
def _fetch_label(drug_name: str, timeout: float) -> dict | None:
    # Module-level (not instance-level) cache: dosage lookup, side-effects
    # lookup, and the synthesizer's indication summary each instantiate
    # their own OpenFDAClient() and independently call get_label() for the
    # same drug — without a shared cache that's 3 identical OpenFDA round
    # trips per drug instead of 1.
    try:
        query = f'openfda.generic_name:"{drug_name}" OR openfda.brand_name:"{drug_name}"'
        resp = requests.get(
            OPENFDA_BASE_URL,
            params={"search": query, "limit": 1},
            timeout=timeout,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        payload = resp.json() or {}
        results = payload.get("results", []) or []
        return results[0] if results else None
    except Exception:
        logger.warning("OpenFDA label lookup failed for %r", drug_name, exc_info=True)
        return None


class OpenFDAClient:
    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    def get_label(self, drug_name: str) -> dict | None:
        """
        Looks up the FDA label for a drug by generic or brand name.
        Returns the raw label dict (first match) or None if nothing found.
        """
        if not drug_name or not isinstance(drug_name, str):
            return None
        return _fetch_label(drug_name, self.timeout)

    def get_dosage_and_administration(self, drug_name: str) -> str | None:
        label = self.get_label(drug_name)
        if not label:
            return None
        field = label.get("dosage_and_administration")
        return field[0] if field else None

    def get_side_effects(self, drug_name: str) -> list[str]:
        label = self.get_label(drug_name)
        if not label:
            return []
        # adverse_reactions is the most reliable field; fall back to warnings
        field = label.get("adverse_reactions") or label.get("warnings") or []
        return field  # list of text blocks, may need truncation for display

    def get_source_url(self, drug_name: str) -> str:
        """Human-visible citation link for the label lookup, shown alongside side effects."""
        return f"https://api.fda.gov/drug/label.json?search=openfda.generic_name:{drug_name}"
