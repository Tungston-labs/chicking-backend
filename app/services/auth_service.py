import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from smtplib import SMTPException

from app.config.database import db
from app.config.settings import get_settings
from app.models.admin_model import serialize_admin
from app.utils.email import send_password_reset_otp_email
from app.utils.hash import hash_password, verify_password
from app.utils.jwt import create_access_token, create_refresh_token, create_reset_token, decode_token


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


async def _store_refresh_token(admin: dict[str, Any], refresh_token: str, now: datetime) -> None:
    expires_at = now + timedelta(days=settings.refresh_token_expire_days)
    await db.refresh_tokens.insert_one(
        {
            "token_hash": _hash_refresh_token(refresh_token),
            "admin_id": admin["id"],
            "email": admin["email"],
            "expires_at": expires_at,
            "created_at": now,
            "updated_at": now,
            "revoked_at": None,
        }
    )


async def _issue_auth_tokens(admin: dict[str, Any], now: datetime) -> dict[str, Any]:
    token_payload = {
        "sub": admin["id"],
        "email": admin["email"],
        "role": admin["role"],
    }
    access_token = create_access_token(token_payload)
    refresh_token = create_refresh_token(token_payload)
    await _store_refresh_token(admin, refresh_token, now)
    return {
        "accessToken": access_token,
        "refreshToken": refresh_token,
        "tokenType": "bearer",
        "expiresIn": settings.jwt_expire_minutes * 60,
        "refreshExpiresIn": settings.refresh_token_expire_days * 24 * 60 * 60,
    }


async def login_admin(credentials: Any) -> dict[str, Any]:
    admin = await db.admins.find_one({"email": credentials.email, "is_active": True})
    if not admin or not verify_password(credentials.password, admin["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    now = _utc_now()
    await db.admins.update_one(
        {"id": admin["id"]},
        {"$set": {"last_login_at": now, "updated_at": now}},
    )
    admin["last_login_at"] = now
    admin["updated_at"] = now

    tokens = await _issue_auth_tokens(admin, now)

    return {
        "message": "Login successful",
        **tokens,
        "admin": serialize_admin(admin),
    }


async def forgot_password(payload: Any) -> dict[str, Any]:
    admin = await db.admins.find_one({"email": payload.email, "is_active": True})
    success_message = {
        "message": "If the admin account exists, an OTP has been sent to the registered email address.",
    }

    if not admin:
        return success_message

    now = _utc_now()
    otp = _generate_otp()
    expires_at = now + timedelta(minutes=settings.otp_expire_minutes)

    await db.password_reset_otps.update_one(
        {"email": payload.email},
        {
            "$set": {
                "email": payload.email,
                "admin_id": admin["id"],
                "otp_hash": _hash_otp(payload.email, otp),
                "expires_at": expires_at,
                "updated_at": now,
                "verified_at": None,
                "used_at": None,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )

    try:
        await send_password_reset_otp_email(payload.email, otp, settings.otp_expire_minutes)
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
    record = await db.password_reset_otps.find_one({"email": payload.email})
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OTP not found")

    now = _utc_now()
    if record.get("used_at"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OTP already used")
    if record["expires_at"] < now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OTP has expired")
    if record["otp_hash"] != _hash_otp(payload.email, payload.otp):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OTP")

    await db.password_reset_otps.update_one(
        {"email": payload.email},
        {"$set": {"verified_at": now, "updated_at": now}},
    )

    reset_token = create_reset_token({"sub": record["admin_id"], "email": payload.email})

    return {
        "message": "OTP verified successfully",
        "resetToken": reset_token,
    }


async def reset_password(payload: Any) -> dict[str, Any]:
    token_payload = decode_token(payload.reset_token, expected_type="password_reset")
    admin_id = token_payload.get("sub")
    email = token_payload.get("email")

    admin = await db.admins.find_one({"id": admin_id, "email": email, "is_active": True})
    if not admin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Admin not found")

    record = await db.password_reset_otps.find_one({"email": email})
    if not record or not record.get("verified_at") or record.get("used_at"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP verification is required before resetting the password",
        )

    now = _utc_now()
    await db.admins.update_one(
        {"id": admin_id},
        {
            "$set": {
                "password_hash": hash_password(payload.new_password),
                "updated_at": now,
            }
        },
    )
    await db.password_reset_otps.update_one(
        {"email": email},
        {"$set": {"used_at": now, "updated_at": now}},
    )
    await db.refresh_tokens.update_many(
        {"admin_id": admin_id, "revoked_at": None},
        {"$set": {"revoked_at": now, "updated_at": now}},
    )

    return {
        "message": "Password reset successful",
    }


async def refresh_access_token(payload: Any) -> dict[str, Any]:
    refresh_token = payload.refresh_token
    token_payload = decode_token(refresh_token, expected_type="refresh")
    token_hash = _hash_refresh_token(refresh_token)
    record = await db.refresh_tokens.find_one({"token_hash": token_hash})

    if not record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not found",
        )

    now = _utc_now()
    if record.get("revoked_at"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked",
        )
    if record["expires_at"] < now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired",
        )

    admin_id = token_payload.get("sub")
    email = token_payload.get("email")
    admin = await db.admins.find_one({"id": admin_id, "email": email, "is_active": True})
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin account not found",
        )

    await db.refresh_tokens.update_one(
        {"token_hash": token_hash},
        {"$set": {"revoked_at": now, "updated_at": now}},
    )
    tokens = await _issue_auth_tokens(admin, now)

    return {
        "message": "Token refreshed successfully",
        **tokens,
    }
