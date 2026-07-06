from fastapi import APIRouter, Depends
from datetime import datetime
from bson import ObjectId
from app.core.config import get_db
from app.core.security import get_current_user
from app.core.utils import push_notification
from app.models.schemas import SendMessageRequest

router = APIRouter(prefix="/api/messages", tags=["Messages"])


@router.get("/conversations")
async def get_conversations(user=Depends(get_current_user)):
    db = get_db()
    pipeline = [
        {"$match": {"$and": [
            {"$or": [
                {"sender_id": user["_id"]}, {"receiver_id": user["_id"]}
            ]},
            {"hidden_for": {"$not": {"$elemMatch": {"$eq": user["_id"]}}}}
        ]}},
        {"$sort": {"created_at": -1}},
        {"$group": {
            "_id": "$room_id",
            "last_message": {"$first": "$content"},
            "last_time": {"$first": "$created_at"},
            "other_user_id": {"$first": {
                "$cond": [{"$eq": ["$sender_id", user["_id"]]},
                          "$receiver_id", "$sender_id"]
            }},
        }},
        {"$sort": {"last_time": -1}},
    ]
    conversations = []
    async for c in db.messages.aggregate(pipeline):
        other = await db.users.find_one(
            {"_id": c["other_user_id"]},
            {"name": 1, "profile_photo": 1}
        )
        unread = await db.messages.count_documents({
            "room_id": c["_id"],
            "receiver_id": user["_id"],
            "is_read": False
        })

        room_id = c["_id"]
        context_type = "chat"
        context_name = ""
        context_image = None

        if room_id.startswith("venue:"):
            venue_id = room_id.replace("venue:", "")
            try:
                venue = await db.venues.find_one(
                    {"_id": ObjectId(venue_id)},
                    {"name": 1, "media": {"$slice": 1}}
                )
                if venue:
                    context_type = "venue"
                    context_name = venue["name"]
                    context_image = venue["media"][0]["url"] if venue.get("media") else None
            except:
                pass

        elif room_id.startswith("booking:"):
            booking_id = room_id.replace("booking:", "")
            try:
                booking = await db.bookings.find_one(
                    {"_id": ObjectId(booking_id)},
                    {"venue_name": 1, "event_type": 1,
                     "event_date": 1, "venue_image": 1}
                )
                if booking:
                    context_type = "booking"
                    context_name = booking.get("venue_name", "")
                    context_image = booking.get("venue_image")
            except:
                pass

        elif room_id.startswith("bid:"):
            bid_id = room_id.replace("bid:", "")
            try:
                bid = await db.bids.find_one(
                    {"_id": ObjectId(bid_id)},
                    {"event_type": 1}
                )
                if bid:
                    context_type = "bid"
                    context_name = f"Bid — {bid.get('event_type', '')}"
            except:
                pass

        conversations.append({
            "room_id": room_id,
            "other_user_id": str(c["other_user_id"]),
            "name": other["name"] if other else "Unknown",
            "other_user_photo": other.get("profile_photo") if other else None,
            "context_type": context_type,
            "context_name": context_name,
            "context_image": context_image,
            "last_message": c["last_message"],
            "time": c["last_time"].strftime("%I:%M %p"),
            "unread": unread,
            "online": False,
        })
    return {"conversations": conversations}

@router.delete("/conversations/{room_id}")
async def delete_conversation(room_id: str, user=Depends(get_current_user)):
    db = get_db()
    await db.messages.update_many(
        {"room_id": room_id},
        {"$addToSet": {"hidden_for": user["_id"]}}
    )
    return {"success": True}

@router.get("/{room_id}")
async def get_messages(room_id: str, page: int = 1, user=Depends(get_current_user)):
    db = get_db()
    limit, skip = 50, (page - 1) * 50
    cursor = db.messages.find(
        {"room_id": room_id}
    ).sort("created_at", 1).skip(skip).limit(limit)

    messages = []
    async for m in cursor:
        messages.append({
            "id": str(m["_id"]),
            "text": m["content"],
            "isMe": str(m["sender_id"]) == str(user["_id"]),
            "time": m["created_at"].strftime("%I:%M %p"),
            "type": m.get("type", "text"),
            "voice_url": m.get("voice_url"),
        })
    await db.messages.update_many(
        {"room_id": room_id, "receiver_id": user["_id"]},
        {"$set": {"is_read": True}}
    )
    return {"messages": messages}


@router.post("")
async def send_message(body: SendMessageRequest, user=Depends(get_current_user)):
    db = get_db()
    doc = {
        "room_id": body.room_id,
        "sender_id": user["_id"],
        "receiver_id": ObjectId(body.receiver_id),
        "type": body.type,
        "content": body.content,
        "voice_url": body.content if body.type == "voice" else None,
        "is_read": False,
        "created_at": datetime.utcnow(),
    }
    result = await db.messages.insert_one(doc)
    await push_notification(
        db, body.receiver_id, "new_message",
        f"New message from {user['name']}", body.content[:60],
        "message", str(result.inserted_id)
    )
    return {"success": True, "message": {
        "id": str(result.inserted_id),
        "text": body.content, "isMe": True, "time": "Now",
    }}
