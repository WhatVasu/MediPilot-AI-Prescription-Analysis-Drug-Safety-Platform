"""
[3] Confidence Check

Pure logic, no LLM/API call. Flags (never hides, never blocks) any drug where
OCR confidence or RxNorm match confidence is too low to trust. This is the
transparency-based alternative to a severity gate: the app tells the user it
isn't sure, rather than making a judgment call on their behalf.
"""
from app import config
from app.graph.state import MediScanState


def confidence_check_node(state: MediScanState) -> dict:
    checked = []

    for drug in state.get("normalized_drugs", []) or []:
        if drug.canonical_name is None:
            drug.needs_verification = True
            drug.verification_reason = (
                "We couldn't confidently identify this medicine. Please check the original prescription."
            )
        elif drug.ocr_confidence < config.OCR_CONFIDENCE_THRESHOLD:
            drug.needs_verification = True
            drug.verification_reason = "We're not fully confident we read this medicine's name correctly."
        elif drug.match_confidence < config.MATCH_CONFIDENCE_THRESHOLD:
            drug.needs_verification = True
            drug.verification_reason = ""
        else:
            drug.needs_verification = False
            drug.verification_reason = None

        checked.append(drug)

    return {"normalized_drugs": checked}
