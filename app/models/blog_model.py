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


def format_date(value: datetime | None) -> str:
    if value is None:
        return "---"
    return value.strftime("%b %d, %Y")


def format_datetime(value: datetime | None) -> str:
    if value is None:
        return "---"
    return value.strftime("%b %d, %Y %I:%M %p")


def serialize_blog(
    blog: dict[str, Any],
    comments_count: int = 0,
    pending_comments: int = 0,
) -> dict[str, Any]:
    published_at = blog.get("published_at")
    fallback_date = published_at or blog.get("created_at")
    blog_id = str(blog.get("id") or blog.get("_id") or "")
    title = str(blog.get("title") or "").strip() or DEFAULT_BLOG_TITLE

    return {
        "id": blog_id,
        "title": title,
        "excerpt": build_excerpt(blog),
        "content": normalize_text_content(blog.get("content")),
        "author": str(blog.get("author") or "").strip() or DEFAULT_AUTHOR,
        "authorRole": str(blog.get("author_role") or "").strip() or DEFAULT_AUTHOR_ROLE,
        "category": normalize_category(blog.get("category")),
        "image": blog.get("image"),
        "isVideo": blog.get("is_video", False),
        "url": blog.get("url"),
        "slug": str(blog.get("slug") or "").strip(),
        "status": str(blog.get("status") or "").strip() or DEFAULT_BLOG_STATUS,
        "date": format_date(fallback_date),
        "publishedAt": format_datetime(published_at),
        "readTime": normalize_read_time(blog.get("read_time")),
        "views": blog.get("views", 0),
        "comments": comments_count,
        "pendingComments": pending_comments,
        "createdAt": blog.get("created_at").isoformat() if blog.get("created_at") else None,
        "updatedAt": blog.get("updated_at").isoformat() if blog.get("updated_at") else None,
    }


def serialize_comment(comment: dict[str, Any], include_email: bool = False) -> dict[str, Any]:
    payload = {
        "id": comment["id"],
        "blogId": comment["blog_id"],
        "name": comment["name"],
        "message": comment["message"],
        "status": comment["status"],
        "createdAt": comment["created_at"].isoformat(),
        "updatedAt": comment["updated_at"].isoformat(),
    }
    if include_email:
        payload["email"] = comment["email"]
    return payload
