from datetime import datetime
from math import ceil
from typing import Any

from fastapi import HTTPException, status
from pymongo import ReturnDocument

from app.config.database import db
from app.models.blog_model import serialize_blog, serialize_comment
from app.models.category_model import serialize_category
from app.schemas.blog_schema import BlogStatus, CommentStatus
from app.utils.slug import slugify
from app.utils.upload import store_blog_image


PUBLIC_BLOG_LIST_PROJECTION = {
    "id": 1,
    "title": 1,
    "excerpt": 1,
    "author": 1,
    "author_role": 1,
    "category": 1,
    "image": 1,
    "is_video": 1,
    "url": 1,
    "slug": 1,
    "status": 1,
    "published_at": 1,
    "read_time": 1,
    "views": 1,
    "created_at": 1,
    "updated_at": 1,
}


def _utc_now() -> datetime:
    return datetime.utcnow()


def _normalize_page_size(page_size: int | None, default: int = 10, maximum: int = 100) -> int:
    if page_size is None:
        return default
    return max(1, min(page_size, maximum))


async def _next_sequence(key: str, prefix: str) -> str:
    counter = await db.counters.find_one_and_update(
        {"key": key},
        {"$inc": {"value": 1}, "$setOnInsert": {"key": key}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return f"{prefix}-{counter['value']:03d}"


async def _generate_unique_slug(title: str, exclude_blog_id: str | None = None) -> str:
    base_slug = slugify(title)
    candidate = base_slug
    counter = 2

    while True:
        query: dict[str, Any] = {"slug": candidate}
        if exclude_blog_id:
            query["id"] = {"$ne": exclude_blog_id}
        existing = await db.blogs.find_one(query)
        if not existing:
            return candidate
        candidate = f"{base_slug}-{counter}"
        counter += 1


async def _ensure_blog_exists(blog_id: str, allow_unpublished: bool = True) -> dict[str, Any]:
    query: dict[str, Any] = {"id": blog_id}
    if not allow_unpublished:
        query["status"] = BlogStatus.PUBLISHED.value
    blog = await db.blogs.find_one(query)
    if not blog:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog not found")
    return blog


async def _comment_counts(blog_ids: list[str], status_filter: str | None = None) -> dict[str, int]:
    if not blog_ids:
        return {}

    match: dict[str, Any] = {"blog_id": {"$in": blog_ids}}
    if status_filter:
        match["status"] = status_filter

    pipeline = [
        {"$match": match},
        {"$group": {"_id": "$blog_id", "count": {"$sum": 1}}},
    ]
    counts: dict[str, int] = {}
    async for item in db.comments.aggregate(pipeline):
        counts[item["_id"]] = item["count"]
    return counts


async def create_blog(blog: Any) -> dict[str, Any]:
    blog_dict = blog.model_dump(exclude_none=True)
    now = _utc_now()
    requested_id = blog_dict.get("id")
    if requested_id:
        blog_id = requested_id
        existing = await db.blogs.find_one({"id": blog_id})
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Blog id already exists")
    else:
        while True:
            blog_id = await _next_sequence("blogs", "blog")
            existing = await db.blogs.find_one({"id": blog_id})
            if not existing:
                break

    status_value = blog_dict["status"].value if hasattr(blog_dict["status"], "value") else blog_dict["status"]
    published_at = blog_dict.get("published_at")
    if status_value == BlogStatus.PUBLISHED.value and published_at is None:
        published_at = now

    blog_payload = {
        **blog_dict,
        "id": blog_id,
        "status": status_value,
        "slug": await _generate_unique_slug(blog_dict["title"]),
        "published_at": published_at,
        "created_at": now,
        "updated_at": now,
    }
    if "image" in blog_payload:
        blog_payload["image"] = store_blog_image(blog_payload.get("image"), blog_id)

    await db.blogs.insert_one(blog_payload)

    return {
        "message": "Blog created successfully",
        "blog": serialize_blog(blog_payload),
    }


async def list_admin_blogs(
    status_filter: str | None = None,
    category: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> list[dict[str, Any]] | dict[str, Any]:
    query: dict[str, Any] = {}
    if status_filter:
        query["status"] = status_filter.title()
    if category:
        query["category"] = category

    use_pagination = page is not None or page_size is not None
    cursor = db.blogs.find(query).sort("created_at", -1)
    total_blogs = await db.blogs.count_documents(query) if use_pagination else None

    if use_pagination:
        resolved_page = max(page or 1, 1)
        resolved_page_size = _normalize_page_size(page_size)
        blogs = await cursor.skip((resolved_page - 1) * resolved_page_size).limit(resolved_page_size).to_list(
            length=resolved_page_size
        )
    else:
        resolved_page = None
        resolved_page_size = None
        blogs = await cursor.to_list(length=None)

    ids = [str(blog.get("id")) for blog in blogs if blog.get("id")]
    total_comments = await _comment_counts(ids)
    pending_comments = await _comment_counts(ids, status_filter=CommentStatus.PENDING.value)
    items: list[dict[str, Any]] = []

    for blog in blogs:
        blog_id = str(blog.get("id") or "")
        items.append(
            serialize_blog(
                blog,
                comments_count=total_comments.get(blog_id, 0),
                pending_comments=pending_comments.get(blog_id, 0),
            )
        )

    if not use_pagination:
        return items

    total_items = total_blogs or 0
    total_pages = ceil(total_items / resolved_page_size) if total_items else 0
    return {
        "items": items,
        "pagination": {
            "page": resolved_page,
            "pageSize": resolved_page_size,
            "totalItems": total_items,
            "totalPages": total_pages,
            "hasNext": resolved_page < total_pages,
            "hasPrevious": resolved_page > 1,
        },
    }


async def get_admin_blog(blog_id: str) -> dict[str, Any]:
    blog = await _ensure_blog_exists(blog_id)
    total_comments = await db.comments.count_documents({"blog_id": blog_id})
    pending_comments = await db.comments.count_documents(
        {"blog_id": blog_id, "status": CommentStatus.PENDING.value}
    )
    return serialize_blog(blog, comments_count=total_comments, pending_comments=pending_comments)


async def update_blog(blog_id: str, payload: Any) -> dict[str, Any]:
    blog = await _ensure_blog_exists(blog_id)
    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        return {"message": "No changes submitted", "blog": serialize_blog(blog)}

    now = _utc_now()
    if "title" in update_data and update_data["title"]:
        update_data["slug"] = await _generate_unique_slug(update_data["title"], exclude_blog_id=blog_id)
    if "image" in update_data:
        update_data["image"] = store_blog_image(update_data.get("image"), blog_id)
    if "status" in update_data and update_data["status"] is not None:
        update_data["status"] = update_data["status"].value
        if update_data["status"] == BlogStatus.PUBLISHED.value and not update_data.get("published_at"):
            update_data["published_at"] = blog.get("published_at") or now

    update_data["updated_at"] = now

    updated_blog = await db.blogs.find_one_and_update(
        {"id": blog_id},
        {"$set": update_data},
        return_document=ReturnDocument.AFTER,
    )
    total_comments = await db.comments.count_documents({"blog_id": blog_id})
    pending_comments = await db.comments.count_documents(
        {"blog_id": blog_id, "status": CommentStatus.PENDING.value}
    )

    return {
        "message": "Blog updated successfully",
        "blog": serialize_blog(updated_blog, comments_count=total_comments, pending_comments=pending_comments),
    }


async def delete_blog(blog_id: str) -> dict[str, str]:
    result = await db.blogs.delete_one({"id": blog_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Blog not found")
    await db.comments.delete_many({"blog_id": blog_id})
    return {"message": "Blog deleted successfully"}


async def list_public_blogs(
    category: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
    include_content: bool = False,
) -> list[dict[str, Any]] | dict[str, Any]:
    query: dict[str, Any] = {"status": BlogStatus.PUBLISHED.value}
    if category:
        query["category"] = category

    projection = dict(PUBLIC_BLOG_LIST_PROJECTION)
    if include_content:
        projection["content"] = 1

    use_pagination = page is not None or page_size is not None
    cursor = db.blogs.find(query, projection).sort("published_at", -1)
    total_blogs = await db.blogs.count_documents(query) if use_pagination else None

    if use_pagination:
        resolved_page = max(page or 1, 1)
        resolved_page_size = _normalize_page_size(page_size)
        blogs = await cursor.skip((resolved_page - 1) * resolved_page_size).limit(resolved_page_size).to_list(
            length=resolved_page_size
        )
    else:
        resolved_page = None
        resolved_page_size = None
        blogs = await cursor.to_list(length=None)

    ids = [str(blog.get("id")) for blog in blogs if blog.get("id")]
    comment_counts = await _comment_counts(ids, status_filter=CommentStatus.APPROVED.value)

    items = [
        serialize_blog(
            blog,
            comments_count=comment_counts.get(str(blog.get("id") or ""), 0),
            include_content=include_content,
        )
        for blog in blogs
    ]

    if not use_pagination:
        return items

    total_items = total_blogs or 0
    total_pages = ceil(total_items / resolved_page_size) if total_items else 0
    return {
        "items": items,
        "pagination": {
            "page": resolved_page,
            "pageSize": resolved_page_size,
            "totalItems": total_items,
            "totalPages": total_pages,
            "hasNext": resolved_page < total_pages,
            "hasPrevious": resolved_page > 1,
        },
    }


async def get_public_blog(blog_id: str) -> dict[str, Any]:
    blog = await _ensure_blog_exists(blog_id, allow_unpublished=False)
    await db.blogs.update_one({"id": blog_id}, {"$inc": {"views": 1}})
    blog["views"] = blog.get("views", 0) + 1
    comments_count = await db.comments.count_documents(
        {"blog_id": blog_id, "status": CommentStatus.APPROVED.value}
    )
    return serialize_blog(blog, comments_count=comments_count)


async def create_public_comment(blog_id: str, payload: Any) -> dict[str, Any]:
    await _ensure_blog_exists(blog_id, allow_unpublished=False)
    now = _utc_now()
    comment_payload = {
        **payload.model_dump(),
        "id": await _next_sequence("comments", "cmt"),
        "blog_id": blog_id,
        "status": CommentStatus.PENDING.value,
        "created_at": now,
        "updated_at": now,
    }
    await db.comments.insert_one(comment_payload)
    return {
        "message": "Comment submitted successfully and is pending review",
        "comment": serialize_comment(comment_payload),
    }


async def list_public_comments(blog_id: str) -> list[dict[str, Any]]:
    await _ensure_blog_exists(blog_id, allow_unpublished=False)
    comments = await db.comments.find(
        {"blog_id": blog_id, "status": CommentStatus.APPROVED.value}
    ).sort("created_at", -1).to_list(length=None)
    return [serialize_comment(comment) for comment in comments]


async def list_admin_comments(blog_id: str) -> list[dict[str, Any]]:
    await _ensure_blog_exists(blog_id)
    comments = await db.comments.find({"blog_id": blog_id}).sort("created_at", -1).to_list(length=None)
    return [serialize_comment(comment, include_email=True) for comment in comments]


async def moderate_comment(blog_id: str, comment_id: str, payload: Any) -> dict[str, Any]:
    await _ensure_blog_exists(blog_id)
    updated = await db.comments.find_one_and_update(
        {"blog_id": blog_id, "id": comment_id},
        {"$set": {"status": payload.status.value, "updated_at": _utc_now()}},
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    return {
        "message": "Comment status updated successfully",
        "comment": serialize_comment(updated, include_email=True),
    }


async def delete_comment(blog_id: str, comment_id: str) -> dict[str, str]:
    await _ensure_blog_exists(blog_id)
    result = await db.comments.delete_one({"blog_id": blog_id, "id": comment_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    return {"message": "Comment deleted successfully"}


async def list_public_categories() -> list[dict[str, Any]]:
    pipeline = [
        {"$match": {"status": BlogStatus.PUBLISHED.value}},
        {"$match": {"category": {"$type": "string", "$ne": ""}}},
        {"$group": {"_id": "$category", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]
    categories: list[dict[str, Any]] = []
    async for item in db.blogs.aggregate(pipeline):
        categories.append(serialize_category(item["_id"], item["count"]))
    return categories
