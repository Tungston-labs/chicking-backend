from datetime import datetime
from enum import Enum
from typing import Optional

from app.constants.blog_defaults import normalize_category, normalize_read_time
from pydantic import AliasChoices, BaseModel, ConfigDict, EmailStr, Field, field_validator


class BlogStatus(str, Enum):
    DRAFT = "Draft"
    PUBLISHED = "Published"
    TRASH = "Trash"


class CommentStatus(str, Enum):
    PENDING = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"


def _parse_frontend_datetime(value: str) -> datetime:
    return datetime.strptime(value, "%b %d, %Y %I:%M %p")


class BlogCreateSchema(BaseModel):
    id: Optional[str] = None
    title: str
    excerpt: str
    content: str
    category: str
    author: str = "Robert Pattinson"
    author_role: str = Field(
        default="Super Admin",
        validation_alias=AliasChoices("authorRole", "author_role"),
    )
    image: Optional[str] = None
    is_video: bool = Field(
        default=False,
        validation_alias=AliasChoices("isVideo", "is_video"),
    )
    url: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("url", "featuredVideo", "featured_video"),
    )
    published_at: Optional[datetime] = Field(
        default=None,
        validation_alias=AliasChoices("publishedAt", "published_at"),
    )
    read_time: str = Field(
        default="2 min Read",
        validation_alias=AliasChoices("readTime", "read_time"),
    )
    status: BlogStatus = BlogStatus.DRAFT
    views: int = Field(default=0, ge=0)

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, value: str | BlogStatus) -> BlogStatus:
        if isinstance(value, BlogStatus):
            return value

        normalized = str(value).strip().lower()
        mapping = {
            "draft": BlogStatus.DRAFT,
            "published": BlogStatus.PUBLISHED,
            "trash": BlogStatus.TRASH,
        }
        if normalized not in mapping:
            raise ValueError("Status must be Draft, Published, or Trash")
        return mapping[normalized]

    @field_validator("published_at", mode="before")
    @classmethod
    def parse_published_at(cls, value: object) -> object:
        if value in (None, "", "---"):
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return _parse_frontend_datetime(value)
            except ValueError:
                return value
        return value

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category_value(cls, value: object) -> str:
        return normalize_category(value)

    @field_validator("read_time", mode="before")
    @classmethod
    def normalize_read_time_value(cls, value: object) -> str:
        return normalize_read_time(value)


class BlogUpdateSchema(BaseModel):
    title: Optional[str] = None
    excerpt: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    author: Optional[str] = None
    author_role: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("authorRole", "author_role"),
    )
    image: Optional[str] = None
    is_video: Optional[bool] = Field(
        default=None,
        validation_alias=AliasChoices("isVideo", "is_video"),
    )
    url: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("url", "featuredVideo", "featured_video"),
    )
    published_at: Optional[datetime] = Field(
        default=None,
        validation_alias=AliasChoices("publishedAt", "published_at"),
    )
    read_time: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("readTime", "read_time"),
    )
    status: Optional[BlogStatus] = None
    views: Optional[int] = Field(default=None, ge=0)

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, value: str | BlogStatus | None) -> BlogStatus | None:
        if value is None or isinstance(value, BlogStatus):
            return value
        normalized = str(value).strip().lower()
        mapping = {
            "draft": BlogStatus.DRAFT,
            "published": BlogStatus.PUBLISHED,
            "trash": BlogStatus.TRASH,
        }
        if normalized not in mapping:
            raise ValueError("Status must be Draft, Published, or Trash")
        return mapping[normalized]

    @field_validator("published_at", mode="before")
    @classmethod
    def parse_published_at(cls, value: object) -> object:
        if value in (None, "", "---"):
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return _parse_frontend_datetime(value)
            except ValueError:
                return value
        return value

    @field_validator("category", mode="before")
    @classmethod
    def normalize_category_value(cls, value: object) -> object:
        if value is None:
            return value
        return normalize_category(value)

    @field_validator("read_time", mode="before")
    @classmethod
    def normalize_read_time_value(cls, value: object) -> object:
        if value is None:
            return value
        return normalize_read_time(value)


class PublicCommentCreateSchema(BaseModel):
    name: str
    email: EmailStr
    message: str = Field(min_length=3)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return value.lower()


class CommentModerationSchema(BaseModel):
    status: CommentStatus
