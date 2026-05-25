
# app/utils/image_upload.py

import base64
import os
import uuid

from app.config.settings import get_settings


UPLOAD_DIR = "uploads/blogs"
settings = get_settings()


def _public_base_url() -> str:
    return settings.public_base_url.rstrip("/")


def build_public_asset_url(path: str) -> str:
    cleaned_path = path.strip()
    if cleaned_path.startswith(("http://", "https://")):
        return cleaned_path
    if cleaned_path.startswith("/"):
        return f"{_public_base_url()}{cleaned_path}"
    return f"{_public_base_url()}/{cleaned_path}"


def save_base64_image(image_data: str) -> str:
    if not image_data.startswith("data:image"):
        return build_public_asset_url(image_data)

    header, encoded = image_data.split(",", 1)
    mime = header.split(";")[0].split(":")[1]

    mime_map = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
        "image/svg+xml": "svg",
    }

    ext = mime_map.get(mime, "png")
    filename = f"{uuid.uuid4()}.{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    with open(filepath, "wb") as file:
        file.write(base64.b64decode(encoded))

    return build_public_asset_url(f"/uploads/blogs/{filename}")


def normalize_image_value(image_data: str | None) -> str | None:
    if not isinstance(image_data, str):
        return image_data

    cleaned_image = image_data.strip()
    if not cleaned_image:
        return cleaned_image

    if cleaned_image.startswith("data:image"):
        return save_base64_image(cleaned_image)

    return build_public_asset_url(cleaned_image)
