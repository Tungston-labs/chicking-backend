import re
from typing import Any

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING, DESCENDING

from app.constants.blog_defaults import (
    DEFAULT_AUTHOR,
    DEFAULT_AUTHOR_ROLE,
    DEFAULT_READ_TIME,
    build_excerpt,
    normalize_category,
    normalize_read_time,
)
from app.config.settings import get_settings
from app.utils.slug import slugify
from app.utils.upload import store_blog_image


load_dotenv()

settings = get_settings()


client = AsyncIOMotorClient(settings.mongo_url)
db = client[settings.database_name]


def _extract_numeric_suffix(value: str | None, prefix: str) -> int | None:
    if not value:
        return None
    match = re.fullmatch(rf"{re.escape(prefix)}-(\d+)", value)
    if not match:
        return None
    return int(match.group(1))


async def _next_legacy_identifier(
    collection_name: str,
    field_name: str,
    prefix: str,
    used_values: set[str],
) -> str:
    collection = getattr(db, collection_name)
    max_value = 0

    async for doc in collection.find(
        {field_name: {"$type": "string"}},
        {field_name: 1},
    ):
        numeric = _extract_numeric_suffix(doc.get(field_name), prefix)
        if numeric:
            max_value = max(max_value, numeric)

    next_value = max_value + 1
    candidate = f"{prefix}-{next_value:03d}"
    while candidate in used_values:
        next_value += 1
        candidate = f"{prefix}-{next_value:03d}"
    used_values.add(candidate)
    return candidate


async def _generate_unique_slug_for_existing_blog(
    title: str | None,
    used_slugs: set[str],
) -> str:
    base_slug = slugify(title or "blog")
    candidate = base_slug
    counter = 2

    while candidate in used_slugs:
        candidate = f"{base_slug}-{counter}"
        counter += 1

    used_slugs.add(candidate)
    return candidate


async def _normalize_existing_blogs() -> None:
    used_ids: set[str] = set()
    used_slugs: set[str] = set()

    async for blog in db.blogs.find({}, {"id": 1, "slug": 1}):
        blog_id = blog.get("id")
        slug = blog.get("slug")
        if isinstance(blog_id, str) and blog_id:
            used_ids.add(blog_id)
        if isinstance(slug, str) and slug:
            used_slugs.add(slug)

    async for blog in db.blogs.find({}):
        updates: dict[str, Any] = {}
        legacy_id = blog.get("id")
        if not isinstance(legacy_id, str) or not legacy_id.strip():
            updates["id"] = await _next_legacy_identifier("blogs", "id", "blog", used_ids)
        else:
            used_ids.add(legacy_id)

        slug = blog.get("slug")
        if not isinstance(slug, str) or not slug.strip():
            updates["slug"] = await _generate_unique_slug_for_existing_blog(blog.get("title"), used_slugs)
        else:
            used_slugs.add(slug)

        status = blog.get("status")
        if isinstance(status, str):
            normalized_status = status.strip().title()
            if normalized_status in {"Draft", "Published", "Trash"} and normalized_status != status:
                updates["status"] = normalized_status

        if "views" not in blog or blog.get("views") is None:
            updates["views"] = 0
        if "author" not in blog or not blog.get("author"):
            updates["author"] = DEFAULT_AUTHOR
        if "author_role" not in blog or not blog.get("author_role"):
            updates["author_role"] = DEFAULT_AUTHOR_ROLE
        if "category" not in blog or not str(blog.get("category") or "").strip():
            updates["category"] = normalize_category(blog.get("category"))
        elif normalize_category(blog.get("category")) != blog.get("category"):
            updates["category"] = normalize_category(blog.get("category"))
        if "read_time" not in blog or not blog.get("read_time"):
            updates["read_time"] = DEFAULT_READ_TIME
        elif normalize_read_time(blog.get("read_time")) != blog.get("read_time"):
            updates["read_time"] = normalize_read_time(blog.get("read_time"))
        if isinstance(blog.get("image"), str):
            normalized_image = store_blog_image(blog.get("image"), updates.get("id") or blog.get("id"))
            if normalized_image != blog.get("image"):
                updates["image"] = normalized_image
        if "is_video" not in blog:
            updates["is_video"] = False
        if "excerpt" not in blog or not str(blog.get("excerpt") or "").strip():
            updates["excerpt"] = build_excerpt(blog)
        if "updated_at" not in blog:
            updates["updated_at"] = blog.get("created_at")

        if updates:
            await db.blogs.update_one({"_id": blog["_id"]}, {"$set": updates})


