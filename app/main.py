import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config.database import ensure_indexes
from app.config.settings import get_settings
from app.routes.auth_routes import router as auth_router
from app.routes.blog_routes import router as blog_router
from app.routes.category_routes import router as category_router
from app.routes.public_routes import router as public_router

settings = get_settings()

# Ensure uploads directory exists
os.makedirs("uploads/blogs", exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure MySQL tables and indexes are ready on startup
    await ensure_indexes()
    yield


app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve uploaded files
app.mount(
    "/uploads",
    StaticFiles(directory="uploads"),
    name="uploads",
)

app.include_router(auth_router, prefix="/api")
app.include_router(blog_router, prefix="/api")
app.include_router(public_router, prefix="/api")
app.include_router(category_router, prefix="/api")


@app.get("/")
async def home():
    return {
        "message": "Chicking backend running"
    }


@app.get("/api")
async def api_home():
    return {
        "message": "Chicking backend API running"
    }
