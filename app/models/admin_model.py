from datetime import datetime
from typing import Any


def serialize_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def serialize_admin(admin: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": admin["id"],
        "name": admin["name"],
        "email": admin["email"],
        "role": admin["role"],
        "isActive": admin.get("is_active", True),
        "lastLoginAt": serialize_datetime(admin.get("last_login_at")),
        "createdAt": serialize_datetime(admin.get("created_at")),
        "updatedAt": serialize_datetime(admin.get("updated_at")),
    }
