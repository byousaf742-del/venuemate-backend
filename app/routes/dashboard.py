from fastapi import APIRouter, Depends
from datetime import datetime, timedelta
from app.core.config import get_db
from app.core.security import require_role

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/owner/stats")
async def owner_stats(user=Depends(require_role("owner"))):
    db = get_db()
    venue_ids = []
    async for v in db.venues.find({"owner_id": user["_id"]}, {"_id": 1}):
        venue_ids.append(v["_id"])

    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0)
    week_start  = now - timedelta(days=7)

    rev_result = await db.transactions.aggregate([
        {"$match": {"owner_id": user["_id"],
                    "created_at": {"$gte": month_start}, "status": "success"}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
    ]).to_list(1)
    revenue = rev_result[0]["total"] if rev_result else 0

    active_bookings   = await db.bookings.count_documents(
        {"owner_id": user["_id"], "status": {"$in": ["confirmed","payment_pending","requested"]}}
    )
    new_bids          = await db.bids.count_documents(
        {"venue_ids": {"$in": venue_ids}, "status": "open"}
    )
    bookings_this_week = await db.bookings.count_documents(
        {"owner_id": user["_id"], "created_at": {"$gte": week_start}}
    )
    total_reviews = 0
    async for v in db.venues.find({"owner_id": user["_id"]}, {"review_count": 1}):
        total_reviews += v.get("review_count", 0)

    total_venues = len(venue_ids)
    total_bookings_count = await db.bookings.count_documents(
        {"owner_id": user["_id"]}
    )
    avg_rating_result = await db.venues.aggregate([
        {"$match": {"owner_id": user["_id"]}},
        {"$group": {"_id": None, "avg": {"$avg": "$rating"}}}
    ]).to_list(1)
    avg_rating = round(avg_rating_result[0]["avg"], 1) if avg_rating_result else 0.0

    return {
        "total_venues": total_venues,
        "total_bookings": total_bookings_count,
        "total_revenue": revenue,
        "avg_rating": avg_rating,
        "kpis": [
            {"title": "Total Revenue",
             "value": f"PKR {revenue/100000:.1f}L" if revenue >= 100000 else f"PKR {revenue:,}",
             "subtitle": "This month", "change_percent": 12.5, "is_positive": True},
            {"title": "Active Bookings",
             "value": str(active_bookings),
             "subtitle": f"{bookings_this_week} this week", "change_percent": 0, "is_positive": True},
            {"title": "New Bids",
             "value": str(new_bids),
             "subtitle": "Awaiting response", "change_percent": 0, "is_positive": True},
            {"title": "Reviews",
             "value": str(total_reviews),
             "subtitle": "Total received", "change_percent": 0, "is_positive": True},
        ]
    }

@router.get("/owner/revenue")
async def owner_revenue(user=Depends(require_role("owner"))):
    db = get_db()
    import calendar
    months = []
    now = datetime.utcnow()
    for i in range(5, -1, -1):
        month_date = now - timedelta(days=30 * i)
        year = month_date.year
        month = month_date.month
        month_name = calendar.month_abbr[month]
        start = datetime(year, month, 1)
        end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
        count = await db.bookings.count_documents({
            "owner_id": user["_id"],
            "created_at": {"$gte": start, "$lt": end}
        })
        months.append({
            "month": month_name,
            "bookings": count,
            "year": year,
        })
    return {"monthly": months}



@router.get("/owner/pending")
async def owner_pending(user=Depends(require_role("owner"))):
    db = get_db()
    venue_ids = []
    async for v in db.venues.find({"owner_id": user["_id"]}, {"_id": 1}):
        venue_ids.append(v["_id"])

    pending_bookings = []
    async for b in db.bookings.find(
        {"owner_id": user["_id"], "status": "requested"},
        sort=[("created_at", -1)], limit=5
    ):
        pending_bookings.append({
            "id": str(b["_id"]),
            "customer_name": b.get("customer_name", "Customer"),
            "event_type": b.get("event_type", ""),
            "event_date": b.get("event_date", ""),
            "guest_count": b.get("guest_count", 0),
            "total_amount": b.get("total_amount", 0),
        })

    pending_bids = []
    async for b in db.bids.find(
        {"venue_ids": {"$in": venue_ids}, "status": "open"},
        sort=[("created_at", -1)], limit=5
    ):
        pending_bids.append({
            "id": str(b["_id"]),
            "customer_name": b.get("user_name", "Customer"),
            "event_type": b.get("event_type", ""),
            "event_date": b.get("event_date", ""),
            "guest_count": b.get("guest_count", 0),
            "budget": b.get("budget", 0),
        })

    return {"pending_bookings": pending_bookings, "pending_bids": pending_bids}