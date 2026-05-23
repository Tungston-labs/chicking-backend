from fastapi import APIRouter

from app.services.blog_service import list_public_categories

router = APIRouter(tags=["Categories"])


@router.get("/public/categories", include_in_schema=False)
@router.get("/public/categories/", include_in_schema=False)
@router.get("/categories", include_in_schema=False)
@router.get("/categories/")
async def get_categories():
    return await list_public_categories()
