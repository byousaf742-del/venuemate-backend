from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from datetime import datetime
from bson import ObjectId
import asyncio
import io
from app.core.config import get_db
from app.core.security import get_current_user, require_role
from app.core.utils import push_notification, make_token
from app.core.booking_token_pdf import generate_booking_token_pdf
from app.models.schemas import CreateBookingRequest, BookingActionRequest, PaymentRequest

router = APIRouter(prefix="/api/bookings", tags=["Bookings"])


@router.post("")
async def create_booking(body: CreateBookingRequest, user=Depends(get_current_user)):
    db = get_db()
    venue = await db.venues.find_one({"_id": ObjectId(body.venue_id)})
    if not venue:
        raise HTTPException(404, "Venue not found")

    conflict = await db.bookings.find_one({
        "venue_id": ObjectId(body.venue_id),
        "event_date": body.event_date,
        "status": {"$in": ["requested", "approved", "payment_pending", "confirmed"]},
    })
    if conflict:
        raise HTTPException(400, "Venue is already booked for that date")

    result = await db.bookings.insert_one({
        "venue_id": ObjectId(body.venue_id),
        "user_id": user["_id"],
        "owner_id": venue["owner_id"],
        "venue_name": venue["name"],
        "customer_name": user["name"],
        "customer_phone": user.get("phone", ""),
        "customer_photo": user.get("profile_photo", ""),
        "venue_image": venue["media"][0]["url"] if venue.get("media") else None,
        "event_date": body.event_date,
        "event_time": body.event_time,
        "event_type": body.event_type,
        "guest_count": body.guest_count,
        "status": "requested",
        "confirmation_token": None,
        "total_amount": venue["pricing"]["base_per_day"],
        "advance_paid": 0,
        "services_requested": body.services_requested,
        "notes": body.notes,
        "bid_id": ObjectId(body.bid_id) if body.bid_id else None,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    })
    booking_id = str(result.inserted_id)

    await push_notification(
        db, str(venue["owner_id"]),
        "booking_request",
        "New Booking Request",
        f"{user['name']} wants to book {venue['name']} on {body.event_date}",
        "booking", booking_id
    )

    return {"success": True, "booking_id": booking_id}


@router.get("/my")
async def my_bookings(user=Depends(get_current_user)):
    db = get_db()
    cursor = db.bookings.find({"user_id": user["_id"]}, sort=[("created_at", -1)])
    bookings = []
    async for b in cursor:
        b["id"] = str(b.pop("_id"))
        b["venue_id"] = str(b["venue_id"])
        b["user_id"] = str(b["user_id"])
        b["owner_id"] = str(b["owner_id"])
        if b.get("bid_id"):
            b["bid_id"] = str(b["bid_id"])
        bookings.append(b)
    return {"bookings": bookings}


@router.get("/owner")
async def owner_bookings(user=Depends(require_role("owner"))):
    db = get_db()
    cursor = db.bookings.find(
        {"owner_id": user["_id"]},
        sort=[("created_at", -1)]
    )
    bookings = []
    async for b in cursor:
        customer = await db.users.find_one({"_id": b["user_id"]})
        bookings.append({
            "id": str(b["_id"]),
            "venue_id": str(b["venue_id"]),
            "user_id": str(b["user_id"]),
            "owner_id": str(b["owner_id"]),
            "venue_name": b.get("venue_name", ""),
            "venue_image": b.get("venue_image"),
            "event_date": b.get("event_date", ""),
            "event_time": b.get("event_time", ""),
            "event_type": b.get("event_type", ""),
            "guest_count": b.get("guest_count", 0),
            "status": b.get("status", ""),
            "confirmation_token": b.get("confirmation_token"),
            "total_amount": b.get("total_amount", 0),
            "advance_paid": b.get("advance_paid", 0),
            "notes": b.get("notes"),
            "customer_name": b.get("customer_name", "Customer"),
            "customer_phone": b.get("customer_phone", ""),
            "customer_photo": customer.get("profile_photo", "") if customer else "",
            "created_at": str(b.get("created_at", "")),
        })
    return {"bookings": bookings}


