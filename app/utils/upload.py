import base64
import os
import re
import uuid

from app.config.settings import get_settings


UPLOAD_DIR = "uploads/blogs"


def _public_base_url() -> str:
    return get_settings().public_base_url.rstrip("/")


def build_public_asset_url(path: str) -> str:
    cleaned_path = path.strip()

    # If the URL contains /uploads/ (even from localhost or a previous domain),
    # rewrite it dynamically to use the active public_base_url
    match = re.search(r"/(uploads/.*)$", cleaned_path)
    if match:
        return f"{_public_base_url()}/{match.group(1)}"

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


def process_html_content_images(html_content: str) -> str:
    """
    Parses HTML content and replaces all base64 images with server URLs.
    """
    if not html_content or not isinstance(html_content, str):
        return html_content

    # Regex to find all img tags with base64 src
    pattern = r'(<img\b[^>]*\bsrc=")(data:image/[^;]+;base64,[^"]+)(")'

    def replace_base64(match):
        prefix = match.group(1)
        base64_data = match.group(2)
        suffix = match.group(3)

        new_url = save_base64_image(base64_data)
        return f"{prefix}{new_url}{suffix}"

    return re.sub(pattern, replace_base64, html_content)


def normalize_html_content_images(html_content: str | None) -> str | None:
    """
    Ensures any /uploads/ image inside HTML content uses the active PUBLIC_BASE_URL
    instead of hardcoded localhost URLs.
    """
    if not html_content or not isinstance(html_content, str):
        return html_content

    # First convert base64 images if any
    content = process_html_content_images(html_content)

    # Rewrite any src=".../uploads/..." to use the active _public_base_url()
    pattern = r'(<img\b[^>]*\bsrc=")([^"]*?/uploads/[^"]+)(")'

    def replace_src(match):
        prefix = match.group(1)
        src = match.group(2)
        suffix = match.group(3)
        upload_idx = src.find("/uploads/")
        if upload_idx != -1:
            rel_path = src[upload_idx:]
            new_src = f"{_public_base_url()}{rel_path}"
            return f"{prefix}{new_src}{suffix}"
        return match.group(0)

    return re.sub(pattern, replace_src, content)


def normalize_image_value(image_data: str | None) -> str | None:
    if not isinstance(image_data, str):
        return image_data

    cleaned_image = image_data.strip()
    if not cleaned_image:
        return cleaned_image

    if cleaned_image.startswith("data:image"):
        return save_base64_image(cleaned_image)

    return build_public_asset_url(cleaned_image)
