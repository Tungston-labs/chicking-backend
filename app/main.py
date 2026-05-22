from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.database import ensure_indexes
from app.config.settings import get_settings
from app.routes.auth_routes import router as auth_router
from app.routes.blog_routes import router as blog_router
from app.routes.public_routes import router as public_router
from app.routes.category_routes import router as category_router

settings = get_settings()

app = FastAPI(
    title=settings.app_name
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(blog_router)
app.include_router(public_router)
app.include_router(category_router)


@app.on_event("startup")
async def startup_event():
    await ensure_indexes()


@app.get("/")
async def home():
    return {
        "message": "Chicking backend running"
    }
