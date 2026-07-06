from fastapi import APIRouter, HTTPException
from datetime import datetime, timedelta
from app.core.config import get_db
from app.core.security import hash_password, verify_password, create_jwt
from app.models.schemas import (
    RegisterRequest, 
    LoginRequest,
    ForgotPasswordRequest, 
    VerifyOtpRequest, 
    ResetPasswordRequest
)
from pymongo.errors import DuplicateKeyError
from app.core.utils import send_email, generate_otp


router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.post("/register")
async def register(body: RegisterRequest):
    db = get_db()
    if await db.users.find_one({"email": body.email.lower()}):
        raise HTTPException(400, "Email already registered")
     
    try:
        result = await db.users.insert_one({
        "name": body.name,
        "email": body.email.lower(),
        "phone": body.phone,
        "password_hash": hash_password(body.password),
        "userRole": body.role,
        "is_verified": False,
        "is_active": True,
        "profile_photo": None,
        "device_tokens": [],
        "preferences": {},
        "saved_venues": [],
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    })
    except DuplicateKeyError as e:
        if "phone" in str(e):
            raise HTTPException(400, "Phone number already registered")
        raise HTTPException(400, "Account already exists")
    user_id = str(result.inserted_id)
    return {
        "success": True,
        "token": create_jwt(user_id, body.role),
        "user": {
            "id": user_id,
            "name": body.name,
            "email": body.email,
            "phone": body.phone,
            "userRole": body.role,
            "profileImageUrl": None,
            "isVerified": False,
        }
    }


@router.post("/login")
async def login(body: LoginRequest):
    db = get_db()
    user = await db.users.find_one({"email": body.email.lower()})
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password")
    if not user.get("is_active", True):
        raise HTTPException(403, "Account suspended")

    return {
        "success": True,
        "token": create_jwt(str(user["_id"]), user["userRole"]),
        "user": {
            "id": str(user["_id"]),
            "name": user["name"],
            "email": user["email"],
            "phone": user.get("phone"),
            "userRole": user["userRole"],
            "profileImageUrl": user.get("profile_photo"),
            "isVerified": user.get("is_verified", False),
        }
    }


@router.post("/forgot-password")
async def forgot_password(body: ForgotPasswordRequest):
    print(f"Forgot password called for: {body.email}")
    db = get_db()
    user = await db.users.find_one({"email": body.email.lower()})
    print(f"User found: {user is not None}")
    if not user:
        raise HTTPException(404, "No account found with this email")

    otp = generate_otp()
    expiry = datetime.utcnow() + timedelta(minutes=10)

    await db.users.update_one(
        {"email": body.email.lower()},
        {"$set": {
            "reset_otp": otp,
            "reset_otp_expiry": expiry
        }}
    )

    email_body = f"""
    <div style="font-family: Arial, sans-serif; max-width: 500px; margin: 0 auto;">
        <h2 style="color: #E91E8C;">VenueMate Password Reset</h2>
        <p>You requested to reset your password.</p>
        <p>Your OTP code is:</p>
        <h1 style="color: #E91E8C; letter-spacing: 8px; text-align: center;">
            {otp}
        </h1>
        <p>This code expires in <strong>10 minutes</strong>.</p>
        <p>If you did not request this, ignore this email.</p>
        <hr>
        <p style="color: #999; font-size: 12px;">VenueMate — AI Powered Venue Booking</p>
    </div>
    """

    sent = send_email(body.email, "VenueMate — Password Reset OTP", email_body)
    if not sent:
        raise HTTPException(500, "Failed to send email. Try again.")

    return {"success": True, "message": "OTP sent to your email"}


@router.post("/verify-otp")
async def verify_otp(body: VerifyOtpRequest):
    db = get_db()
    user = await db.users.find_one({"email": body.email.lower()})
    if not user:
        raise HTTPException(404, "No account found with this email")

    if user.get("reset_otp") != body.otp:
        raise HTTPException(400, "Invalid OTP")

    if datetime.utcnow() > user.get("reset_otp_expiry", datetime.utcnow()):
        raise HTTPException(400, "OTP has expired. Request a new one.")

    return {"success": True, "message": "OTP verified"}


@router.post("/reset-password")
async def reset_password(body: ResetPasswordRequest):
    db = get_db()
    user = await db.users.find_one({"email": body.email.lower()})
    if not user:
        raise HTTPException(404, "No account found with this email")

    if user.get("reset_otp") != body.otp:
        raise HTTPException(400, "Invalid OTP")

    if datetime.utcnow() > user.get("reset_otp_expiry", datetime.utcnow()):
        raise HTTPException(400, "OTP has expired")

    if len(body.new_password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")

    hashed = hash_password(body.new_password)

    await db.users.update_one(
        {"email": body.email.lower()},
        {"$set": {
            "password_hash": hashed,
            "reset_otp": None,
            "reset_otp_expiry": None
        }}
    )

    return {"success": True, "message": "Password reset successfully"}