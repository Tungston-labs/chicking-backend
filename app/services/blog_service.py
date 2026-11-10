from datetime import datetime
from math import ceil
import re
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import get_db_session
from app.constants.blog_defaults import (
    DEFAULT_AUTHOR,
    DEFAULT_AUTHOR_ROLE,
    DEFAULT_BLOG_TITLE,
    DEFAULT_READ_TIME,
    normalize_category,
    normalize_read_time,
)
from app.models.blog_model import serialize_blog, serialize_comment
from app.models.category_model import serialize_category
from app.models.entities import Blog, Comment, Counter
from app.schemas.blog_schema import BlogStatus, CommentStatus
from app.utils.slug import slugify
from app.utils.upload import normalize_image_value, process_html_content_images


def _utc_now() -> datetime:
    return datetime.utcnow()


def _normalize_page_size(
    page_size: int | None, default: int = 10, maximum: int = 100
) -> int:
    if page_size is None:
        return default
    return max(1, min(page_size, maximum))


def _extract_numeric_suffix(value: str | None, prefix: str) -> int | None:
    if not value:
        return None
    match = re.fullmatch(rf"{re.escape(prefix)}-(\d+)", value)
    if not match:
        return None
    return int(match.group(1))


async def _next_sequence(key: str, prefix: str, session: AsyncSession) -> str:
    stmt = select(Counter).where(Counter.key == key).with_for_update()
    result = await session.execute(stmt)
    counter = result.scalar_one_or_none()

    if not counter:
        max_value = 0
        if key == "blogs":
            blogs_res = await session.execute(select(Blog.id))
            for (b_id,) in blogs_res:
                numeric = _extract_numeric_suffix(b_id, prefix)
                if numeric:
                    max_value = max(max_value, numeric)
        elif key == "comments":
            cmt_res = await session.execute(select(Comment.id))
            for (c_id,) in cmt_res:
                numeric = _extract_numeric_suffix(c_id, prefix)
                if numeric:
                    max_value = max(max_value, numeric)

        counter = Counter(key=key, value=max_value + 1)
        session.add(counter)
        await session.flush()
        return f"{prefix}-{counter.value:03d}"

    counter.value += 1
    await session.flush()
    return f"{prefix}-{counter.value:03d}"


async def _generate_unique_slug(
    title: str, session: AsyncSession, exclude_blog_id: str | None = None
) -> str:
    base_slug = slugify(title)
    candidate = base_slug
    counter = 2

    while True:
        stmt = select(Blog.id).where(Blog.slug == candidate)
        if exclude_blog_id:
            stmt = stmt.where(Blog.id != exclude_blog_id)
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if not existing:
            return candidate
        candidate = f"{base_slug}-{counter}"
        counter += 1


async def _ensure_blog_exists(
    blog_id: str, session: AsyncSession, allow_unpublished: bool = True
) -> Blog:
    stmt = select(Blog).where(Blog.id == blog_id)
    if not allow_unpublished:
        stmt = stmt.where(Blog.status == BlogStatus.PUBLISHED.value)
    result = await session.execute(stmt)
    blog = result.scalar_one_or_none()
    if not blog:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Blog not found"
        )
    return blog


async def _comment_counts(
    blog_ids: list[str],
    session: AsyncSession,
    status_filter: str | None = None,
) -> dict[str, int]:
    if not blog_ids:
        return {}

    stmt = select(Comment.blog_id, func.count(Comment.id)).where(Comment.blog_id.in_(blog_ids))
    if status_filter:
        stmt = stmt.where(Comment.status == status_filter)
    stmt = stmt.group_by(Comment.blog_id)

    res = await session.execute(stmt)
    return {row[0]: row[1] for row in res.all()}


