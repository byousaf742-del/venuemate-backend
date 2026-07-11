import os
import cloudinary
import cloudinary.uploader
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from datetime import datetime, timedelta
from bson import ObjectId
from app.core.config import get_db
from app.core.security import get_current_user, require_role
from app.models.schemas import CreateVenueRequest
from fastapi import UploadFile, File


cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
)

router = APIRouter(prefix="/api/venues", tags=["Venues"])


def _serialize_venue(v: dict) -> dict:
    """Convert all ObjectId fields to strings in a venue document."""
    v["id"] = str(v.pop("_id"))
    if "owner_id" in v:
        v["owner_id"] = str(v["owner_id"])
    if "availability_slots" in v:
        for slot in v.get("availability_slots", []):
            if "_id" in slot:
                slot["_id"] = str(slot["_id"])
    return v

@router.get("")
async def list_venues(
    type: Optional[str] = None,
    city: Optional[str] = None,
    sort: str = "recommended",
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    min_capacity: Optional[int] = None,
    q: Optional[str] = None,
    page: int = 1, limit: int = 20,
):
    db = get_db()
    query = {"is_verified": True, "is_active": True}
    if type and type != "all":
        query["type"] = type.lower()
    if city:
        query["location.city"] = {"$regex": city, "$options": "i"}
    if min_price:
        query["pricing.base_per_day"] = {"$gte": min_price}
    if max_price:
        ex = query.get("pricing.base_per_day", {})
        ex["$lte"] = max_price
        query["pricing.base_per_day"] = ex
    if min_capacity:
        query["capacity.max"] = {"$gte": min_capacity}
    if q:
        query["$text"] = {"$search": q}

    sort_map = {
        "price_asc":   [("pricing.base_per_day", 1)],
        "price_desc":  [("pricing.base_per_day", -1)],
        "rating":      [("rating", -1)],
        "recommended": [("rating", -1), ("review_count", -1)],
    }
    sort_order = sort_map.get(sort, sort_map["recommended"])
    skip = (page - 1) * limit

    cursor = db.venues.find(query, {
        "name": 1, "type": 1, "location": 1, "pricing": 1,
        "capacity": 1, "rating": 1, "review_count": 1,
        "media": {"$slice": 1}, "is_verified": 1, "badge": 1, "is_active": 1,  "owner_id": 1,
    }).sort(sort_order).skip(skip).limit(limit)

    venues = []
    async for v in cursor:
        venues.append(_serialize_venue(v))

    total = await db.venues.count_documents(query)
    return {"venues": venues, "total": total, "page": page}


@router.get("/featured")
async def featured_venues():
    db = get_db()
    cursor = db.venues.find(
        {"is_verified": True, "is_active": True},
        {"name": 1, "type": 1, "location": 1, "pricing": 1,
         "rating": 1, "media": {"$slice": 1}, "badge": 1,
         "capacity": 1, "review_count": 1, "is_active": 1}
    ).sort("rating", -1).limit(5)
    venues = []
    async for v in cursor:
        venues.append(_serialize_venue(v))
    return {"venues": venues}


