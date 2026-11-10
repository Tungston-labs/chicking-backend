from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from app.config.database import get_db_session
from app.models.admin_model import serialize_admin
from app.models.entities import Admin
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

    async with get_db_session() as session:
        stmt = select(Admin).where(Admin.id == admin_id, Admin.is_active == True)
        admin = (await session.execute(stmt)).scalar_one_or_none()
        if not admin:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Admin account not found",
            )
        return admin.to_dict()


async def get_current_admin_profile(
    admin: dict = Depends(get_current_admin),
) -> dict:
    return serialize_admin(admin)
