"""
VenueMate API — Entry Point
Run with: uvicorn main:app --reload
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import connect_db, close_db
from app.core.indexes import create_indexes

from app.routes import auth, venues, bookings, bids, messages
from app.routes import notifications, dashboard, users, admin, ai
from app.routes import ws


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    await create_indexes()
    yield
    await close_db()


app = FastAPI(
    title="VenueMate API",
    version="1.0.0",
    description="Backend for the VenueMate marriage halls booking app",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(venues.router)
app.include_router(bookings.router)
app.include_router(bids.router)
app.include_router(messages.router)
app.include_router(notifications.router)
app.include_router(dashboard.router)
app.include_router(users.router)
app.include_router(admin.router)
app.include_router(ai.router)
app.include_router(ws.router)


@app.get("/")
async def root():
    return {"status": "API is Running"}
