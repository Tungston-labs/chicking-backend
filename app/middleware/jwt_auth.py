from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config.database import db
from app.models.admin_model import serialize_admin
from app.utils.jwt import decode_token


bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    payload = decode_token(credentials.credentials, expected_type="access")
    admin_id = payload.get("sub")
    admin = await db.admins.find_one({"id": admin_id, "is_active": True})
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin account not found",
        )
    return admin


async def get_current_admin_profile(
    admin: dict = Depends(get_current_admin),
) -> dict:
    return serialize_admin(admin)
