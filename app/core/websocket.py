from typing import List, Dict, Any, Optional
import json
import asyncio
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
import logging

logger = logging.getLogger(__name__)

class ConnectionManager:
    """WebSocket connection manager"""
    
    def __init__(self):
        # Store active connections by user_id
        self.active_connections: Dict[int, WebSocket] = {}
        # Store connections by room/channel
        self.rooms: Dict[str, List[int]] = {}
        # Store user sessions
        self.user_sessions: Dict[int, Dict[str, Any]] = {}
    
    async def connect(self, websocket: WebSocket, user_id: int):
        """Accept WebSocket connection and store it"""
        await websocket.accept()
        self.active_connections[user_id] = websocket
        self.user_sessions[user_id] = {
            "connected_at": datetime.utcnow(),
            "last_activity": datetime.utcnow(),
            "status": "online"
        }
        
        logger.info(f"User {user_id} connected via WebSocket")
        
        # Notify user's contacts about online status
        await self.broadcast_user_status(user_id, "online")
    
    def disconnect(self, user_id: int):
        """Remove user connection"""
        if user_id in self.active_connections:
            del self.active_connections[user_id]
        
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]
        
        # Remove user from all rooms
        for room_name, users in self.rooms.items():
            if user_id in users:
                users.remove(user_id)
        
        logger.info(f"User {user_id} disconnected from WebSocket")
        
        # Notify user's contacts about offline status
        asyncio.create_task(self.broadcast_user_status(user_id, "offline"))
    
    async def send_personal_message(self, user_id: int, message: Dict[str, Any]):
        """Send message to specific user"""
        if user_id in self.active_connections:
            websocket = self.active_connections[user_id]
            try:
                await websocket.send_text(json.dumps(message))
                
                # Update last activity
                if user_id in self.user_sessions:
                    self.user_sessions[user_id]["last_activity"] = datetime.utcnow()
                
            except Exception as e:
                logger.error(f"Error sending message to user {user_id}: {str(e)}")
                # Remove stale connection
                self.disconnect(user_id)
    
    async def broadcast_to_room(self, room: str, message: Dict[str, Any], exclude_user: Optional[int] = None):
        """Broadcast message to all users in a room"""
        if room in self.rooms:
            for user_id in self.rooms[room]:
                if exclude_user and user_id == exclude_user:
                    continue
                await self.send_personal_message(user_id, message)
    
    async def broadcast_user_status(self, user_id: int, status: str):
        """Broadcast user status change to relevant users"""
        # This would typically notify mentors, assigned interns, etc.
        status_message = {
            "type": "user_status",
            "user_id": user_id,
            "status": status,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Get users who should be notified (mentors, assigned interns)
        relevant_users = await self.get_relevant_users_for_status(user_id)
        
        for relevant_user_id in relevant_users:
            await self.send_personal_message(relevant_user_id, status_message)
    
    def join_room(self, user_id: int, room: str):
        """Add user to a room"""
        if room not in self.rooms:
            self.rooms[room] = []
        
        if user_id not in self.rooms[room]:
            self.rooms[room].append(user_id)
        
        logger.info(f"User {user_id} joined room {room}")
    
    def leave_room(self, user_id: int, room: str):
        """Remove user from a room"""
        if room in self.rooms and user_id in self.rooms[room]:
            self.rooms[room].remove(user_id)
            
            # Clean up empty rooms
            if not self.rooms[room]:
                del self.rooms[room]
        
        logger.info(f"User {user_id} left room {room}")
    
    def get_online_users(self) -> List[int]:
        """Get list of currently online users"""
        return list(self.active_connections.keys())
    
    def is_user_online(self, user_id: int) -> bool:
        """Check if user is currently online"""
        return user_id in self.active_connections
    
    async def get_relevant_users_for_status(self, user_id: int) -> List[int]:
        """Get users who should be notified about status changes"""
        # This would query the database to find mentors, assigned interns, etc.
        # For now, return empty list - implement based on your business logic
        return []

# Global connection manager instance
manager = ConnectionManager()
