from fastapi import APIRouter, Query

from app.schemas.blog_schema import PublicCommentCreateSchema
from app.services.blog_service import (
    create_public_comment,
    get_public_blog,
    list_public_blogs,
    list_public_comments,
)

router = APIRouter(tags=["Public Blogs"])


@router.get("/public/blogs", include_in_schema=False)
@router.get("/public/blogs/", include_in_schema=False)
@router.get("/blogs/", include_in_schema=False)
@router.get("/blogs")
async def public_blogs(category: str | None = Query(default=None)):
    return await list_public_blogs(category)


@router.get("/public/blogs/{blog_id}", include_in_schema=False)
@router.get("/public/blogs/{blog_id}/", include_in_schema=False)
@router.get("/blogs/{blog_id}/", include_in_schema=False)
@router.get("/blogs/{blog_id}")
async def public_blog_detail(blog_id: str):
    return await get_public_blog(blog_id)


@router.post("/public/blogs/{blog_id}/comments", include_in_schema=False)
@router.post("/public/blogs/{blog_id}/comments/", include_in_schema=False)
@router.post("/blogs/{blog_id}/comments/", include_in_schema=False)
@router.post("/blogs/{blog_id}/comments")
async def add_blog_comment(blog_id: str, payload: PublicCommentCreateSchema):
    return await create_public_comment(blog_id, payload)


@router.get("/public/blogs/{blog_id}/comments", include_in_schema=False)
@router.get("/public/blogs/{blog_id}/comments/", include_in_schema=False)
@router.get("/blogs/{blog_id}/comments/", include_in_schema=False)
@router.get("/blogs/{blog_id}/comments")
async def get_public_blog_comments(blog_id: str):
    return await list_public_comments(blog_id)
