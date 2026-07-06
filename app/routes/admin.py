from fastapi import APIRouter, Depends
from datetime import datetime
from bson import ObjectId
from app.core.config import get_db
from app.core.security import require_role
from app.core.utils import push_notification

router = APIRouter(prefix="/api/admin", tags=["Admin"])

@router.get("/venues/pending")
async def pending_venues(user=Depends(require_role("admin"))):
    db = get_db()
    cursor = db.venues.find({"is_verified": False, "is_active": {"$ne": False}})
    venues = []
    async for v in cursor:
        owner = await db.users.find_one(
            {"_id": v["owner_id"]}, {"name": 1, "email": 1})
        venues.append({
            "id": str(v["_id"]),
            "name": v.get("name", ""),
            "type": v.get("type", ""),
            "location": v.get("location", {}),
            "owner_name": owner["name"] if owner else "Unknown",
            "owner_email": owner["email"] if owner else "",
            "created_at": str(v.get("created_at", "")),
            "media": v.get("media", []),
            "pricing": v.get("pricing", {}),
            "capacity": v.get("capacity", {}),
        })
    return {"venues": venues}


@router.get("/venues/all")
async def all_venues(user=Depends(require_role("admin"))):
    db = get_db()
    cursor = db.venues.find({}).sort("created_at", -1)
    venues = []
    async for v in cursor:
        venues.append({
            "id": str(v["_id"]),
            "name": v.get("name", ""),
            "type": v.get("type", ""),
            "is_verified": v.get("is_verified", False),
            "is_active": v.get("is_active", True),
            "rating": v.get("rating", 0.0),
            "owner_id": str(v.get("owner_id", "")),
        })
    return {"venues": venues}


@router.put("/venues/{venue_id}/verify")
async def verify_venue(
    venue_id: str, approve: bool = True,
    user=Depends(require_role("admin"))
):
    db = get_db()
    venue = await db.venues.find_one({"_id": ObjectId(venue_id)})
    if venue:
        await db.venues.update_one(
            {"_id": ObjectId(venue_id)},
            {"$set": {
                "is_verified": approve,
                "is_active": approve,
                "updated_at": datetime.utcnow()
            }}
        )
        await push_notification(
            db, str(venue["owner_id"]),
            "venue_verified" if approve else "venue_rejected",
            "Venue Verified!" if approve else "Venue Not Approved",
            f"Your venue '{venue['name']}' has been {'approved and is now live' if approve else 'rejected by admin'}.",
            "venue", venue_id
        )
    return {"success": True}


@router.delete("/venues/{venue_id}/reject")
async def reject_venue(venue_id: str, user=Depends(require_role("admin"))):
    db = get_db()
    venue = await db.venues.find_one({"_id": ObjectId(venue_id)})
    if venue:
        await push_notification(
            db, str(venue["owner_id"]),
            "venue_rejected",
            "Venue Request Not Approved",
            f"Your venue '{venue['name']}' verification request was not approved by admin.",
            "venue", venue_id
        )
        await db.venues.delete_one({"_id": ObjectId(venue_id)})
    return {"success": True}


@router.get("/users")
async def all_users(user=Depends(require_role("admin"))):
    db = get_db()
    cursor = db.users.find({}).sort("created_at", -1)
    users = []
    async for u in cursor:
        users.append({
            "id": str(u["_id"]),
            "name": u.get("name", ""),
            "email": u.get("email", ""),
            "phone": u.get("phone", ""),
            "userRole": u.get("userRole", "customer"),
            "is_active": u.get("is_active", True),
            "is_verified": u.get("is_verified", False),
            "created_at": str(u.get("created_at", "")),
        })
    return {"users": users}

@router.put("/venues/{venue_id}/suspend")
async def suspend_venue(
    venue_id: str, suspend: bool = True,
    user=Depends(require_role("admin"))
):
    db = get_db()
    await db.venues.update_one(
        {"_id": ObjectId(venue_id)},
        {"$set": {"is_active": not suspend}}
    )
    return {"success": True}


@router.put("/users/{user_id}/suspend")

@router.put("/users/{user_id}/suspend")
async def suspend_user(
    user_id: str, suspend: bool = True,
    user=Depends(require_role("admin"))
):
    db = get_db()
    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"is_active": not suspend}}
    )
    return {"success": True}


@router.get("/bookings")
async def all_bookings(user=Depends(require_role("admin"))):
    db = get_db()
    cursor = db.bookings.find({}).sort("created_at", -1).limit(100)
    bookings = []
    async for b in cursor:
        bookings.append({
            "id": str(b["_id"]),
            "venue_name": b.get("venue_name", ""),
            "customer_name": b.get("customer_name", ""),
            "event_date": b.get("event_date", ""),
            "event_type": b.get("event_type", ""),
            "status": b.get("status", ""),
            "total_amount": b.get("total_amount", 0),
            "advance_paid": b.get("advance_paid", 0),
            "created_at": str(b.get("created_at", "")),
        })
    return {"bookings": bookings}



@router.get("/stats")
async def system_stats(user=Depends(require_role("admin"))):
    db = get_db()
    total_revenue_result = await db.bookings.aggregate([
        {"$match": {"status": {"$in": ["confirmed", "completed"]}}},
        {"$group": {"_id": None, "total": {"$sum": "$advance_paid"}}}
    ]).to_list(1)
    total_revenue = total_revenue_result[0]["total"] if total_revenue_result else 0

    return {
        "total_customers": await db.users.count_documents({"userRole": "customer"}),
        "total_owners": await db.users.count_documents({"userRole": "owner"}),
        "total_venues": await db.venues.count_documents({}),
        "verified_venues": await db.venues.count_documents({"is_verified": True}),
        "pending_venues": await db.venues.count_documents({"is_verified": False}),
        "total_bookings": await db.bookings.count_documents({}),
        "confirmed_bookings": await db.bookings.count_documents({"status": "confirmed"}),
        "active_bids": await db.bids.count_documents({"status": "open"}),
        "total_revenue": total_revenue,
    }



@router.post("/announce")
async def send_announcement(
    body: dict,
    user=Depends(require_role("admin"))
):
    db = get_db()
    title = body.get("title", "VenueMate Announcement")
    message = body.get("message", "")
    target = body.get("target", "all")  # all | customers | owners

    query = {}
    if target == "customers":
        query = {"userRole": "customer"}
    elif target == "owners":
        query = {"userRole": "owner"}

    cursor = db.users.find(query, {"_id": 1})
    count = 0
    async for u in cursor:
        await push_notification(
            db, str(u["_id"]),
            "system", title, message
        )
        count += 1

    return {"success": True, "notified": count}