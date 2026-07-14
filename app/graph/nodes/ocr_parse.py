"""
[1] OCR & Parse Agent

Two-step: OCR.Space extracts raw text from the prescription image, then a
structured-output LLM call turns that raw text into a list of ParsedDrug
items. Split into two calls (rather than one multimodal call) because the
LLM provider here (Groq) doesn't support vision input.
"""
import logging

from langchain_core.messages import HumanMessage

from app.clients.llm_client import get_chat_model
from app.clients.vision_client import get_ocr_text
from app.graph.state import MediScanState
from app.schemas.ocr import ParsedPrescription

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are given raw OCR text extracted from a handwritten medical prescription.

Analyze the OCR output and extract every medicine mentioned.

For each medicine, return:
- raw_name: the medicine name exactly as it appears in the OCR text. Do NOT correct spelling, normalize names, or guess the intended medicine. Preserve OCR errors and ambiguities exactly as written. A later stage will handle normalization.
- dosage_as_written: the dosage only if it is explicitly present in the OCR text. Otherwise return null. Do not infer or assume a typical dosage.
- frequency_as_written: the administration frequency only if it is explicitly present in the OCR text. Otherwise return null.
- ocr_confidence: your confidence (0–1) that the extracted medicine name is correct based on the OCR text. If the OCR appears noisy, incomplete, or ambiguous, assign a lower confidence. Prefer under-confidence over over-confidence.

Do not invent or infer medicines that are not supported by the OCR text.

If the OCR text contains no identifiable medicine names, return an empty drugs list.
"""
def ocr_parse_node(state: MediScanState) -> dict:
    image_path = state.get("image_path")
    if not image_path:
        logger.error("ocr_parse_node called with no image_path in state")
        return {"raw_ocr_text": "", "parsed_drugs": []}

    try:
        ocr_text = get_ocr_text(image_path)

        if not ocr_text:
            return {"raw_ocr_text": "", "parsed_drugs": []}

        model = get_chat_model().with_structured_output(ParsedPrescription)
        message = HumanMessage(
            content=[
                {"type": "text", "text": SYSTEM_PROMPT},
                {"type": "text", "text": f"OCR Text:\n\n{ocr_text}"},
            ]
        )
        result: ParsedPrescription = model.invoke([message])
        drugs = getattr(result, "drugs", None) or []
        return {"raw_ocr_text": ocr_text, "parsed_drugs": drugs}
    except Exception:
        logger.exception("ocr_parse_node failed for image_path=%r", image_path)
        return {"raw_ocr_text": "", "parsed_drugs": []}
