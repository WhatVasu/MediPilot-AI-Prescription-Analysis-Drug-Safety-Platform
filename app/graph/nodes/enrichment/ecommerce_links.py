"""
[4d] E-commerce Search Links

Generates public site-search URLs rather than hitting any scraping/partner
API — no auth, no ToS risk, always works. Uses the *canonical* (corrected)
drug name, which is exactly why normalization has to happen before this step:
searching for a misspelled name returns nothing useful on any of these sites.
"""
from urllib.parse import quote_plus

from app.schemas.enrichment import EcommerceLinks
from app.schemas.normalization import NormalizedDrug


def build_ecommerce_links(drug: NormalizedDrug) -> EcommerceLinks | None:
    if not drug.canonical_name:
        return None

    name = quote_plus(drug.canonical_name)
    return EcommerceLinks(
        tata_1mg=f"https://www.1mg.com/search/all?name={name}",
        pharmeasy=f"https://pharmeasy.in/search/all?name={name}",
        netmeds=f"https://www.netmeds.com/catalogsearch/result?q={name}",
    )