async def create_blog(blog: Any) -> dict[str, Any]:
    blog_dict = blog.model_dump(exclude_none=True)
    now = _utc_now()
    requested_id = blog_dict.get("id")

    async with get_db_session() as session:
        if requested_id:
            blog_id = requested_id
            stmt = select(Blog.id).where(Blog.id == blog_id)
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Blog id already exists",
                )
        else:
            while True:
                blog_id = await _next_sequence("blogs", "blog", session)
                stmt = select(Blog.id).where(Blog.id == blog_id)
                existing = (await session.execute(stmt)).scalar_one_or_none()
                if not existing:
                    break

        status_value = (
            blog_dict["status"].value
            if hasattr(blog_dict["status"], "value")
            else blog_dict["status"]
        )

        published_at = blog_dict.get("published_at")
        if status_value == BlogStatus.PUBLISHED.value and published_at is None:
            published_at = now

        # Normalize image values before saving so APIs always return URLs.
        if blog_dict.get("image"):
            blog_dict["image"] = normalize_image_value(blog_dict["image"])

        # Process content to store base64 images as files
        if blog_dict.get("content"):
            blog_dict["content"] = process_html_content_images(blog_dict["content"])

        slug = await _generate_unique_slug(blog_dict.get("title", ""), session)

        blog_entity = Blog(
            id=blog_id,
            title=blog_dict.get("title") or DEFAULT_BLOG_TITLE,
            excerpt=blog_dict.get("excerpt"),
            content=blog_dict.get("content"),
            author=blog_dict.get("author") or DEFAULT_AUTHOR,
            author_role=blog_dict.get("author_role") or DEFAULT_AUTHOR_ROLE,
            category=normalize_category(blog_dict.get("category")),
            image=blog_dict.get("image"),
            is_video=blog_dict.get("is_video", False),
            url=blog_dict.get("url"),
            slug=slug,
            status=status_value,
            published_at=published_at,
            read_time=blog_dict.get("read_time") or DEFAULT_READ_TIME,
            views=blog_dict.get("views", 0),
            created_at=now,
            updated_at=now,
        )
        session.add(blog_entity)
        await session.flush()

        return {
            "message": "Blog created successfully",
            "blog": serialize_blog(blog_entity),
        }


async def list_admin_blogs(
    status_filter: str | None = None,
    category: str | None = None,
    page: int | None = None,
    page_size: int | None = None,
) -> list[dict[str, Any]] | dict[str, Any]:
    async with get_db_session() as session:
        filters = []
        if status_filter:
            filters.append(Blog.status == status_filter.title())
        if category:
            filters.append(Blog.category == category)

        use_pagination = page is not None or page_size is not None

        if use_pagination:
            count_stmt = select(func.count(Blog.id))
            if filters:
                count_stmt = count_stmt.where(and_(*filters))
            total_blogs = (await session.execute(count_stmt)).scalar_one()

            resolved_page = max(page or 1, 1)
            resolved_page_size = _normalize_page_size(page_size)

            stmt = select(Blog).order_by(Blog.created_at.desc())
            if filters:
                stmt = stmt.where(and_(*filters))
            stmt = stmt.offset((resolved_page - 1) * resolved_page_size).limit(resolved_page_size)
            blogs = list((await session.execute(stmt)).scalars().all())
        else:
            stmt = select(Blog).order_by(Blog.created_at.desc())
            if filters:
                stmt = stmt.where(and_(*filters))
            blogs = list((await session.execute(stmt)).scalars().all())
            total_blogs = None
            resolved_page = None
            resolved_page_size = None

        ids = [blog.id for blog in blogs if blog.id]
        total_comments = await _comment_counts(ids, session=session)
        pending_comments = await _comment_counts(
            ids, session=session, status_filter=CommentStatus.PENDING.value
        )

        items = [
            serialize_blog(
                blog,
                comments_count=total_comments.get(blog.id, 0),
                pending_comments=pending_comments.get(blog.id, 0),
            )
            for blog in blogs
        ]

        if not use_pagination:
            return items

        total_items = total_blogs or 0
        total_pages = ceil(total_items / resolved_page_size) if total_items and resolved_page_size else 0
        return {
            "items": items,
            "pagination": {
                "page": resolved_page,
                "pageSize": resolved_page_size,
                "totalItems": total_items,
                "totalPages": total_pages,
                "hasNext": resolved_page < total_pages if resolved_page and total_pages else False,
                "hasPrevious": resolved_page > 1 if resolved_page else False,
            },
        }


async def get_admin_blog(blog_id: str) -> dict[str, Any]:
    async with get_db_session() as session:
        blog = await _ensure_blog_exists(blog_id, session)
        total_comments = (
            await session.execute(
                select(func.count(Comment.id)).where(Comment.blog_id == blog_id)
            )
        ).scalar_one()
        pending_comments = (
            await session.execute(
                select(func.count(Comment.id)).where(
                    Comment.blog_id == blog_id,
                    Comment.status == CommentStatus.PENDING.value,
                )
            )
        ).scalar_one()
        return serialize_blog(
            blog, comments_count=total_comments, pending_comments=pending_comments
        )


