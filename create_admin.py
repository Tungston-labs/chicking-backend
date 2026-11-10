import argparse
import asyncio
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.config.database import engine, ensure_indexes, get_db_session
from app.models.entities import Admin
from app.utils.hash import hash_password


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create a super admin for Chicking CMS")
    parser.add_argument("--name", required=True, help="Admin full name")
    parser.add_argument("--email", required=True, help="Admin email")
    parser.add_argument("--password", required=True, help="Admin password")
    parser.add_argument("--role", default="super_admin", help="Admin role")
    parser.add_argument(
        "--force-update",
        action="store_true",
        help="Update the existing admin if the email already exists",
    )
    return parser


async def create_admin(args: argparse.Namespace) -> None:
    try:
        await ensure_indexes()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        email = args.email.lower()

        async with get_db_session() as session:
            stmt = select(Admin).where(Admin.email == email)
            existing = (await session.execute(stmt)).scalar_one_or_none()

            if existing:
                if not args.force_update:
                    print("Admin already exists. Use --force-update to replace the password/details.")
                    return

                existing.name = args.name
                existing.password_hash = hash_password(args.password)
                existing.role = args.role
                existing.is_active = True
                existing.updated_at = now
                print(f"Updated admin: {email}")
                return

            total_admins = (await session.execute(select(func.count(Admin.id)))).scalar_one()
            new_admin = Admin(
                id=f"admin-{total_admins + 1:03d}",
                name=args.name,
                email=email,
                password_hash=hash_password(args.password),
                role=args.role,
                is_active=True,
                last_login_at=None,
                created_at=now,
                updated_at=now,
            )
            session.add(new_admin)
            print(f"Created admin: {email}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(create_admin(build_parser().parse_args()))
