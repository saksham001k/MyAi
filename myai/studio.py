"""Validated image preprocessing for local Studio img2img jobs."""
import base64
import binascii
import io
import re
from pathlib import Path

from PIL import Image, UnidentifiedImageError


MAX_IMAGE_BYTES = 20 * 1024 * 1024
ALLOWED_FORMATS = {"PNG", "JPEG", "WEBP"}


def _decode_data_url(value):
    if not isinstance(value, str):
        raise ValueError("Image must be a base64 data URL.")
    match = re.fullmatch(r"data:image/(png|jpeg|jpg|webp);base64,([A-Za-z0-9+/=\s]+)", value, re.IGNORECASE)
    if not match:
        raise ValueError("Image must be a PNG, JPEG, or WebP base64 data URL.")
    try:
        data = base64.b64decode(match.group(2), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Image data is not valid base64.") from exc
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise ValueError("Image must be between 1 byte and 20 MB.")
    return data


def preprocess_image(data_url, destination, target_size=768):
    """Validate, center-crop, and save an image at a diffusion-safe size."""
    if type(target_size) is not int or target_size not in (512, 768, 1024):
        raise ValueError("Image target size must be 512, 768, or 1024.")
    data = _decode_data_url(data_url)
    try:
        with Image.open(io.BytesIO(data)) as source:
            if source.format not in ALLOWED_FORMATS:
                raise ValueError("Image must be PNG, JPEG, or WebP.")
            source.load()
            width, height = source.size
            if not width or not height:
                raise ValueError("Image dimensions are invalid.")
            image = source.convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("Image could not be decoded.") from exc

    scale = max(target_size / width, target_size / height)
    resized = image.resize((round(width * scale), round(height * scale)), Image.Resampling.LANCZOS)
    left = (resized.width - target_size) // 2
    top = (resized.height - target_size) // 2
    normalized = resized.crop((left, top, left + target_size, top + target_size))
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    normalized.save(destination, format="PNG", optimize=True)
    return {"path": destination, "width": width, "height": height,
            "normalized_width": target_size, "normalized_height": target_size}
