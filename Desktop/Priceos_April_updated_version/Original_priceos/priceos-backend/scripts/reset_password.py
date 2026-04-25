#!/usr/bin/env python3
"""
scripts/reset_password.py
─────────────────────────
Resets a user's password directly in MongoDB.

USAGE:
    python scripts/reset_password.py --email admin@priceos.com --password NewPass@123
    python scripts/reset_password.py --email rohith@lyzr.ai --password NewPass@123
"""
import asyncio
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def reset(email: str, new_password: str) -> None:
    uri = os.environ.get("MONGODB_URI", "")
    db_name = os.environ.get("DATABASE_NAME") or os.environ.get("MONGODB_DB") or "priceos"
    client = AsyncIOMotorClient(uri)
    db = client[db_name]

    new_hash = pwd_context.hash(new_password)
    result = await db["users"].update_one(
        {"email": email},
        {"$set": {"passwordHash": new_hash}}
    )

    if result.modified_count > 0:
        print(f"✅ Password reset for: {email}")
        print(f"   New password: {new_password}")
    elif result.matched_count > 0:
        print(f"⚠️  User {email} found but no change was made")
    else:
        print(f"❌ No user found with email: {email}")
        users = await db["users"].find({}, {"email": 1, "name": 1}).to_list(20)
        print("\nAvailable users:")
        for u in users:
            print(f"   {u.get('email')} ({u.get('name', 'no name')})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reset a user password")
    parser.add_argument("--email", required=True, help="User email address")
    parser.add_argument("--password", required=True, help="New plain-text password")
    args = parser.parse_args()
    asyncio.run(reset(args.email, args.password))
