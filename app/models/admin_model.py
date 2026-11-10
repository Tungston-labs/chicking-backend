from datetime import datetime
from typing import Any


def serialize_datetime(value: datetime | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return value.isoformat()


def serialize_admin(admin: Any) -> dict[str, Any]:
    admin_dict = admin.to_dict() if hasattr(admin, "to_dict") else admin
    return {
        "id": admin_dict["id"],
        "name": admin_dict["name"],
        "email": admin_dict["email"],
        "role": admin_dict["role"],
        "isActive": admin_dict.get("is_active", True),
        "lastLoginAt": serialize_datetime(admin_dict.get("last_login_at")),
        "createdAt": serialize_datetime(admin_dict.get("created_at")),
        "updatedAt": serialize_datetime(admin_dict.get("updated_at")),
    }
