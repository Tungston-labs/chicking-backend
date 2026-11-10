from datetime import datetime, timedelta
import hashlib
import secrets
from smtplib import SMTPException
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db_session
from app.config.settings import get_settings
from app.models.admin_model import serialize_admin
from app.models.entities import Admin, PasswordResetOTP, RefreshToken
from app.utils.email import send_password_reset_otp_email
from app.utils.hash import hash_password, verify_password
from app.utils.jwt import (
    create_access_token,
    create_refresh_token,
    create_reset_token,
    decode_token,
)

settings = get_settings()


def _utc_now() -> datetime:
    return datetime.utcnow()


def _hash_otp(email: str, otp: str) -> str:
    value = f"{email}:{otp}:{settings.jwt_secret}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _hash_refresh_token(token: str) -> str:
    value = f"{token}:{settings.jwt_secret}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _generate_otp() -> str:
    minimum = 10 ** (settings.otp_length - 1)
    maximum = (10**settings.otp_length) - 1
    return str(secrets.randbelow(maximum - minimum + 1) + minimum)


async def _store_refresh_token(
    admin: dict[str, Any], refresh_token: str, now: datetime, session: AsyncSession
) -> None:
    expires_at = now + timedelta(days=settings.refresh_token_expire_days)
    token_entity = RefreshToken(
        token_hash=_hash_refresh_token(refresh_token),
        admin_id=admin["id"],
        email=admin["email"],
        expires_at=expires_at,
        created_at=now,
        updated_at=now,
        revoked_at=None,
    )
    session.add(token_entity)
    await session.flush()


async def _issue_auth_tokens(
    admin: dict[str, Any], now: datetime, session: AsyncSession
) -> dict[str, Any]:
    token_payload = {
        "sub": admin["id"],
        "email": admin["email"],
        "role": admin["role"],
    }
    access_token = create_access_token(token_payload)
    refresh_token = create_refresh_token(token_payload)
    await _store_refresh_token(admin, refresh_token, now, session)
    return {
        "accessToken": access_token,
        "refreshToken": refresh_token,
        "tokenType": "bearer",
        "expiresIn": settings.jwt_expire_minutes * 60,
        "refreshExpiresIn": settings.refresh_token_expire_days * 24 * 60 * 60,
    }


async def login_admin(credentials: Any) -> dict[str, Any]:
    async with get_db_session() as session:
        stmt = select(Admin).where(
            Admin.email == credentials.email.lower(), Admin.is_active == True
        )
        admin = (await session.execute(stmt)).scalar_one_or_none()

        if not admin or not verify_password(credentials.password, admin.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        now = _utc_now()
        admin.last_login_at = now
        admin.updated_at = now
        await session.flush()

        admin_dict = admin.to_dict()
        tokens = await _issue_auth_tokens(admin_dict, now, session)

        return {
            "message": "Login successful",
            **tokens,
            "admin": serialize_admin(admin_dict),
        }


async def forgot_password(payload: Any) -> dict[str, Any]:
    email = payload.email.lower()
    success_message = {
        "message": "If the admin account exists, an OTP has been sent to the registered email address.",
    }

    async with get_db_session() as session:
        stmt = select(Admin).where(Admin.email == email, Admin.is_active == True)
        admin = (await session.execute(stmt)).scalar_one_or_none()

        if not admin:
            return success_message

        now = _utc_now()
        otp = _generate_otp()
        expires_at = now + timedelta(minutes=settings.otp_expire_minutes)

        otp_stmt = select(PasswordResetOTP).where(PasswordResetOTP.email == email)
        record = (await session.execute(otp_stmt)).scalar_one_or_none()

        if record:
            record.admin_id = admin.id
            record.otp_hash = _hash_otp(email, otp)
            record.expires_at = expires_at
            record.updated_at = now
            record.verified_at = None
            record.used_at = None
        else:
            record = PasswordResetOTP(
                email=email,
                admin_id=admin.id,
                otp_hash=_hash_otp(email, otp),
                expires_at=expires_at,
                created_at=now,
                updated_at=now,
                verified_at=None,
                used_at=None,
            )
            session.add(record)

        await session.flush()

        try:
            await send_password_reset_otp_email(email, otp, settings.otp_expire_minutes)
        except (RuntimeError, SMTPException, OSError) as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to send OTP email at the moment. Please try again later.",
            ) from exc

        return {
            **success_message,
            "expiresInMinutes": settings.otp_expire_minutes,
        }


async def verify_reset_otp(payload: Any) -> dict[str, Any]:
    email = payload.email.lower()
    async with get_db_session() as session:
        stmt = select(PasswordResetOTP).where(PasswordResetOTP.email == email)
        record = (await session.execute(stmt)).scalar_one_or_none()

        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OTP not found")

        now = _utc_now()
        if record.used_at:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OTP already used")
        if record.expires_at < now:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OTP has expired")
        if record.otp_hash != _hash_otp(email, payload.otp):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OTP")

        record.verified_at = now
        record.updated_at = now
        await session.flush()

        reset_token = create_reset_token({"sub": record.admin_id, "email": email})

        return {
            "message": "OTP verified successfully",
            "resetToken": reset_token,
        }


async def reset_password(payload: Any) -> dict[str, Any]:
    token_payload = decode_token(payload.reset_token, expected_type="password_reset")
    admin_id = token_payload.get("sub")
    email = (token_payload.get("email") or "").lower()

    async with get_db_session() as session:
        admin_stmt = select(Admin).where(
            Admin.id == admin_id, Admin.email == email, Admin.is_active == True
        )
        admin = (await session.execute(admin_stmt)).scalar_one_or_none()
        if not admin:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin not found")

        otp_stmt = select(PasswordResetOTP).where(PasswordResetOTP.email == email)
        record = (await session.execute(otp_stmt)).scalar_one_or_none()
        if not record or not record.verified_at or record.used_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OTP verification is required before resetting the password",
            )

        now = _utc_now()
        admin.password_hash = hash_password(payload.new_password)
        admin.updated_at = now

        record.used_at = now
        record.updated_at = now

        await session.execute(
            update(RefreshToken)
            .where(RefreshToken.admin_id == admin_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now, updated_at=now)
        )

        return {
            "message": "Password reset successful",
        }


async def refresh_access_token(payload: Any) -> dict[str, Any]:
    refresh_token = payload.refresh_token
    token_payload = decode_token(refresh_token, expected_type="refresh")
    token_hash = _hash_refresh_token(refresh_token)

    async with get_db_session() as session:
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        record = (await session.execute(stmt)).scalar_one_or_none()

        if not record:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token not found",
            )

        now = _utc_now()
        if record.revoked_at:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has been revoked",
            )
        if record.expires_at < now:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has expired",
            )

        admin_id = token_payload.get("sub")
        email = (token_payload.get("email") or "").lower()
        admin_stmt = select(Admin).where(
            Admin.id == admin_id, Admin.email == email, Admin.is_active == True
        )
        admin = (await session.execute(admin_stmt)).scalar_one_or_none()
        if not admin:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Admin account not found",
            )

        record.revoked_at = now
        record.updated_at = now
        await session.flush()

        admin_dict = admin.to_dict()
        tokens = await _issue_auth_tokens(admin_dict, now, session)

        return {
            "message": "Token refreshed successfully",
            **tokens,
        }
