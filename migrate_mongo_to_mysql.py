"""
Script to migrate existing data from MongoDB to MySQL database.
Usage:
    python migrate_mongo_to_mysql.py --mongo-url "mongodb://localhost:27017" --database-name "chicking_cms"
or simply:
    python migrate_mongo_to_mysql.py (using environment variables MONGO_URL and DATABASE_NAME)
"""

import argparse
import asyncio
from datetime import datetime
import os
import re
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient
from sqlalchemy import func, select

from app.config.database import engine, ensure_indexes, get_db_session
from app.config.settings import get_settings
from app.constants.blog_defaults import (
    DEFAULT_AUTHOR,
    DEFAULT_AUTHOR_ROLE,
    DEFAULT_BLOG_STATUS,
    DEFAULT_BLOG_TITLE,
    DEFAULT_READ_TIME,
    normalize_category,
    normalize_read_time,
)
from app.models.entities import (
    Admin,
    Blog,
    Comment,
    Counter,
    PasswordResetOTP,
    RefreshToken,
)
from app.utils.upload import normalize_image_value, process_html_content_images


def _extract_numeric(value: str | None, prefix: str) -> int:
    if not value:
        return 0
    match = re.fullmatch(rf"{re.escape(prefix)}-(\d+)", value)
    return int(match.group(1)) if match else 0


