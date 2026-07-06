from app.core.config import get_db

async def create_indexes():
    db = get_db()

    # users
    await db.users.create_index("email", unique=True)
    await db.users.create_index("phone", unique=True, sparse=True)

    # venues
    await db.venues.create_index([("location", "2dsphere")])
    await db.venues.create_index("owner_id")
    await db.venues.create_index("is_verified")
    await db.venues.create_index([("name", "text"), ("description", "text")])

    # bookings
    await db.bookings.create_index("user_id")
    await db.bookings.create_index("owner_id")
    await db.bookings.create_index([("venue_id", 1), ("event_date", 1)])

    # bids
    await db.bids.create_index("user_id")
    await db.bids.create_index("venue_ids")
    await db.bids.create_index("status")

    # messages
    await db.messages.create_index([("room_id", 1), ("created_at", 1)])

    # notifications
    await db.notifications.create_index([("user_id", 1), ("is_read", 1)])

    # analytics — auto-delete after 90 days
    await db.analytics_events.create_index(
        "created_at", expireAfterSeconds=60 * 60 * 24 * 90
    )

    print("✅ Indexes created")
