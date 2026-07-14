import logging
import os
import tempfile
import mimetypes

import requests
from PIL import Image, UnidentifiedImageError

from app import config

logger = logging.getLogger(__name__)


def compress_image(image_path: str, max_size=(2000, 2000), quality=85) -> str:
    """
    Compress and resize the image before uploading.
    Returns the path of the compressed temporary image.

    Raises ValueError if `image_path` doesn't exist or isn't a readable image —
    callers are expected to handle this (get_ocr_text does).
    """
    if not image_path or not os.path.exists(image_path):
        raise ValueError(f"Image file not found: {image_path!r}")

    try:
        img = Image.open(image_path)
        img.load()  # force-read now so truncated/corrupt files fail here, not later on save()
    except (UnidentifiedImageError, OSError) as e:
        raise ValueError(f"Could not read {image_path!r} as an image: {e}") from e

    # Convert RGBA/PNG images to RGB for JPEG
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    # Resize while maintaining aspect ratio
    img.thumbnail(max_size)

    # Save to a temporary file. Close the NamedTemporaryFile's own handle
    # immediately — we only need its unique path; Image.save() opens its own
    # handle to write into, so keeping this one open just leaks a file
    # descriptor for no reason.
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
    temp_file.close()

    try:
        img.save(
            temp_file.name,
            format="JPEG",
            quality=quality,
            optimize=True,
        )
    except Exception:
        # Don't leak the temp file if saving fails partway through.
        if os.path.exists(temp_file.name):
            os.remove(temp_file.name)
        raise

    return temp_file.name


def get_ocr_text(
    image_path: str,
    api_key: str | None = None,
    engine: int = 3
) -> str | None:
    """
    Extract text from a local prescription image using OCR.Space.
    Automatically compresses large images before uploading.
    """

    api_key = api_key or config.OCR_SPACE_API_KEY

    if not api_key:
        raise ValueError(
            "OCR_SPACE_API_KEY is not set. Add it to your environment or .env file."
        )

    api_endpoint = "https://api.ocr.space/parse/image"

    payload = {
        "apikey": api_key,
        "OCREngine": engine,
    }

    compressed_image = None
    try:
        compressed_image = compress_image(image_path)
        mime_type = mimetypes.guess_type(compressed_image)[0] or "image/jpeg"

        with open(compressed_image, "rb") as f:
            files = {
                "file": (
                    os.path.basename(compressed_image),
                    f,
                    mime_type,
                )
            }

            response = requests.post(
                api_endpoint,
                data=payload,
                files=files,
                timeout=60  # 60 seconds timeout
            )

            response.raise_for_status()

            result = response.json()

            if result.get("IsErroredOnProcessing"):
                logger.error("OCR Error: %s | Full response: %s", result.get("ErrorMessage"), result)
                return None

            parsed_results = result.get("ParsedResults", [])

            text = "\n".join(
                page.get("ParsedText", "")
                for page in parsed_results
            ).strip()

            return text if text else None

    except ValueError as e:
        # Raised by compress_image() for a missing/unreadable image file.
        logger.error("Invalid prescription image: %s", e)

    except requests.exceptions.Timeout:
        logger.error("OCR request timed out.")

    except requests.exceptions.RequestException as e:
        logger.error("OCR request failed: %s", e)

    except Exception as e:
        logger.exception("Unexpected error during OCR: %s", e)

    finally:
        # Delete temporary compressed image, if one was ever created.
        if compressed_image and os.path.exists(compressed_image):
            os.remove(compressed_image)

    return None