@router.put("/{booking_id}/action")
async def booking_action(
    booking_id: str,
    body: BookingActionRequest,
    user=Depends(get_current_user)
):
    db = get_db()
    booking = await db.bookings.find_one({"_id": ObjectId(booking_id)})
    if not booking:
        raise HTTPException(404, "Booking not found")

    updates = {"updated_at": datetime.utcnow()}
    if body.action == "approve":
        if str(booking["owner_id"]) != str(user["_id"]):
            raise HTTPException(403, "Only owner can approve")
        updates["status"] = "payment_pending"
        await push_notification(
            db, str(booking["user_id"]), "booking_approved",
            "Booking Approved!", "Please pay the advance to confirm.",
            "booking", booking_id
        )
    elif body.action == "cancel":
        updates["status"] = "cancelled"
        await push_notification(
            db, str(booking["user_id"]), "booking_cancelled",
            "Booking Cancelled",
            f"Your booking for {booking.get('venue_name', 'venue')} on {booking.get('event_date', '')} has been cancelled.",
            "booking", booking_id
        )
    elif body.action == "complete":
        if str(booking["owner_id"]) != str(user["_id"]):
            raise HTTPException(403, "Only owner can complete")
        updates["status"] = "completed"
        await push_notification(
            db, str(booking["user_id"]), "booking_completed",
            "Booking Completed!",
            f"Your event at {booking.get('venue_name', 'venue')} has been marked as completed.",
            "booking", booking_id
        )

    await db.bookings.update_one({"_id": ObjectId(booking_id)}, {"$set": updates})
    return {"success": True, "status": updates["status"]}


@router.post("/{booking_id}/pay")
async def pay_booking(
    booking_id: str,
    body: PaymentRequest,
    user=Depends(get_current_user)
):
    db = get_db()
    booking = await db.bookings.find_one({"_id": ObjectId(booking_id)})
    if not booking:
        raise HTTPException(404, "Booking not found")
    if str(booking["user_id"]) != str(user["_id"]):
        raise HTTPException(403, "Not your booking")

    token = make_token()
    await db.transactions.insert_one({
        "booking_id": booking["_id"],
        "user_id": user["_id"],
        "owner_id": booking["owner_id"],
        "amount": body.amount,
        "type": "advance",
        "status": "success",
        "gateway": body.gateway,
        "gateway_ref": body.gateway_ref,
        "created_at": datetime.utcnow(),
    })
    await db.bookings.update_one(
        {"_id": ObjectId(booking_id)},
        {"$set": {
            "status": "confirmed",
            "confirmation_token": token,
            "advance_paid": body.amount,
            "updated_at": datetime.utcnow(),
        }}
    )
    await push_notification(
        db, str(booking["owner_id"]), "payment_received",
        "Payment Received",
        f"Advance received for booking on {booking['event_date']}",
        "booking", booking_id
    )
    return {"success": True, "confirmation_token": token}


@router.get("/{booking_id}/token-pdf")
async def download_booking_token(
    booking_id: str,
    user=Depends(get_current_user)
):
    db = get_db()

    booking = await db.bookings.find_one({"_id": ObjectId(booking_id)})
    if not booking:
        raise HTTPException(404, "Booking not found")

    if str(booking["user_id"]) != str(user["_id"]):
        raise HTTPException(403, "Access denied")

    if booking.get("status") != "confirmed":
        raise HTTPException(400, "Token only available for confirmed bookings")

    venue_doc, customer_doc, owner_doc = await asyncio.gather(
        db.venues.find_one({"_id": booking["venue_id"]}),
        db.users.find_one({"_id": booking["user_id"]}),
        db.users.find_one({"_id": booking["owner_id"]}),
    )

    if not venue_doc or not customer_doc or not owner_doc:
        raise HTTPException(500, "Could not load booking details")

    booking["id"]   = str(booking.pop("_id"))
    venue_doc["id"] = str(venue_doc.pop("_id"))

    pdf_bytes = generate_booking_token_pdf(
        booking=booking,
        venue=venue_doc,
        customer=customer_doc,
        owner=owner_doc,
    )

    token_num = booking.get("confirmation_token", booking_id)
    filename  = f"VenueMate_Token_{token_num}.pdf"

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
