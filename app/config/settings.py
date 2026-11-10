import os
from functools import lru_cache
from typing import Optional
from urllib.parse import quote_plus

from dotenv import load_dotenv
from pydantic import BaseModel, Field


load_dotenv()


class Settings(BaseModel):
    app_name: str = "Chicking CMS API"

    # MySQL connection configuration
    mysql_url: Optional[str] = Field(default=None, alias="MYSQL_URL")
    database_url: Optional[str] = Field(default=None, alias="DATABASE_URL")
    mysql_host: str = Field(default="localhost", alias="MYSQL_HOST")
    mysql_port: int = Field(default=3306, alias="MYSQL_PORT")
    mysql_user: str = Field(default="root", alias="MYSQL_USER")
    mysql_password: str = Field(default="", alias="MYSQL_PASSWORD")
    mysql_database: str = Field(default="chicking_cms", alias="MYSQL_DATABASE")
    mysql_charset: str = Field(default="utf8mb4", alias="MYSQL_CHARSET")

    # Legacy MongoDB fields preserved for backwards compatibility / migration
    mongo_url: Optional[str] = Field(default=None, alias="MONGO_URL")
    database_name: Optional[str] = Field(default=None, alias="DATABASE_NAME")

    # App & Security settings
    public_base_url: str = Field(default="http://178.248.112.5", alias="PUBLIC_BASE_URL")
    jwt_secret: str = Field(default="chicking-cms-secret-key-change-in-production", alias="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(default=1440, alias="JWT_EXPIRE_MINUTES")
    refresh_token_expire_days: int = Field(default=30, alias="REFRESH_TOKEN_EXPIRE_DAYS")
    reset_token_expire_minutes: int = 30
    otp_expire_minutes: int = 10
    otp_length: int = 6

    # SMTP / Email settings
    smtp_host: Optional[str] = Field(default=None, alias="EMAIL_HOST")
    smtp_port: int = Field(default=587, alias="EMAIL_PORT")
    smtp_username: Optional[str] = Field(default=None, alias="EMAIL_HOST_USER")
    smtp_password: Optional[str] = Field(default=None, alias="EMAIL_HOST_PASSWORD")
    smtp_use_tls: bool = Field(default=True, alias="EMAIL_USE_TLS")
    smtp_timeout_seconds: int = Field(default=30, alias="EMAIL_TIMEOUT_SECONDS")
    email_from: Optional[str] = Field(default=None, alias="EMAIL_FROM")
    email_from_name: str = Field(default="Chicking CMS", alias="EMAIL_FROM_NAME")
    franchise_enquiry_recipient: Optional[str] = Field(default=None, alias="FRANCHISE_ENQUIRY_RECIPIENT")

    def get_database_url(self) -> str:
        """
        Builds or normalizes the async SQLAlchemy database URL.
        Supports MySQL (aiomysql driver) and falls back to URL provided in env.
        """
        raw_url = self.database_url or self.mysql_url
        if raw_url:
            raw_url = raw_url.strip()
            # Convert standard synchronous or alternate drivers to async drivers
            if raw_url.startswith("mysql://"):
                return raw_url.replace("mysql://", "mysql+aiomysql://", 1)
            if raw_url.startswith("mysql+pymysql://"):
                return raw_url.replace("mysql+pymysql://", "mysql+aiomysql://", 1)
            if raw_url.startswith("sqlite://") and not raw_url.startswith("sqlite+aiosqlite://"):
                return raw_url.replace("sqlite://", "sqlite+aiosqlite://", 1)
            return raw_url

        # Build from discrete MySQL environment variables
        user = quote_plus(self.mysql_user)
        pwd = quote_plus(self.mysql_password) if self.mysql_password else ""
        auth = f"{user}:{pwd}" if pwd else user
        return f"mysql+aiomysql://{auth}@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}?charset={self.mysql_charset}"


@lru_cache
def get_settings() -> Settings:
    return Settings.model_validate(os.environ)