async def update_blog(blog_id: str, payload: Any) -> dict[str, Any]:
    async with get_db_session() as session:
        blog = await _ensure_blog_exists(blog_id, session)
        update_data = payload.model_dump(exclude_unset=True)

        if not update_data:
            total_comments = (
                await session.execute(
                    select(func.count(Comment.id)).where(Comment.blog_id == blog_id)
                )
            ).scalar_one()
            pending_comments = (
                await session.execute(
                    select(func.count(Comment.id)).where(
                        Comment.blog_id == blog_id,
                        Comment.status == CommentStatus.PENDING.value,
                    )
                )
            ).scalar_one()
            return {
                "message": "No changes submitted",
                "blog": serialize_blog(
                    blog, comments_count=total_comments, pending_comments=pending_comments
                ),
            }

        now = _utc_now()

        # Handle title change
        if "title" in update_data and update_data["title"]:
            blog.title = update_data["title"]
            blog.slug = await _generate_unique_slug(
                update_data["title"], session, exclude_blog_id=blog_id
            )

        # Handle status change
        if "status" in update_data and update_data["status"] is not None:
            status_val = (
                update_data["status"].value
                if hasattr(update_data["status"], "value")
                else update_data["status"]
            )
            blog.status = status_val
            if status_val == BlogStatus.PUBLISHED.value and not update_data.get("published_at"):
                if not blog.published_at:
                    blog.published_at = now

        if "published_at" in update_data:
            blog.published_at = update_data["published_at"]
        if "excerpt" in update_data:
            blog.excerpt = update_data["excerpt"]
        if "category" in update_data and update_data["category"] is not None:
            blog.category = normalize_category(update_data["category"])
        if "author" in update_data and update_data["author"] is not None:
            blog.author = update_data["author"]
        if "author_role" in update_data and update_data["author_role"] is not None:
            blog.author_role = update_data["author_role"]
        if "is_video" in update_data and update_data["is_video"] is not None:
            blog.is_video = update_data["is_video"]
        if "url" in update_data:
            blog.url = update_data["url"]
        if "read_time" in update_data and update_data["read_time"] is not None:
            blog.read_time = normalize_read_time(update_data["read_time"])
        if "views" in update_data and update_data["views"] is not None:
            blog.views = update_data["views"]

        # Normalize image values before saving so APIs always return URLs.
        if "image" in update_data and update_data["image"]:
            blog.image = normalize_image_value(update_data["image"])
        elif "image" in update_data:
            blog.image = update_data["image"]

        # Process content to store base64 images as files
        if "content" in update_data and update_data["content"]:
            blog.content = process_html_content_images(update_data["content"])
        elif "content" in update_data:
            blog.content = update_data["content"]

        blog.updated_at = now
        await session.flush()

        total_comments = (
            await session.execute(
                select(func.count(Comment.id)).where(Comment.blog_id == blog_id)
            )
        ).scalar_one()
        pending_comments = (
            await session.execute(
                select(func.count(Comment.id)).where(
                    Comment.blog_id == blog_id,
                    Comment.status == CommentStatus.PENDING.value,
                )
            )
        ).scalar_one()

        return {
            "message": "Blog updated successfully",
            "blog": serialize_blog(
                blog,
                comments_count=total_comments,
                pending_comments=pending_comments,
            ),
        }


async def delete_blog(blog_id: str) -> dict[str, str]:
    async with get_db_session() as session:
        blog = await _ensure_blog_exists(blog_id, session)
        await session.execute(delete(Comment).where(Comment.blog_id == blog_id))
        await session.delete(blog)
        return {"message": "Blog deleted successfully"}


async def list_public_blogs(category: str | None = None) -> list[dict[str, Any]]:
    async with get_db_session() as session:
        stmt = (
            select(Blog)
            .where(Blog.status == BlogStatus.PUBLISHED.value)
            .order_by(Blog.published_at.desc())
        )
        if category:
            stmt = stmt.where(Blog.category == category)
        blogs = list((await session.execute(stmt)).scalars().all())
        ids = [blog.id for blog in blogs if blog.id]
        comment_counts = await _comment_counts(
            ids, session=session, status_filter=CommentStatus.APPROVED.value
        )
        return [
            serialize_blog(
                blog, comments_count=comment_counts.get(blog.id, 0)
            )
            for blog in blogs
        ]


async def get_public_blog(blog_id: str) -> dict[str, Any]:
    async with get_db_session() as session:
        blog = await _ensure_blog_exists(blog_id, session, allow_unpublished=False)
        blog.views = (blog.views or 0) + 1
        await session.flush()
        comments_count = (
            await session.execute(
                select(func.count(Comment.id)).where(
                    Comment.blog_id == blog_id,
                    Comment.status == CommentStatus.APPROVED.value,
                )
            )
        ).scalar_one()
        return serialize_blog(blog, comments_count=comments_count)


