"""
[4a] General Dosage & Timing Lookup

Since prescriptions often only state the drug name (dosage/timing given
orally), this pulls the standard label dosing from OpenFDA as a reference —
explicitly kept separate from whatever was actually legible on the
prescription. Never presented as "your dose."
"""
from app.clients.openfda_client import OpenFDAClient
from app.schemas.enrichment import DosageInfo
from app.schemas.normalization import NormalizedDrug

_openfda = OpenFDAClient()


def lookup_dosage(drug: NormalizedDrug) -> DosageInfo:
    general_reference = None
    source = None

    if drug.canonical_name:
        general_reference = _openfda.get_dosage_and_administration(drug.canonical_name)
        if general_reference:
            source = _openfda.get_source_url(drug.canonical_name)

    general_reference = general_reference[:200] if general_reference else None

    return DosageInfo(
        as_written=drug.dosage_as_written,
        frequency_as_written=drug.frequency_as_written,
        general_reference=general_reference,
        source=source,
    )
