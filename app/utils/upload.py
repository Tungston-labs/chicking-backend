
# app/utils/image_upload.py

import base64
import os
import uuid

UPLOAD_DIR = "uploads/blogs"
BASE_URL = "http://178.248.112.5/uploads/blogs"


def save_base64_image(image_data: str) -> str:
    if not image_data.startswith("data:image"):
        return image_data  # already URL

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

    with open(filepath, "wb") as f:
        f.write(base64.b64decode(encoded))

    return f"{BASE_URL}/{filename}"