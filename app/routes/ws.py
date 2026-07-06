from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Dict, List
from datetime import datetime
from bson import ObjectId
import jwt
from app.core.config import JWT_SECRET, get_db

router = APIRouter(tags=["WebSocket"])

# room_id -> list of connected websockets
_rooms: Dict[str, List[WebSocket]] = {}


async def _authenticate(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        db = get_db()
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        return user
    except Exception:
        return None


@router.websocket("/ws/chat/{room_id}")
async def websocket_chat(
    websocket: WebSocket,
    room_id: str,
    token: str = Query(...),
):
    user = await _authenticate(token)
    if not user:
        await websocket.close(code=4001)
        return

    await websocket.accept()

    if room_id not in _rooms:
        _rooms[room_id] = []
    _rooms[room_id].append(websocket)

    try:
        while True:
            data = await websocket.receive_json()
            content = data.get("content", "").strip()
            receiver_id = data.get("receiver_id", "")
            if not content or not receiver_id:
                continue

            db = get_db()
            now = datetime.utcnow()
            doc = {
                "room_id": room_id,
                "sender_id": user["_id"],
                "receiver_id": ObjectId(receiver_id),
                "type": "text",
                "content": content,
                "is_read": False,
                "created_at": now,
                "hidden_for": [],
            }
            result = await db.messages.insert_one(doc)

            message_out = {
                "id": str(result.inserted_id),
                "text": content,
                "time": now.strftime("%I:%M %p"),
                "sender_id": str(user["_id"]),
            }

            # Broadcast to all clients in the room
            dead = []
            for ws in _rooms.get(room_id, []):
                try:
                    await ws.send_json(message_out)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                _rooms[room_id].remove(ws)

    except WebSocketDisconnect:
        if room_id in _rooms and websocket in _rooms[room_id]:
            _rooms[room_id].remove(websocket)
        if room_id in _rooms and not _rooms[room_id]:
            del _rooms[room_id]