async def run_migration(mongo_url: str, db_name: str) -> None:
    print("=" * 60)
    print("Starting MongoDB -> MySQL Data Migration")
    print("=" * 60)

    # 1. Ensure MySQL schema is ready
    print("Ensuring MySQL schema and tables exist...")
    await ensure_indexes()

    # 2. Connect to MongoDB
    print(f"Connecting to MongoDB at {mongo_url}, database: {db_name}...")
    client = AsyncIOMotorClient(mongo_url)
    mongo_db = client[db_name]

    max_blog_seq = 0
    max_comment_seq = 0
    max_admin_seq = 0

    async with get_db_session() as session:
        # Migrate Admins
        print("\n[1/5] Migrating Admins...")
        admin_count = 0
        async for doc in mongo_db.admins.find({}):
            admin_id = doc.get("id") or f"admin-{admin_count + 1:03d}"
            max_admin_seq = max(max_admin_seq, _extract_numeric(admin_id, "admin"))

            stmt = select(Admin).where(Admin.id == admin_id)
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if not existing:
                admin = Admin(
                    id=admin_id,
                    name=doc.get("name") or "Admin",
                    email=str(doc.get("email") or "").lower(),
                    password_hash=doc.get("password_hash") or "",
                    role=doc.get("role") or "super_admin",
                    is_active=bool(doc.get("is_active", True)),
                    last_login_at=doc.get("last_login_at"),
                    created_at=doc.get("created_at") or datetime.utcnow(),
                    updated_at=doc.get("updated_at") or datetime.utcnow(),
                )
                session.add(admin)
                admin_count += 1
        print(f"Migrated {admin_count} new admins.")

        # Migrate Blogs
        print("\n[2/5] Migrating Blogs...")
        blog_count = 0
        async for doc in mongo_db.blogs.find({}):
            blog_id = str(doc.get("id") or doc.get("_id"))
            max_blog_seq = max(max_blog_seq, _extract_numeric(blog_id, "blog"))

            stmt = select(Blog).where(Blog.id == blog_id)
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if not existing:
                content = doc.get("content")
                if content:
                    content = process_html_content_images(content)
                image = doc.get("image")
                if image:
                    image = normalize_image_value(image)

                blog = Blog(
                    id=blog_id,
                    title=doc.get("title") or DEFAULT_BLOG_TITLE,
                    excerpt=doc.get("excerpt"),
                    content=content,
                    author=doc.get("author") or DEFAULT_AUTHOR,
                    author_role=doc.get("author_role") or DEFAULT_AUTHOR_ROLE,
                    category=normalize_category(doc.get("category")),
                    image=image,
                    is_video=bool(doc.get("is_video", False)),
                    url=doc.get("url"),
                    slug=doc.get("slug") or f"blog-{blog_id}",
                    status=doc.get("status") or DEFAULT_BLOG_STATUS,
                    published_at=doc.get("published_at"),
                    read_time=normalize_read_time(doc.get("read_time") or DEFAULT_READ_TIME),
                    views=int(doc.get("views") or 0),
                    created_at=doc.get("created_at") or datetime.utcnow(),
                    updated_at=doc.get("updated_at") or datetime.utcnow(),
                )
                session.add(blog)
                blog_count += 1
        print(f"Migrated {blog_count} new blogs.")

        # Migrate Comments
        print("\n[3/5] Migrating Comments...")
        comment_count = 0
        async for doc in mongo_db.comments.find({}):
            comment_id = str(doc.get("id") or doc.get("_id"))
            max_comment_seq = max(max_comment_seq, _extract_numeric(comment_id, "cmt"))

            stmt = select(Comment).where(Comment.id == comment_id)
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if not existing:
                reply = doc.get("reply")
                if isinstance(reply, dict):
                    # Ensure datetimes are ISO strings in JSON
                    if "created_at" in reply and hasattr(reply["created_at"], "isoformat"):
                        reply["created_at"] = reply["created_at"].isoformat()
                    if "updated_at" in reply and hasattr(reply["updated_at"], "isoformat"):
                        reply["updated_at"] = reply["updated_at"].isoformat()

                comment = Comment(
                    id=comment_id,
                    blog_id=doc.get("blog_id"),
                    name=doc.get("name") or "Anonymous",
                    email=str(doc.get("email") or "").lower(),
                    message=doc.get("message") or "",
                    status=doc.get("status") or "Pending",
                    reply=reply if isinstance(reply, dict) else None,
                    created_at=doc.get("created_at") or datetime.utcnow(),
                    updated_at=doc.get("updated_at") or datetime.utcnow(),
                )
                session.add(comment)
                comment_count += 1
        print(f"Migrated {comment_count} new comments.")

        # Migrate Password Reset OTPs
        print("\n[4/5] Migrating Password Reset OTPs...")
        otp_count = 0
        async for doc in mongo_db.password_reset_otps.find({}):
            email = str(doc.get("email") or "").lower()
            stmt = select(PasswordResetOTP).where(PasswordResetOTP.email == email)
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if not existing and email:
                otp_entity = PasswordResetOTP(
                    email=email,
                    admin_id=doc.get("admin_id") or "",
                    otp_hash=doc.get("otp_hash") or "",
                    expires_at=doc.get("expires_at") or datetime.utcnow(),
                    verified_at=doc.get("verified_at"),
                    used_at=doc.get("used_at"),
                    created_at=doc.get("created_at") or datetime.utcnow(),
                    updated_at=doc.get("updated_at") or datetime.utcnow(),
                )
                session.add(otp_entity)
                otp_count += 1
        print(f"Migrated {otp_count} reset OTP records.")

        # Migrate Refresh Tokens
        print("\n[5/5] Migrating Refresh Tokens...")
        token_count = 0
        async for doc in mongo_db.refresh_tokens.find({}):
            token_hash = doc.get("token_hash")
            if not token_hash:
                continue
            stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if not existing:
                token_entity = RefreshToken(
                    token_hash=token_hash,
                    admin_id=doc.get("admin_id") or "",
                    email=str(doc.get("email") or "").lower(),
                    expires_at=doc.get("expires_at") or datetime.utcnow(),
                    revoked_at=doc.get("revoked_at"),
                    created_at=doc.get("created_at") or datetime.utcnow(),
                    updated_at=doc.get("updated_at") or datetime.utcnow(),
                )
                session.add(token_entity)
                token_count += 1
        print(f"Migrated {token_count} refresh tokens.")

        # Initialize sequence counters
        for key, val in [("blogs", max_blog_seq), ("comments", max_comment_seq), ("admins", max_admin_seq)]:
            c_stmt = select(Counter).where(Counter.key == key)
            counter = (await session.execute(c_stmt)).scalar_one_or_none()
            if not counter:
                session.add(Counter(key=key, value=val))
            elif counter.value < val:
                counter.value = val

    await engine.dispose()
    print("\nMigration completed successfully!")


def main():
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Migrate MongoDB data to MySQL")
    parser.add_argument("--mongo-url", default=settings.mongo_url, help="MongoDB connection string")
    parser.add_argument("--database-name", default=settings.database_name or "chicking", help="MongoDB database name")
    args = parser.parse_args()

    if not args.mongo_url:
        print("Error: MONGO_URL must be provided via --mongo-url or environment variable.")
        return

    asyncio.run(run_migration(args.mongo_url, args.database_name))


if __name__ == "__main__":
    main()
