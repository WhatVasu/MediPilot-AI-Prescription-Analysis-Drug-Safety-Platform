"""
Thin wrapper around RxNorm's public REST API (no key required).
Docs: https://lhncbc.nlm.nih.gov/RxNav/APIs/RxNormAPIs.html

approximate_term() is the one that matters for this project: it's built for
fuzzy/misspelled drug name matching, which is exactly the handwriting-OCR
problem this app exists to solve.
"""

import logging

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app import config

logger = logging.getLogger(__name__)


class RxNormClient:
    def __init__(self, base_url: str | None = None, timeout: float = 10.0):
        self.base_url = base_url or config.RXNORM_BASE_URL
        self.timeout = timeout

        # Reuse connections across all requests
        self.session = requests.Session()

        # Retry transient connection/DNS/server errors
        retry = Retry(
            total=3,
            connect=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def approximate_term(self, term: str, max_entries: int | None = None) -> list[dict]:
        """
        Fuzzy-matches `term` against real drug names.

        Returns a list of candidates, each:
            {"rxcui": str, "name": str, "score": float}   # score normalized to 0-1
        Ordered best match first. Empty list if nothing usable was found.
        """
        if not term:
            return []

        max_entries = max_entries or config.RXNORM_MAX_CANDIDATES

        try:
            resp = self.session.get(
                f"{self.base_url}/approximateTerm.json",
                params={"term": term, "maxEntries": max_entries},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json() or {}
        except Exception:
            logger.warning("RxNorm approximateTerm lookup failed for %r", term, exc_info=True)
            return []

        candidates = data.get("approximateGroup", {}).get("candidate", []) or []
        results = []

        for c in candidates:
            if not isinstance(c, dict):
                continue

            rxcui = c.get("rxcui")
            raw_score = c.get("score")

            if rxcui is None or raw_score is None:
                continue

            name = self._rxcui_to_name(rxcui)
            if name is None:
                continue

            results.append(
                {
                    "rxcui": rxcui,
                    "name": name,
                    # RxNorm scores aren't bounded to 0-100 in practice, but are
                    # effectively bounded well under it for real medicine names.
                    # Clamp so this always reads as a clean 0-1 confidence.
                    "score": min(float(raw_score) / 100.0, 1.0),
                }
            )

        # normalize.py picks results[0] as the best match — don't rely on
        # RxNorm always returning candidates pre-sorted by score; sort
        # explicitly so that assumption always holds.
        results.sort(key=lambda r: r["score"], reverse=True)
        return results

    def _rxcui_to_name(self, rxcui: str) -> str | None:
        """approximateTerm doesn't return a clean display name directly — resolve it via /rxcui/{id}/property."""
        if not rxcui:
            return None

        try:
            resp = self.session.get(
                f"{self.base_url}/rxcui/{rxcui}/property.json",
                params={"propName": "RxNorm Name"},
                timeout=self.timeout,
            )

            if resp.status_code != 200:
                return None

            data = resp.json() or {}
            props = data.get("propConceptGroup", {}).get("propConcept", []) or []

            if not props:
                return None

            first_prop = props[0] if isinstance(props, list) and props else None
            return first_prop.get("propValue") if isinstance(first_prop, dict) else None
        except Exception:
            logger.warning("RxNorm rxcui->name lookup failed for %r", rxcui, exc_info=True)
            return None

    def brand_to_generic(self, rxcui: str) -> list[str]:
        """Given an rxcui, return related generic names (used later by node [4c])."""
        if not rxcui:
            return []

        try:
            resp = self.session.get(
                f"{self.base_url}/rxcui/{rxcui}/related.json",
                params={"tty": "IN"},  # IN = Ingredient (generic name) term type
                timeout=self.timeout,
            )
            resp.raise_for_status()

            data = resp.json() or {}
            groups = data.get("relatedGroup", {}).get("conceptGroup", []) or []

            names = []
            for g in groups:
                if not isinstance(g, dict):
                    continue
                for prop in g.get("conceptProperties", []) or []:
                    if isinstance(prop, dict) and prop.get("name"):
                        names.append(prop["name"])

            return names
        except Exception:
            logger.warning("RxNorm related-concepts lookup failed for rxcui=%r", rxcui, exc_info=True)
            return []