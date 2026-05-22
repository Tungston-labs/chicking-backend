from fastapi import APIRouter
from app.services.blog_service import list_public_categories

router = APIRouter(
    prefix="/categories",
    tags=["Categories"]
)


@router.get("/")
async def get_categories():
    return await list_public_categories()
