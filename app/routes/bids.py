from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timedelta
from bson import ObjectId
from app.core.config import get_db
from app.core.security import get_current_user, require_role
from app.core.utils import push_notification
from app.models.schemas import CreateBidRequest, SendQuotationRequest, BidActionRequest

router = APIRouter(prefix="/api/bids", tags=["Bids"])


@router.post("")
async def create_bid(body: CreateBidRequest, user=Depends(get_current_user)):
    db = get_db()
    venue_oids = [ObjectId(vid) for vid in body.venue_ids]
    result = await db.bids.insert_one({
        "user_id": user["_id"],
        "user_name": user["name"],
        "venue_ids": venue_oids,
        "event_date": body.event_date,
        "event_type": body.event_type,
        "guest_count": body.guest_count,
        "budget": body.budget,
        "services_required": body.services_required,
        "message": body.message,
        "status": "open",
        "quotations": [],
        "accepted_quotation_id": None,
        "expires_at": datetime.utcnow() + timedelta(hours=72),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    })
    bid_id = str(result.inserted_id)

    notified_owners = set()
    async for v in db.venues.find({"_id": {"$in": venue_oids}}):
        owner_id = str(v["owner_id"])
        if owner_id not in notified_owners:
            notified_owners.add(owner_id)
            await push_notification(
                db, owner_id, "bid_received",
                "New Bid Received!",
                f"{user['name']} sent a bid for {body.event_type} on {body.event_date}",
                "bid", bid_id
            )
    return {"success": True, "bid_id": bid_id}


@router.get("/my")
async def my_bids(user=Depends(get_current_user)):
    db = get_db()
    cursor = db.bids.find(
        {"user_id": user["_id"]},
        sort=[("created_at", -1)]
    )
    bids = []
    async for b in cursor:
        venue_names = []
        vids = [v for v in b.get("venue_ids", [])]
        async for v in db.venues.find({"_id": {"$in": vids}}, {"name": 1}):
            venue_names.append(v["name"])
        bids.append({
            "id": str(b["_id"]),
            "event_type": b.get("event_type", ""),
            "event_date": b.get("event_date", ""),
            "budget": b.get("budget", 0),
            "guest_count": b.get("guest_count", 0),
            "services_required": b.get("services_required", []),
            "status": b.get("status", "open"),
            "quotation_count": len(b.get("quotations", [])),
            "venue_names": venue_names,
            "created_at": str(b.get("created_at", "")),
        })
    return {"bids": bids}


@router.get("/quotations/received")
async def quotations_received(user=Depends(get_current_user)):
    db = get_db()
    cursor = db.bids.find({
        "user_id": user["_id"],
        "quotations": {"$ne": []}
    })
    quotations = []
    async for b in cursor:
        for q in b.get("quotations", []):
            venue = await db.venues.find_one(
                {"_id": q["venue_id"]},
                {"name": 1, "media": {"$slice": 1}, "rating": 1}
            )
            quotations.append({
                "bid_id": str(b["_id"]),
                "quotation_id": str(q["_id"]),
                "venue_id": str(q["venue_id"]),
                "venue": venue["name"] if venue else "",
                "image": venue["media"][0]["url"] if venue and venue.get("media") else None,
                "rating": float(venue.get("rating", 0)) if venue else 0.0,
                "offered_price": q.get("amount", 0),
                "original_budget": b.get("budget", 0),
                "discount": float(q.get("discount_percent", 0)),
                "message": q.get("message", ""),
                "valid_until": q.get("valid_until", ""),
                "status": q.get("status", "pending"),
                "event_date": b.get("event_date", ""),
            })
    return {"quotations": quotations}


@router.get("/owner/received")
async def owner_received_bids(user=Depends(require_role("owner"))):
    db = get_db()
    owner_venue_ids = []
    async for v in db.venues.find({"owner_id": user["_id"]}, {"_id": 1}):
        owner_venue_ids.append(v["_id"])

    cursor = db.bids.find(
        {"venue_ids": {"$in": owner_venue_ids}},
        sort=[("created_at", -1)]
    )
    bids = []
    seen_bid_ids = set()
    async for b in cursor:
        bid_id_str = str(b["_id"])
        if bid_id_str in seen_bid_ids:
            continue
        seen_bid_ids.add(bid_id_str)
        already_quoted = any(
            str(q.get("owner_id")) == str(user["_id"])
            for q in b.get("quotations", [])
        )
        bids.append({
            "id": str(b["_id"]),
            "user_id": str(b["user_id"]),
            "customer_name": b.get("user_name", "Customer"),
            "customer_phone": b.get("customer_phone", ""),
            "event_type": b.get("event_type", ""),
            "event_date": b.get("event_date", ""),
            "budget": b.get("budget", 0),
            "guest_count": b.get("guest_count", 0),
            "services_required": b.get("services_required", []),
            "message": b.get("message", ""),
            "status": b.get("status", "open"),
            "already_quoted": already_quoted,
            "quotation_count": len(b.get("quotations", [])),
            "created_at": str(b.get("created_at", "")),
        })
    return {"bids": bids}


