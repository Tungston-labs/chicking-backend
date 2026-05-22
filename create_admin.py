import argparse
import asyncio
from datetime import datetime

from app.config.database import db, ensure_indexes
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
    await ensure_indexes()
    now = datetime.utcnow()
    email = args.email.lower()

    existing = await db.admins.find_one({"email": email})
    total_admins = await db.admins.count_documents({})
    payload = {
        "id": f"admin-{total_admins + 1:03d}" if not existing else existing["id"],
        "name": args.name,
        "email": email,
        "password_hash": hash_password(args.password),
        "role": args.role,
        "is_active": True,
        "updated_at": now,
    }

    if existing:
        if not args.force_update:
            print("Admin already exists. Use --force-update to replace the password/details.")
            return

        await db.admins.update_one(
            {"email": email},
            {"$set": payload},
        )
        print(f"Updated admin: {email}")
        return

    payload["created_at"] = now
    payload["last_login_at"] = None
    await db.admins.insert_one(payload)
    print(f"Created admin: {email}")


if __name__ == "__main__":
    asyncio.run(create_admin(build_parser().parse_args()))
