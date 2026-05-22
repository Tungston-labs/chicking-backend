from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class LoginRequestSchema(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return value.lower()


class ForgotPasswordRequestSchema(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return value.lower()


class VerifyOtpRequestSchema(BaseModel):
    email: EmailStr
    otp: str = Field(min_length=4, max_length=8)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return value.lower()


class ResetPasswordRequestSchema(BaseModel):
    reset_token: str = Field(alias="resetToken")
    new_password: str = Field(alias="newPassword", min_length=8)

    model_config = ConfigDict(populate_by_name=True)


class RefreshTokenRequestSchema(BaseModel):
    refresh_token: str = Field(alias="refreshToken", min_length=1)

    model_config = ConfigDict(populate_by_name=True)
