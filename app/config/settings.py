import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import BaseModel, Field


load_dotenv()


class Settings(BaseModel):
    app_name: str = "Chicking CMS API"
    mongo_url: str = Field(alias="MONGO_URL")
    database_name: str = Field(alias="DATABASE_NAME")
    jwt_secret: str = Field(alias="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(default=1440, alias="JWT_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=30, alias="REFRESH_TOKEN_EXPIRE_DAYS")
    reset_token_expire_minutes: int = 30
    otp_expire_minutes: int = 10
    otp_length: int = 6
    smtp_host: str | None = Field(default=None, alias="EMAIL_HOST")
    smtp_port: int = Field(default=587, alias="EMAIL_PORT")
    smtp_username: str | None = Field(default=None, alias="EMAIL_HOST_USER")
    smtp_password: str | None = Field(default=None, alias="EMAIL_HOST_PASSWORD")
    smtp_use_tls: bool = Field(default=True, alias="EMAIL_USE_TLS")
    smtp_timeout_seconds: int = Field(default=30, alias="EMAIL_TIMEOUT_SECONDS")
    email_from: str | None = Field(default=None, alias="EMAIL_FROM")
    email_from_name: str = Field(default="Chicking CMS", alias="EMAIL_FROM_NAME")


@lru_cache
def get_settings() -> Settings:
    return Settings.model_validate(os.environ)
