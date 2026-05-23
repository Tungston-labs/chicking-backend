from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from app.config.database import ensure_indexes
from app.config.settings import get_settings
from app.routes.auth_routes import router as auth_router
from app.routes.blog_routes import router as blog_router
from app.routes.public_routes import router as public_router
from app.routes.category_routes import router as category_router
from app.utils.upload import ensure_upload_directories

settings = get_settings()
ensure_upload_directories()
uploads_prefix = settings.uploads_url_prefix if settings.uploads_url_prefix.startswith("/") else f"/{settings.uploads_url_prefix}"

app = FastAPI(
    title=settings.app_name
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

app.include_router(auth_router)
app.include_router(blog_router)
app.include_router(public_router)
app.include_router(category_router)
app.mount(uploads_prefix, StaticFiles(directory=settings.uploads_dir, check_dir=False), name="uploads")


@app.on_event("startup")
async def startup_event():
    await ensure_indexes()


@app.get("/")
async def home():
    return {
        "message": "Chicking backend running"
    }