async def create_public_comment(blog_id: str, payload: Any) -> dict[str, Any]:
    async with get_db_session() as session:
        await _ensure_blog_exists(blog_id, session, allow_unpublished=False)
        now = _utc_now()
        comment_id = await _next_sequence("comments", "cmt", session)
        comment_dict = payload.model_dump()
        comment_entity = Comment(
            id=comment_id,
            blog_id=blog_id,
            name=comment_dict["name"],
            email=comment_dict["email"],
            message=comment_dict["message"],
            status=CommentStatus.PENDING.value,
            reply=None,
            created_at=now,
            updated_at=now,
        )
        session.add(comment_entity)
        await session.flush()
        return {
            "message": "Comment submitted successfully and is pending review",
            "comment": serialize_comment(comment_entity),
        }


async def list_public_comments(blog_id: str) -> list[dict[str, Any]]:
    async with get_db_session() as session:
        await _ensure_blog_exists(blog_id, session, allow_unpublished=False)
        stmt = (
            select(Comment)
            .where(
                Comment.blog_id == blog_id,
                Comment.status == CommentStatus.APPROVED.value,
            )
            .order_by(Comment.created_at.desc())
        )
        comments = list((await session.execute(stmt)).scalars().all())
        return [serialize_comment(comment) for comment in comments]


async def list_admin_comments(blog_id: str) -> list[dict[str, Any]]:
    async with get_db_session() as session:
        await _ensure_blog_exists(blog_id, session)
        stmt = (
            select(Comment)
            .where(Comment.blog_id == blog_id)
            .order_by(Comment.created_at.desc())
        )
        comments = list((await session.execute(stmt)).scalars().all())
        return [serialize_comment(comment, include_email=True) for comment in comments]


async def moderate_comment(
    blog_id: str, comment_id: str, payload: Any
) -> dict[str, Any]:
    async with get_db_session() as session:
        await _ensure_blog_exists(blog_id, session)
        stmt = select(Comment).where(Comment.blog_id == blog_id, Comment.id == comment_id)
        comment = (await session.execute(stmt)).scalar_one_or_none()
        if not comment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found"
            )
        comment.status = payload.status.value
        comment.updated_at = _utc_now()
        await session.flush()
        return {
            "message": "Comment status updated successfully",
            "comment": serialize_comment(comment, include_email=True),
        }


async def reply_to_comment(
    blog_id: str,
    comment_id: str,
    payload: Any,
    admin: dict[str, Any],
) -> dict[str, Any]:
    async with get_db_session() as session:
        await _ensure_blog_exists(blog_id, session)
        stmt = select(Comment).where(Comment.blog_id == blog_id, Comment.id == comment_id)
        comment = (await session.execute(stmt)).scalar_one_or_none()
        if not comment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found"
            )

        now = _utc_now()
        existing_reply = comment.reply if isinstance(comment.reply, dict) else {}
        created_at = existing_reply.get("created_at") or now.isoformat()
        if hasattr(created_at, "isoformat"):
            created_at = created_at.isoformat()

        reply_payload = {
            "message": payload.message,
            "admin_id": admin["id"],
            "admin_name": admin["name"],
            "admin_email": admin["email"],
            "created_at": created_at,
            "updated_at": now.isoformat(),
        }
        comment.reply = reply_payload
        comment.updated_at = now
        if payload.status is not None:
            comment.status = payload.status.value
        await session.flush()
        return {
            "message": "Comment reply saved successfully",
            "comment": serialize_comment(comment, include_email=True),
        }


async def delete_comment(blog_id: str, comment_id: str) -> dict[str, str]:
    async with get_db_session() as session:
        await _ensure_blog_exists(blog_id, session)
        stmt = select(Comment).where(Comment.blog_id == blog_id, Comment.id == comment_id)
        comment = (await session.execute(stmt)).scalar_one_or_none()
        if not comment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found"
            )
        await session.delete(comment)
        return {"message": "Comment deleted successfully"}


async def list_public_categories() -> list[dict[str, Any]]:
    async with get_db_session() as session:
        stmt = (
            select(Blog.category, func.count(Blog.id))
            .where(Blog.status == BlogStatus.PUBLISHED.value)
            .where(Blog.category.isnot(None))
            .where(Blog.category != "")
            .group_by(Blog.category)
            .order_by(Blog.category.asc())
        )
        result = await session.execute(stmt)
        return [serialize_category(cat, count) for cat, count in result.all()]
