"""
[4c] Generic Alternative Lookup

Uses RxNorm's related-concepts endpoint (already wrapped in RxNormClient)
to find the generic ingredient name(s) for a resolved drug.
"""
from app.clients.rxnorm_client import RxNormClient
from app.schemas.normalization import NormalizedDrug

_rxnorm = RxNormClient()


def lookup_generics(drug: NormalizedDrug) -> list[str]:
    if not drug.rxcui:
        return []
    try:
        return _rxnorm.brand_to_generic(drug.rxcui)
    except Exception:
        # Non-critical enrichment — missing generics shouldn't fail the whole card.
        return []
