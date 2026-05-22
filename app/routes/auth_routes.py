from fastapi import APIRouter, Depends

from app.middleware.jwt_auth import get_current_admin_profile
from app.schemas.auth_schema import (
    ForgotPasswordRequestSchema,
    LoginRequestSchema,
    RefreshTokenRequestSchema,
    ResetPasswordRequestSchema,
    VerifyOtpRequestSchema,
)
from app.services.auth_service import (
    forgot_password,
    login_admin,
    refresh_access_token,
    reset_password,
    verify_reset_otp,
)

router = APIRouter(
    prefix="/auth",
    tags=["Auth"]
)


@router.post("/login")
async def login(payload: LoginRequestSchema):
    return await login_admin(payload)


@router.post("/forgot-password")
async def forgot_password_request(payload: ForgotPasswordRequestSchema):
    return await forgot_password(payload)


@router.post("/verify-otp")
async def verify_otp(payload: VerifyOtpRequestSchema):
    return await verify_reset_otp(payload)


@router.post("/reset-password")
async def reset_password_request(payload: ResetPasswordRequestSchema):
    return await reset_password(payload)


@router.post("/refresh-token")
async def refresh_token_request(payload: RefreshTokenRequestSchema):
    return await refresh_access_token(payload)


@router.get("/me")
async def get_me(admin: dict = Depends(get_current_admin_profile)):
    return admin