@router.get("/owner/quotations")
async def owner_sent_quotations(user=Depends(require_role("owner"))):
    db = get_db()
    cursor = db.bids.find(
        {"quotations.owner_id": user["_id"]},
        sort=[("created_at", -1)]
    )
    quotations = []
    async for b in cursor:
        for q in b.get("quotations", []):
            if str(q.get("owner_id")) == str(user["_id"]):
                venue = await db.venues.find_one(
                    {"_id": q["venue_id"]}, {"name": 1}
                )
                quotations.append({
                    "bid_id": str(b["_id"]),
                    "quotation_id": str(q["_id"]),
                    "customerName": b.get("user_name", "Customer"),
                    "offeredPrice": q.get("amount", 0),
                    "validUntil": q.get("valid_until", ""),
                    "message": q.get("message", ""),
                    "status": q.get("status", "pending"),
                    "venue_name": venue["name"] if venue else "",
                    "event_type": b.get("event_type", ""),
                    "event_date": b.get("event_date", ""),
                    "bidId": str(b["_id"]),
                })
    return {"quotations": quotations}


@router.post("/{bid_id}/quotation")
async def send_quotation(
    bid_id: str, body: SendQuotationRequest, user=Depends(require_role("owner"))
):
    db = get_db()
    bid = await db.bids.find_one({"_id": ObjectId(bid_id)})
    if not bid:
        raise HTTPException(404, "Bid not found")

    owner_venue = None
    if body.venue_id:
        owner_venue = await db.venues.find_one(
            {"_id": ObjectId(body.venue_id), "owner_id": user["_id"]}
        )
    if not owner_venue:
        async for v in db.venues.find(
            {"owner_id": user["_id"], "_id": {"$in": bid["venue_ids"]}}
        ):
            owner_venue = v
            break
    if not owner_venue:
        raise HTTPException(403, "Your venue is not part of this bid")

    quotation = {
        "_id": ObjectId(),
        "owner_id": user["_id"],
        "venue_id": owner_venue["_id"],
        "venue_name": owner_venue.get("name", ""),
        "amount": body.amount,
        "discount_percent": body.discount_percent,
        "message": body.message,
        "valid_until": body.valid_until,
        "package_details": body.package_details,
        "status": "pending",
        "created_at": datetime.utcnow(),
    }
    await db.bids.update_one(
        {"_id": ObjectId(bid_id)},
        {"$push": {"quotations": quotation},
         "$set": {"status": "countered", "updated_at": datetime.utcnow()}}
    )
    await push_notification(
        db, str(bid["user_id"]), "quotation_received",
        "New Quotation Received!",
        f"{owner_venue['name']} sent you a quote of PKR {body.amount:,}",
        "bid", bid_id
    )
    return {"success": True}


@router.put("/{bid_id}/action")
async def bid_action(
    bid_id: str, body: BidActionRequest, user=Depends(get_current_user)
):
    db = get_db()
    bid = await db.bids.find_one({"_id": ObjectId(bid_id)})
    if not bid:
        raise HTTPException(404, "Bid not found")

    # Owner declining the entire bid
    if body.action == "reject" and body.quotation_id is None:
        await db.bids.update_one(
            {"_id": ObjectId(bid_id)},
            {"$set": {"status": "rejected", "updated_at": datetime.utcnow()}}
        )
        await push_notification(
            db, str(bid["user_id"]),
            "bid_rejected",
            "Bid Declined",
            f"A venue has declined your bid for {bid.get('event_type', 'your event')}",
            "bid", bid_id
        )
        return {"success": True}

    # Customer accepting a specific quotation
    if body.action == "accept" and body.quotation_id:
        if str(bid["user_id"]) != str(user["_id"]):
            raise HTTPException(403, "Not your bid")
        await db.bids.update_one(
            {"_id": ObjectId(bid_id), "quotations._id": ObjectId(body.quotation_id)},
            {"$set": {
                "quotations.$.status": "accepted",
                "status": "accepted",
                "accepted_quotation_id": ObjectId(body.quotation_id),
                "updated_at": datetime.utcnow(),
            }}
        )
        accepted_q = next(
            (q for q in bid["quotations"] if str(q["_id"]) == body.quotation_id), None
        )
        if accepted_q:
            venue = await db.venues.find_one({"_id": accepted_q["venue_id"]})
            b_result = await db.bookings.insert_one({
                "venue_id": accepted_q["venue_id"],
                "user_id": user["_id"],
                "owner_id": accepted_q["owner_id"],
                "venue_name": venue["name"] if venue else "",
                "customer_name": user["name"],
                "customer_phone": user.get("phone", ""),
                "event_date": bid["event_date"],
                "event_type": bid["event_type"],
                "guest_count": bid["guest_count"],
                "status": "requested",
                "confirmation_token": None,
                "total_amount": accepted_q["amount"],
                "advance_paid": 0,
                "services_requested": bid["services_required"],
                "bid_id": bid["_id"],
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            })
            await db.bids.update_one(
                {"_id": ObjectId(bid_id)},
                {"$set": {"status": "converted"}}
            )
            return {"success": True, "booking_id": str(b_result.inserted_id)}

    # Customer rejecting a specific quotation
    if body.action == "reject" and body.quotation_id:
        if str(bid["user_id"]) != str(user["_id"]):
            raise HTTPException(403, "Not your bid")
        await db.bids.update_one(
            {"_id": ObjectId(bid_id), "quotations._id": ObjectId(body.quotation_id)},
            {"$set": {"quotations.$.status": "rejected"}}
        )
        return {"success": True}

    return {"success": True}
