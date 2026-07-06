from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from app.core.config import get_db
from app.core.security import get_current_user
from app.models.schemas import UpdateProfileRequest

router = APIRouter(prefix="/api/users", tags=["Users"])


@router.get("/me")
async def get_profile(user=Depends(get_current_user)):
    db = get_db()
    total_bookings = await db.bookings.count_documents({"user_id": user["_id"]})
    total_bids = await db.bids.count_documents({"user_id": user["_id"]})
    total_reviews = await db.reviews.count_documents({"user_id": user["_id"]})
    return {
        "user": {
            "id": str(user["_id"]), "name": user["name"],
            "email": user["email"], "phone": user.get("phone"),
            "userRole": user["userRole"], "profile_photo": user.get("profile_photo"),
            "is_verified": user.get("is_verified", False),
        },
        "stats": {
            "total_bookings": total_bookings,
            "total_bids": total_bids,
            "total_reviews": total_reviews,
            "saved_venues": len(user.get("saved_venues", [])),
        }
    }


@router.put("/me")
async def update_profile(body: UpdateProfileRequest, user=Depends(get_current_user)):
    db = get_db()
    updates = {"updated_at": datetime.utcnow()}
    if body.name:          updates["name"] = body.name
    if body.phone:         updates["phone"] = body.phone
    if body.profile_photo: updates["profile_photo"] = body.profile_photo
    await db.users.update_one({"_id": user["_id"]}, {"$set": updates})
    return {"success": True}


@router.put("/me/device-token")
async def update_device_token(token: str, user=Depends(get_current_user)):
    db = get_db()
    await db.users.update_one(
        {"_id": user["_id"]}, {"$addToSet": {"device_tokens": token}}
    )
    return {"success": True}

@router.put("/change-password")
async def change_password(body: dict, user=Depends(get_current_user)):
    db = get_db()
    from app.core.security import verify_password, hash_password
    if not verify_password(body['old_password'], user['password_hash']):
        raise HTTPException(400, "Current password is incorrect")
    if len(body['new_password']) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    hashed = hash_password(body['new_password'])
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"password_hash": hashed, "updated_at": datetime.utcnow()}}
    )
    return {"success": True, "message": "Password changed successfully"}

@router.post("/fcm-token")
async def save_fcm_token(body: dict, user=Depends(get_current_user)):
    db = get_db()
    token = body.get("token")
    if not token:
        raise HTTPException(400, "Token required")
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$addToSet": {"fcm_tokens": token}}
    )
    return {"success": True}

@router.delete("/fcm-token")
async def remove_fcm_token(body: dict, user=Depends(get_current_user)):
    db = get_db()
    token = body.get("token")
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$pull": {"fcm_tokens": token}}
    )
    return {"success": True}