async def _normalize_existing_comments() -> None:
    used_ids: set[str] = set()

    async for comment in db.comments.find({}, {"id": 1}):
        comment_id = comment.get("id")
        if isinstance(comment_id, str) and comment_id:
            used_ids.add(comment_id)

    async for comment in db.comments.find({}):
        updates: dict[str, Any] = {}
        comment_id = comment.get("id")
        if not isinstance(comment_id, str) or not comment_id.strip():
            updates["id"] = await _next_legacy_identifier("comments", "id", "cmt", used_ids)

        status = comment.get("status")
        if isinstance(status, str):
            normalized_status = status.strip().title()
            if normalized_status in {"Pending", "Approved", "Rejected"} and normalized_status != status:
                updates["status"] = normalized_status

        if "updated_at" not in comment:
            updates["updated_at"] = comment.get("created_at")

        if updates:
            await db.comments.update_one({"_id": comment["_id"]}, {"$set": updates})


async def _normalize_existing_admins() -> None:
    used_ids: set[str] = set()

    async for admin in db.admins.find({}, {"id": 1}):
        admin_id = admin.get("id")
        if isinstance(admin_id, str) and admin_id:
            used_ids.add(admin_id)

    async for admin in db.admins.find({}):
        updates: dict[str, Any] = {}
        admin_id = admin.get("id")
        if not isinstance(admin_id, str) or not admin_id.strip():
            updates["id"] = await _next_legacy_identifier("admins", "id", "admin", used_ids)

        if "is_active" not in admin:
            updates["is_active"] = True

        if updates:
            await db.admins.update_one({"_id": admin["_id"]}, {"$set": updates})


async def migrate_legacy_documents() -> None:
    await _normalize_existing_admins()
    await _normalize_existing_blogs()
    await _normalize_existing_comments()


async def _ensure_index(
    collection_name: str,
    keys: str | list[tuple[str, int]],
    name: str,
    **kwargs: Any,
) -> None:
    collection = getattr(db, collection_name)
    index_information = await collection.index_information()
    existing = index_information.get(name)
    expected_keys = [(keys, ASCENDING)] if isinstance(keys, str) else keys

    if existing:
        same_keys = existing.get("key") == expected_keys
        same_unique = bool(existing.get("unique")) == bool(kwargs.get("unique"))
        same_partial = existing.get("partialFilterExpression") == kwargs.get("partialFilterExpression")
        same_expire = existing.get("expireAfterSeconds") == kwargs.get("expireAfterSeconds")
        if not (same_keys and same_unique and same_partial and same_expire):
            await collection.drop_index(name)

    await collection.create_index(keys, name=name, **kwargs)


async def ensure_indexes() -> None:
    await migrate_legacy_documents()

    await _ensure_index(
        "admins",
        "email",
        "email_1",
        unique=True,
        partialFilterExpression={"email": {"$type": "string"}},
    )
    await _ensure_index(
        "admins",
        "id",
        "id_1",
        unique=True,
        partialFilterExpression={"id": {"$type": "string"}},
    )
    await _ensure_index(
        "blogs",
        "id",
        "id_1",
        unique=True,
        partialFilterExpression={"id": {"$type": "string"}},
    )
    await _ensure_index(
        "blogs",
        "slug",
        "slug_1",
        unique=True,
        partialFilterExpression={"slug": {"$type": "string"}},
    )
    await _ensure_index("blogs", "status", "status_1")
    await _ensure_index("blogs", "category", "category_1")
    await _ensure_index("blogs", "published_at", "published_at_1")
    await _ensure_index(
        "blogs",
        [("status", ASCENDING), ("published_at", DESCENDING)],
        "status_1_published_at_-1",
    )
    await _ensure_index(
        "blogs",
        [("status", ASCENDING), ("category", ASCENDING), ("published_at", DESCENDING)],
        "status_1_category_1_published_at_-1",
    )
    await _ensure_index(
        "comments",
        "id",
        "id_1",
        unique=True,
        partialFilterExpression={"id": {"$type": "string"}},
    )
    await _ensure_index("comments", [("blog_id", ASCENDING), ("created_at", ASCENDING)], "blog_id_1_created_at_1")
    await _ensure_index("comments", "status", "status_1")
    await _ensure_index(
        "comments",
        [("blog_id", ASCENDING), ("status", ASCENDING)],
        "blog_id_1_status_1",
    )
    await _ensure_index("password_reset_otps", "email", "email_1")
    await _ensure_index(
        "password_reset_otps",
        "expires_at",
        "expires_at_1",
        expireAfterSeconds=0,
    )
    await _ensure_index(
        "refresh_tokens",
        "token_hash",
        "token_hash_1",
        unique=True,
        partialFilterExpression={"token_hash": {"$type": "string"}},
    )
    await _ensure_index("refresh_tokens", "admin_id", "admin_id_1")
    await _ensure_index(
        "refresh_tokens",
        "expires_at",
        "expires_at_1",
        expireAfterSeconds=0,
    )
    await _ensure_index(
        "counters",
        "key",
        "key_1",
        unique=True,
        partialFilterExpression={"key": {"$type": "string"}},
    )
