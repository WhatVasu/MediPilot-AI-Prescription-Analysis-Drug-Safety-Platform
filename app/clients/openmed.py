import logging

import requests

logger = logging.getLogger(__name__)

DAILYMED_BASE = "https://dailymed.nlm.nih.gov/dailymed/services/v2"


def get_drug_image_from_rxcui(rxcui: str | None) -> str | None:
    if not rxcui:
        return None

    try:
        spl_resp = requests.get(
            f"{DAILYMED_BASE}/spls.json?rxcui={rxcui}",
            timeout=10,
        )
        spl_resp.raise_for_status()

        spl_payload = spl_resp.json() or {}
        spl_data = spl_payload.get("data") or []
        if not isinstance(spl_data, list) or not spl_data:
            return None

        first_spl = spl_data[0] or {}
        setid = first_spl.get("setid")
        if not setid:
            return None

        media_resp = requests.get(
            f"{DAILYMED_BASE}/spls/{setid}/media.json",
            timeout=10,
        )
        media_resp.raise_for_status()

        media_payload = media_resp.json() or {}
        media_data = media_payload.get("data") or {}
        if not isinstance(media_data, dict):
            return None

        media = media_data.get("media") or []
        if not isinstance(media, list) or not media:
            return None

        first_media = media[0] or {}
        return first_media.get("url") or None

    except Exception as e:
        logger.warning("Failed to fetch drug package image for rxcui=%r: %s", rxcui, e)
        return None