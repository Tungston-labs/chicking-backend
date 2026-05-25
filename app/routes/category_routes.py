from fastapi import APIRouter

from app.services.blog_service import list_public_categories

router = APIRouter(tags=["Categories"])


@router.get("/categories")
async def get_categories():
    return await list_public_categories()
