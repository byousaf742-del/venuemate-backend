from fastapi import APIRouter, Depends
from bson import ObjectId
from app.core.config import get_db
from app.core.security import get_current_user
from datetime import datetime

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


@router.get("")
async def get_notifications(user=Depends(get_current_user)):
    db = get_db()
    cursor = db.notifications.find(
        {"user_id": user["_id"]}, sort=[("created_at", -1)], limit=50
    )
    notifs = []
    async for n in cursor:
        notifs.append({
            "id": str(n["_id"]),
            "type": n["type"],
            "title": n["title"],
            "body": n["body"],
            "entity_type": n.get("entity_type"),
            "entity_id": str(n["entity_id"]) if n.get("entity_id") else None,
            "is_read": n["is_read"],
            "created_at": n["created_at"].isoformat(),
        })
    unread_count = await db.notifications.count_documents(
        {"user_id": user["_id"], "is_read": False}
    )
    return {"notifications": notifs, "unread_count": unread_count}


@router.put("/{notification_id}/read")
async def mark_one_read(notification_id: str, user=Depends(get_current_user)):
    db = get_db()
    await db.notifications.update_one(
        {"_id": ObjectId(notification_id), "user_id": user["_id"]},
        {"$set": {"is_read": True}},
    )
    return {"success": True}


@router.put("/read-all")
async def mark_all_read(user=Depends(get_current_user)):
    db = get_db()
    await db.notifications.update_many(
        {"user_id": user["_id"]}, {"$set": {"is_read": True}}
    )
    return {"success": True}
