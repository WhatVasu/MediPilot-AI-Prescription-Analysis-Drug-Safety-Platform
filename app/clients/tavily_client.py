"""
Thin wrapper around Tavily's /search endpoint, used to pull a direct
"advanced answer" (not just raw links/snippets) for a drug name query before
handing it to the LLM resolver.
"""
from __future__ import annotations

import logging

import requests

from app import config

logger = logging.getLogger(__name__)

_TAVILY_URL = "https://api.tavily.com/search"


class TavilyClient:
    def __init__(self, api_key: str | None = None, timeout: float = 8.0):
        # No hardcoded default: an API key baked into source is a real
        # credential leak the moment this file is committed anywhere. Load
        # it from config (env var) instead, same as every other provider key.
        self._api_key = api_key or config.TAVILY_API_KEY
        self._timeout = timeout

    def get_answer(self, query: str) -> dict:
        """Runs an advanced Tavily search and returns the direct answer plus
        the raw results it was derived from.

        Returns a dict shaped like:
            {"answer": str | None, "results": list[dict]}
        Never raises — network/API failures, and a missing API key, collapse
        to an empty result so callers (drug_name_resolver) can fall back
        gracefully to RxNorm's own fuzzy matching.
        """
        if not self._api_key:
            logger.warning("TAVILY_API_KEY is not set; skipping web-context lookup for %r.", query)
            return {"answer": None, "results": []}

        payload = {
            "api_key": self._api_key,
            "query": query,
            "search_depth": "advanced",
            "include_answer": "advanced",
            "max_results": 5,
        }

        try:
            resp = requests.post(_TAVILY_URL, json=payload, timeout=self._timeout)
            resp.raise_for_status()
            data = resp.json() or {}
        except Exception:
            logger.warning("Tavily search failed for %r", query, exc_info=True)
            return {"answer": None, "results": []}

        return {
            "answer": data.get("answer"),
            "results": data.get("results", []) or [],
        }