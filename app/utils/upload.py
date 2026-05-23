import base64
import binascii
import hashlib
import re
from pathlib import Path
from typing import Any

from app.config.settings import get_settings


settings = get_settings()
DATA_IMAGE_PATTERN = re.compile(r"^data:(image/[\w.+-]+);base64,(.+)$", re.IGNORECASE | re.DOTALL)
IMAGE_EXTENSION_MAP = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
    "image/svg+xml": "svg",
}


def _normalized_upload_prefix() -> str:
    prefix = str(settings.uploads_url_prefix or "/uploads").strip() or "/uploads"
    return prefix if prefix.startswith("/") else f"/{prefix}"


def _normalized_base_url() -> str:
    return str(settings.public_base_url or "").strip().rstrip("/")


def ensure_upload_directories() -> Path:
    uploads_dir = Path(settings.uploads_dir)
    blogs_dir = uploads_dir / "blogs"
    blogs_dir.mkdir(parents=True, exist_ok=True)
    return uploads_dir


def _blog_uploads_dir() -> Path:
    return ensure_upload_directories() / "blogs"


def _blog_upload_relative_path(filename: str) -> str:
    return f"{_normalized_upload_prefix()}/blogs/{filename}"


def _sanitize_identifier(value: str | None) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(value or "blog")).strip("-")
    return normalized or "blog"


def _parse_data_image(value: str) -> tuple[str, bytes] | None:
    match = DATA_IMAGE_PATTERN.match(value.strip())
    if not match:
        return None

    mime_type, encoded = match.groups()
    try:
        decoded = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        return None

    return mime_type.lower(), decoded


def store_blog_image(image_value: Any, blog_id: str | None = None) -> Any:
    if not isinstance(image_value, str):
        return image_value

    normalized = image_value.strip()
    if not normalized:
        return normalized

    parsed_image = _parse_data_image(normalized)
    if parsed_image is None:
        if normalized.startswith(_normalized_upload_prefix()):
            return normalized
        return normalized

    mime_type, image_bytes = parsed_image
    extension = IMAGE_EXTENSION_MAP.get(mime_type, "bin")
    digest = hashlib.sha256(image_bytes).hexdigest()[:16]
    filename = f"{_sanitize_identifier(blog_id)}-{digest}.{extension}"
    file_path = _blog_uploads_dir() / filename

    if not file_path.exists():
        file_path.write_bytes(image_bytes)

    return _blog_upload_relative_path(filename)


def build_public_asset_url(asset_path: Any) -> Any:
    if not isinstance(asset_path, str):
        return asset_path

    normalized = asset_path.strip()
    if not normalized:
        return normalized
    if normalized.startswith(("http://", "https://", "data:")):
        return normalized

    if not normalized.startswith("/"):
        normalized = f"/{normalized}"

    return f"{_normalized_base_url()}{normalized}" if _normalized_base_url() else normalized
