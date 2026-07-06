import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from motor.motor_asyncio import AsyncIOMotorClient
from app.core.security import hash_password
from datetime import datetime

MONGO_URL = "mongodb://localhost:27017/venuemate"
ADMIN_EMAIL = "byousafsardar@gmail.com"
ADMIN_PASSWORD = "admin123"
ADMIN_NAME = "Bilal Yousaf Sardar"

async def create_admin():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client.venuemate

    existing = await db.users.find_one({"email": ADMIN_EMAIL})
    if existing:
        print(f"⚠️  Admin already exists with email: {ADMIN_EMAIL}")
        print(f"    Role: {existing.get('userRole', 'unknown')}")
        client.close()
        return

    await db.users.insert_one({
        "name": ADMIN_NAME,
        "email": ADMIN_EMAIL,
        "password_hash": hash_password(ADMIN_PASSWORD),
        "userRole": "admin",
        "phone": "03000000000",
        "is_active": True,
        "is_verified": True,
        "saved_venues": [],
        "device_tokens": [],
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    })

    print("    Admin created successfully!")
    print(f"   Email:    {ADMIN_EMAIL}")
    print(f"   Password: {ADMIN_PASSWORD}")
    print(f"   Role:     admin")
    print("\n⚠️  IMPORTANT: Change the password after first login!")
    client.close()

if __name__ == "__main__":
    asyncio.run(create_admin())