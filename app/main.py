import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import connect_to_mongo, close_mongo_connection
from app.services.scheduler_service import start_scheduler, stop_scheduler
from app.core.websocket_manager import manager

from app.routers import (
    auth,
    users,
    classes,
    meetings,
    chats,
    files,
    calls,
    notifications
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("teachsync")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting TeachSync Backend...")
    await connect_to_mongo()
    start_scheduler()
    yield
    # Shutdown
    logger.info("Shutting down TeachSync Backend...")
    stop_scheduler()
    await close_mongo_connection()


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static local uploads fallback
os.makedirs("static_uploads", exist_ok=True)
app.mount("/static_uploads", StaticFiles(directory="static_uploads"), name="static_uploads")

# Include Routers
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(users.router, prefix=settings.API_V1_STR)
app.include_router(classes.router, prefix=settings.API_V1_STR)
app.include_router(meetings.router, prefix=settings.API_V1_STR)
app.include_router(chats.router, prefix=settings.API_V1_STR)
app.include_router(files.router, prefix=settings.API_V1_STR)
app.include_router(calls.router, prefix=settings.API_V1_STR)
app.include_router(notifications.router, prefix=settings.API_V1_STR)


@app.get("/")
async def root():
    return {
        "app": settings.PROJECT_NAME,
        "status": "online",
        "docs": f"{settings.API_V1_STR}/docs"
    }


# WebSocket Endpoint for real-time messaging, typing indicators, presence & call signals
@app.websocket(f"{settings.API_V1_STR}/ws/{{user_id}}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await manager.connect(websocket, user_id)
    try:
        while True:
            data = await websocket.receive_json()
            event_type = data.get("type")

            # Handle typing indicator
            if event_type == "typing":
                target_user_ids = data.get("target_user_ids", [])
                await manager.broadcast_to_users({
                    "type": "user_typing",
                    "payload": {
                        "user_id": user_id,
                        "chat_id": data.get("chat_id")
                    }
                }, target_user_ids)

            # Handle call signaling (accept, decline, ICE candidates)
            elif event_type in ["call_accepted", "call_declined", "ice_candidate"]:
                target_id = data.get("target_user_id")
                if target_id:
                    await manager.send_personal_message(data, target_id)

    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}")
        manager.disconnect(websocket, user_id)
