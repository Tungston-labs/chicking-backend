from datetime import datetime
from typing import Any

from app.constants.blog_defaults import (
    DEFAULT_AUTHOR,
    DEFAULT_AUTHOR_ROLE,
    DEFAULT_BLOG_STATUS,
    DEFAULT_BLOG_TITLE,
    build_excerpt,
    normalize_category,
    normalize_read_time,
    normalize_text_content,
)
from app.utils.upload import normalize_image_value


def format_date(value: datetime | str | None) -> str:
    if value is None:
        return "---"
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value
    return value.strftime("%b %d, %Y")


def format_datetime(value: datetime | str | None) -> str:
    if value is None:
        return "---"
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return value
    return value.strftime("%b %d, %Y %I:%M %p")


def _to_iso(value: datetime | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return value.isoformat()


def serialize_comment_reply(
    reply: dict[str, Any] | None,
    include_admin_email: bool = False,
) -> dict[str, Any] | None:
    if not isinstance(reply, dict):
        return None

    message = str(reply.get("message") or "").strip()
    if not message:
        return None

    created_at = reply.get("created_at")
    updated_at = reply.get("updated_at")
    payload = {
        "message": message,
        "adminName": str(reply.get("admin_name") or "").strip() or DEFAULT_AUTHOR,
        "createdAt": _to_iso(created_at),
        "updatedAt": _to_iso(updated_at),
    }
    if include_admin_email and reply.get("admin_email"):
        payload["adminEmail"] = reply["admin_email"]
    return payload


def serialize_blog(
    blog: Any,
    comments_count: int = 0,
    pending_comments: int = 0,
) -> dict[str, Any]:
    blog_dict = blog.to_dict() if hasattr(blog, "to_dict") else blog
    published_at = blog_dict.get("published_at")
    fallback_date = published_at or blog_dict.get("created_at")
    blog_id = str(blog_dict.get("id") or blog_dict.get("_id") or "")
    title = str(blog_dict.get("title") or "").strip() or DEFAULT_BLOG_TITLE

    return {
        "id": blog_id,
        "title": title,
        "excerpt": build_excerpt(blog_dict),
        "content": normalize_text_content(blog_dict.get("content")),
        "author": str(blog_dict.get("author") or "").strip() or DEFAULT_AUTHOR,
        "authorRole": str(blog_dict.get("author_role") or "").strip() or DEFAULT_AUTHOR_ROLE,
        "category": normalize_category(blog_dict.get("category")),
        "image": normalize_image_value(blog_dict.get("image")),
        "isVideo": bool(blog_dict.get("is_video", False)),
        "url": blog_dict.get("url"),
        "slug": str(blog_dict.get("slug") or "").strip(),
        "status": str(blog_dict.get("status") or "").strip() or DEFAULT_BLOG_STATUS,
        "date": format_date(fallback_date),
        "publishedAt": format_datetime(published_at),
        "readTime": normalize_read_time(blog_dict.get("read_time")),
        "views": blog_dict.get("views", 0),
        "comments": comments_count,
        "pendingComments": pending_comments,
        "createdAt": _to_iso(blog_dict.get("created_at")),
        "updatedAt": _to_iso(blog_dict.get("updated_at")),
    }


def serialize_comment(comment: Any, include_email: bool = False) -> dict[str, Any]:
    comment_dict = comment.to_dict() if hasattr(comment, "to_dict") else comment
    created_at = comment_dict.get("created_at")
    updated_at = comment_dict.get("updated_at")
    payload = {
        "id": comment_dict["id"],
        "blogId": comment_dict["blog_id"],
        "name": comment_dict["name"],
        "message": comment_dict["message"],
        "status": comment_dict["status"],
        "createdAt": _to_iso(created_at),
        "updatedAt": _to_iso(updated_at),
        "reply": serialize_comment_reply(comment_dict.get("reply"), include_admin_email=include_email),
    }
    if include_email:
        payload["email"] = comment_dict["email"]
    return payload
