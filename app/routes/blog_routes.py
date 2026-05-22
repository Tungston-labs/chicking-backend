from fastapi import APIRouter, Depends, Query

from app.middleware.jwt_auth import get_current_admin
from app.schemas.blog_schema import BlogCreateSchema, BlogUpdateSchema, CommentModerationSchema
from app.services.blog_service import (
    create_blog,
    delete_blog,
    delete_comment,
    get_admin_blog,
    list_admin_blogs,
    list_admin_comments,
    moderate_comment,
    update_blog,
)

router = APIRouter(
    prefix="/admin/blogs",
    tags=["Blogs"]
)


@router.post("/")
async def create_new_blog(
    blog: BlogCreateSchema,
    admin: dict = Depends(get_current_admin),
):
    return await create_blog(blog)


@router.get("/")
async def get_all_blogs(
    status: str | None = Query(default=None),
    category: str | None = Query(default=None),
    page: int | None = Query(default=None, ge=1),
    page_size: int | None = Query(default=None, ge=1, le=100),
    admin: dict = Depends(get_current_admin),
):
    return await list_admin_blogs(status, category, page, page_size)


@router.get("/{blog_id}")
async def get_blog(blog_id: str, admin: dict = Depends(get_current_admin)):
    return await get_admin_blog(blog_id)


@router.put("/{blog_id}")
async def update_existing_blog(
    blog_id: str,
    payload: BlogUpdateSchema,
    admin: dict = Depends(get_current_admin),
):
    return await update_blog(blog_id, payload)


@router.delete("/{blog_id}")
async def delete_existing_blog(blog_id: str, admin: dict = Depends(get_current_admin)):
    return await delete_blog(blog_id)


@router.get("/{blog_id}/comments")
async def get_blog_comments(blog_id: str, admin: dict = Depends(get_current_admin)):
    return await list_admin_comments(blog_id)


@router.patch("/{blog_id}/comments/{comment_id}")
async def update_comment_status(
    blog_id: str,
    comment_id: str,
    payload: CommentModerationSchema,
    admin: dict = Depends(get_current_admin),
):
    return await moderate_comment(blog_id, comment_id, payload)


@router.delete("/{blog_id}/comments/{comment_id}")
async def remove_comment(
    blog_id: str,
    comment_id: str,
    admin: dict = Depends(get_current_admin),
):
    return await delete_comment(blog_id, comment_id)
