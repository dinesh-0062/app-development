import json
import logging
from typing import Dict, List, Set
from fastapi import WebSocket

logger = logging.getLogger("teachsync.ws")


class ConnectionManager:
    def __init__(self):
        # Map user_id -> List of active WebSockets
        self.active_connections: Dict[str, List[WebSocket]] = {}
        # Track online status
        self.online_users: Set[str] = set()

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        self.online_users.add(user_id)

        # Broadcast user online status
        await self.broadcast_presence(user_id, "online")
        logger.info(f"User {user_id} connected. Total active connections for user: {len(self.active_connections[user_id])}")

    def disconnect(self, websocket: WebSocket, user_id: str):
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
                self.online_users.discard(user_id)
        logger.info(f"User {user_id} disconnected.")

    async def send_personal_message(self, message: dict, user_id: str):
        if user_id in self.active_connections:
            dead_sockets = []
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending message to user {user_id}: {e}")
                    dead_sockets.append(connection)
            for ds in dead_sockets:
                self.disconnect(ds, user_id)

    async def broadcast_to_users(self, message: dict, user_ids: List[str]):
        for uid in user_ids:
            await self.send_personal_message(message, uid)

    async def broadcast_presence(self, user_id: str, status: str):
        msg = {
            "type": "presence_update",
            "payload": {
                "user_id": user_id,
                "status": status, # "online" or "offline"
            }
        }
        for uid in list(self.online_users):
            if uid != user_id:
                await self.send_personal_message(msg, uid)

    def is_online(self, user_id: str) -> bool:
        return user_id in self.online_users


manager = ConnectionManager()
