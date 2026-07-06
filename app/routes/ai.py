import os
import json
import httpx
from fastapi import APIRouter, Depends, HTTPException
from app.core.config import get_db, GEMINI_API_KEY
from app.core.security import get_current_user

router = APIRouter(prefix="/api/ai", tags=["AI"])

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.5-flash:generateContent"
)


@router.post("/recommendations")
async def get_recommendations(
    body: dict,
    user=Depends(get_current_user),
):
    if not GEMINI_API_KEY:
        raise HTTPException(500, "Gemini API key not configured")

    budget = body.get("budget", 0)
    guest_count = body.get("guest_count", 0)
    event_type = body.get("event_type", "")
    query = body.get("query", "")

    db = get_db()

    # Fetch all active verified venues
    cursor = db.venues.find(
        {"is_verified": True, "is_active": True},
        {
            "name": 1, "type": 1, "location": 1,
            "pricing": 1, "capacity": 1, "rating": 1,
            "review_count": 1, "facilities": 1, "badge": 1,
            "media": {"$slice": 1},
        }
    ).limit(20)

    venues = []
    async for v in cursor:
        venues.append({
            "id": str(v["_id"]),
            "name": v.get("name", ""),
            "type": v.get("type", ""),
            "area": v.get("location", {}).get("area", ""),
            "city": v.get("location", {}).get("city", ""),
            "price_per_day": v.get("pricing", {}).get("base_per_day", 0),
            "min_capacity": v.get("capacity", {}).get("min", 0),
            "max_capacity": v.get("capacity", {}).get("max", 0),
            "rating": v.get("rating", 0),
            "reviews": v.get("review_count", 0),
            "facilities": v.get("facilities", []),
            "badge": v.get("badge"),
            "image": (v.get("media") or [{}])[0].get("url", ""),
        })

    if not venues:
        return {"recommendations": [], "message": "No venues available yet."}

    venues_text = json.dumps(venues, ensure_ascii=False)

    prompt = f"""You are VenueMate AI, a venue recommendation assistant for Gujranwala, Pakistan.

Customer Request: "{query}"

Available Venues (JSON):
{venues_text}

Task: Recommend the top 3 most suitable venues from the list above based on the customer's request.

Rules:
- Only recommend venues from the provided list using their exact IDs
- Extract budget, guest count, event type, location preferences from the customer's request if mentioned
- Rank by suitability, then rating
- Keep each explanation to 1-2 sentences, friendly and helpful in English
- If fewer than 3 venues match, recommend what's available

Respond ONLY with a valid JSON array, no markdown, no extra text:
[
  {{
    "id": "venue_id_here",
    "name": "venue name",
    "reason": "Why this venue suits the customer",
    "match_score": 95
  }}
]"""

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{GEMINI_URL}?key={GEMINI_API_KEY}",
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.3,
                    "maxOutputTokens": 1024,
                },
            },
        )

    print("GEMINI STATUS:", resp.status_code)
    print("GEMINI RESPONSE:", resp.text[:500])

    if resp.status_code != 200:
        raise HTTPException(500, f"Gemini API error: {resp.text}")

    raw = resp.json()
    text = raw["candidates"][0]["content"]["parts"][0]["text"]

    # Strip markdown fences if present
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()

    try:
        ranked = json.loads(text)
    except Exception:
        raise HTTPException(500, "Failed to parse AI response")

    # Enrich with full venue data
    venue_map = {v["id"]: v for v in venues}
    results = []
    for r in ranked[:3]:
        vid = r.get("id", "")
        if vid in venue_map:
            v = venue_map[vid]
            results.append({
                "id": vid,
                "name": v["name"],
                "type": v["type"],
                "area": v["area"],
                "city": v["city"],
                "price_per_day": v["price_per_day"],
                "min_capacity": v["min_capacity"],
                "max_capacity": v["max_capacity"],
                "rating": v["rating"],
                "reviews": v["reviews"],
                "facilities": v["facilities"],
                "image": v["image"],
                "reason": r.get("reason", ""),
                "match_score": r.get("match_score", 0),
            })

    return {"recommendations": results}
