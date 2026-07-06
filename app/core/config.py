import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URL  = os.getenv("MONGO_URL", "mongodb://localhost:27017/venuemate")
JWT_SECRET = os.getenv("JWT_SECRET", "change-this-secret")
JWT_EXPIRY = 60 * 24 * 7   # 7 days in minutes
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME", "dfhmfdzmh")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY", "218335423597619")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET", "RIHH44VzIGc2Ttn2iKM7Yw29dF4")
GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

_client: AsyncIOMotorClient = None

def get_db():
    return _client["venuemate"]

async def connect_db():
    global _client
    _client = AsyncIOMotorClient(MONGO_URL)
    print("✅ MongoDB connected")

async def close_db():
    _client.close()
    print("🔌 MongoDB disconnected")
