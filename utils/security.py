import io
import re
import secrets
import time
import unicodedata
from PIL import Image, ImageOps
import streamlit as st

MAX_IMAGE_BYTES = 2 * 1024 * 1024  # 2 MB hard limit
ALLOWED_IMAGE_FORMATS = {"PNG", "JPEG", "WEBP"}


def generate_order_id() -> str:
    """Generate a cryptographically random Order ID: 'WF' + 5 digits."""
    number = secrets.randbelow(90000) + 10000
    return f"WF{number}"


def sanitize_text(value: str, max_len: int = 500) -> str:
    """Clean control characters, neutralize Discord markdown/pings, and trim length."""
    if not value:
        return ""
    cleaned = unicodedata.normalize("NFKC", value)
    cleaned = "".join(
        ch for ch in cleaned
        if ch in ("\n", " ", "\t") or unicodedata.category(ch)[0] != "C"
    )
    cleaned = cleaned.strip()[:max_len]
    # Prevent Discord @everyone / @here / role-ping abuse and broken code blocks
    cleaned = cleaned.replace("@", "@\u200b")
    cleaned = cleaned.replace("```", "'''")
    return cleaned


def validate_phone(phone: str) -> tuple[bool, str]:
    """Validate Pakistani / international phone number format."""
    normalized = re.sub(r"[\s\-()]", "", phone.strip())
    if re.fullmatch(r"(\+92|0)?3\d{9}", normalized) or re.fullmatch(r"\+?\d{10,15}", normalized):
        return True, normalized
    return False, ""


def check_rate_limit(action_key: str, cooldown_seconds: int = 15) -> tuple[bool, int]:
    """Per-session rate limiter to prevent Discord webhook spam/flooding."""
    now = time.time()
    timestamps = st.session_state.setdefault("_rate_limits", {})
    last_time = timestamps.get(action_key, 0.0)
    elapsed = now - last_time
    if elapsed < cooldown_seconds:
        return False, int(cooldown_seconds - elapsed) + 1
    timestamps[action_key] = now
    return True, 0


def validate_and_clean_receipt(uploaded_file) -> tuple[bool, bytes | None, str, str]:
    """
    Validate uploaded payment screenshot:
    - Enforces <= 2 MB size limit
    - Verifies actual image bytes via Pillow (not just file extension)
    - Re-encodes image to strip EXIF/GPS metadata & neutralize polyglot payloads
    Returns: (is_valid, cleaned_bytes, filename, error_message)
    """
    if uploaded_file is None:
        return False, None, "", "Please upload your JazzCash payment screenshot."

    raw_bytes = uploaded_file.getvalue()
    if len(raw_bytes) == 0:
        return False, None, "", "Uploaded file is empty."
    if len(raw_bytes) > MAX_IMAGE_BYTES:
        return False, None, "", "Screenshot exceeds the 2 MB maximum size limit."

    try:
        with Image.open(io.BytesIO(raw_bytes)) as img:
            img.verify()

        with Image.open(io.BytesIO(raw_bytes)) as img:
            if img.format not in ALLOWED_IMAGE_FORMATS:
                return False, None, "", "Only PNG, JPG, JPEG, or WEBP images are allowed."

            img = ImageOps.exif_transpose(img)
            img.thumbnail((1600, 1600))

            output = io.BytesIO()
            if img.mode in ("RGBA", "P") and img.format == "PNG":
                img.save(output, format="PNG", optimize=True)
                clean_name = "receipt.png"
            else:
                if img.mode != "RGB":
                    img = img.convert("RGB")
                img.save(output, format="JPEG", quality=88, optimize=True)
                clean_name = "receipt.jpg"

            return True, output.getvalue(), clean_name, ""
    except Exception:
        return False, None, "", "Invalid or corrupted image file. Please upload a valid screenshot."