@router.get("/trending")
async def trending_venues():
    db = get_db()
    pipeline = [
        {"$match": {"created_at": {"$gte": datetime.utcnow() - timedelta(days=30)}}},
        {"$group": {"_id": "$venue_id", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}, {"$limit": 6},
        {"$lookup": {"from": "venues", "localField": "_id",
                     "foreignField": "_id", "as": "venue"}},
        {"$unwind": "$venue"},
    ]
    results = []
    async for r in db.bookings.aggregate(pipeline):
        v = r["venue"]
        v["booking_count"] = r["count"]
        results.append(_serialize_venue(v))

    if not results:
        cursor = db.venues.find(
            {"is_verified": True},
            {"name": 1, "type": 1, "location": 1, "pricing": 1,
             "rating": 1, "media": {"$slice": 1}, "capacity": 1,
             "review_count": 1, "is_active": 1, "facilities": 1}
        ).sort("rating", -1).limit(6)
        async for v in cursor:
            results.append(_serialize_venue(v))
    return {"venues": results}


@router.get("/mine")
async def owner_venues(user=Depends(require_role("owner"))):
    db = get_db()
    cursor = db.venues.find({"owner_id": user["_id"]})
    venues = []
    async for v in cursor:
        total_bookings = await db.bookings.count_documents({"venue_id": v["_id"]})
        pending_requests = await db.bids.count_documents(
            {"venue_ids": v["_id"], "status": "open"})
        v["total_bookings"] = total_bookings
        v["pending_requests"] = pending_requests
        venues.append(_serialize_venue(v))
    return {"venues": venues}


@router.get("/favourites")
async def get_favourites(user=Depends(get_current_user)):
    db = get_db()
    user_doc = await db.users.find_one({"_id": user["_id"]}, {"saved_venues": 1})
    saved_ids = user_doc.get("saved_venues", []) if user_doc else []
    venues = []
    async for v in db.venues.find({"_id": {"$in": saved_ids}, "is_active": True}):
        v["id"] = str(v.pop("_id"))
        v["owner_id"] = str(v.get("owner_id", ""))
        venues.append(v)
    return {"venues": venues}


@router.post("/{venue_id}/favourite")
async def toggle_favourite(venue_id: str, user=Depends(get_current_user)):
    db = get_db()
    venue_oid = ObjectId(venue_id)
    existing = await db.users.find_one(
        {"_id": user["_id"], "saved_venues": venue_oid}
    )
    if existing:
        await db.users.update_one(
            {"_id": user["_id"]},
            {"$pull": {"saved_venues": venue_oid}}
        )
        return {"saved": False}
    else:
        await db.users.update_one(
            {"_id": user["_id"]},
            {"$addToSet": {"saved_venues": venue_oid}}
        )
        return {"saved": True}


@router.get("/{venue_id}")
async def venue_detail(venue_id: str):
    db = get_db()
    v = await db.venues.find_one({"_id": ObjectId(venue_id)})
    if not v:
        raise HTTPException(404, "Venue not found")
    return {"venue": _serialize_venue(v)}


@router.post("")
async def create_venue(body: CreateVenueRequest, user=Depends(require_role("owner"))):
    db = get_db()
    result = await db.venues.insert_one({
        "owner_id": user["_id"],
        "name": body.name,
        "description": body.description,
        "type": body.type,
        "location": {
            "type": "Point",
            "coordinates": [body.location.longitude, body.location.latitude],
            "address": body.location.address,
            "city": body.location.city,
            "area": body.location.area,
        },
        "capacity": body.capacity.model_dump(),
        "pricing": body.pricing.model_dump(),
        "services": body.services,
        "facilities": body.facilities,
        "media": [],
        "availability_slots": [],
        "rating": 0.0, "review_count": 0,
        "is_verified": False, "is_active": True, "badge": None,
        "created_at": datetime.utcnow(), "updated_at": datetime.utcnow(),
    })
    return {
        "success": True,
        "venue_id": str(result.inserted_id),
        "message": "Venue submitted. Admin will verify within 24 hours."
    }


@router.put("/{venue_id}")
async def update_venue(venue_id: str, body: dict, user=Depends(require_role("owner"))):
    db = get_db()
    venue = await db.venues.find_one({"_id": ObjectId(venue_id)})
    if not venue or str(venue["owner_id"]) != str(user["_id"]):
        raise HTTPException(403, "Not your venue")

    if "location" in body:
        existing_location = venue.get("location", {})
        new_lat = body["location"].get("latitude")
        new_lng = body["location"].get("longitude")
        if new_lat is not None and new_lng is not None:
            new_coords = [new_lng, new_lat]
        else:
            new_coords = existing_location.get("coordinates", [74.1945, 32.1877])
        body["location"] = {
            "type": "Point",
            "coordinates": new_coords,
            "address": body["location"].get("address", existing_location.get("address", "")),
            "city": body["location"].get("city", existing_location.get("city", "Gujranwala")),
            "area": body["location"].get("area", existing_location.get("area", "")),
        }

    body["updated_at"] = datetime.utcnow()
    await db.venues.update_one({"_id": ObjectId(venue_id)}, {"$set": body})
    return {"success": True, "message": "Venue updated successfully."}

@router.post("/upload-image-base64")
async def upload_image_base64(
    body: dict,
    user=Depends(get_current_user)
):
    import base64
    image_data = base64.b64decode(body["image"])
    result = cloudinary.uploader.upload(
        image_data,
        folder="venuemate/venues",
        resource_type="image",
        public_id=f"venue_{str(user['_id'])}_{datetime.utcnow().timestamp()}"
    )
    return {"url": result["secure_url"]}

@router.get("/{venue_id}/blocked-dates")
async def get_blocked_dates(venue_id: str):
    db = get_db()
    venue = await db.venues.find_one(
        {"_id": ObjectId(venue_id)},
        {"blocked_dates": 1}
    )
    if not venue:
        raise HTTPException(404, "Venue not found")
    return {"blocked_dates": venue.get("blocked_dates", [])}


@router.put("/{venue_id}/block-dates")
async def update_blocked_dates(venue_id: str, body: dict, user=Depends(require_role("owner"))):
    db = get_db()
    blocked_dates = body.get("blocked_dates", [])
    await db.venues.update_one(
        {"_id": ObjectId(venue_id)},
        {"$set": {"blocked_dates": blocked_dates}}
    )
    return {"success": True}


@router.get("/owner/reviews")
async def owner_reviews(user=Depends(require_role("owner"))):
    db = get_db()
    owner_venue_ids = []
    async for v in db.venues.find({"owner_id": user["_id"]}, {"_id": 1, "name": 1}):
        owner_venue_ids.append(v["_id"])

    cursor = db.reviews.find(
        {"venue_id": {"$in": owner_venue_ids}},
        sort=[("created_at", -1)]
    )
    reviews = []
    async for r in cursor:
        venue = await db.venues.find_one({"_id": r["venue_id"]}, {"name": 1})
        customer = await db.users.find_one(
            {"_id": r["user_id"]}, {"profile_photo": 1}
        ) if r.get("user_id") else None
        reviews.append({
            "id": str(r["_id"]),
            "venue_name": venue["name"] if venue else "",
            "user_name": r.get("user_name", "Customer"),
            "user_photo": customer.get("profile_photo") if customer else None,
            "rating": r.get("rating", 5),
            "comment": r.get("comment", ""),
            "created_at": str(r.get("created_at", "")),
        })
    return {"reviews": reviews}
