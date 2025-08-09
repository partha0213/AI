# app/api/v1/websocket.py (Complete Implementation)
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from app.core.websocket import manager
from app.api.deps import get_current_user_websocket
import json

router = APIRouter()

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    """WebSocket endpoint for real-time communication"""
    try:
        # Authenticate user (simplified)
        user = await get_current_user_websocket(websocket, user_id)
        if not user:
            await websocket.close(code=4001, reason="Authentication failed")
            return
        
        # Connect user
        await manager.connect(websocket, user_id)
        
        # Send welcome message
        await manager.send_personal_message(user_id, {
            "type": "connection",
            "message": "Connected successfully",
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        try:
            while True:
                # Receive messages from client
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                # Handle different message types
                await handle_websocket_message(user_id, message_data)
                
        except WebSocketDisconnect:
            manager.disconnect(user_id)
            print(f"User {user_id} disconnected")
            
    except Exception as e:
        print(f"WebSocket error: {e}")
        await websocket.close(code=4000, reason="Internal error")

async def handle_websocket_message(user_id: int, message_data: dict):
    """Handle incoming WebSocket messages"""
    message_type = message_data.get("type")
    
    if message_type == "ping":
        await manager.send_personal_message(user_id, {"type": "pong"})
    elif message_type == "task_progress":
        # Handle task progress updates
        await broadcast_task_progress_update(message_data)
    elif message_type == "chat_message":
        # Handle real-time chat
        await handle_chat_message(user_id, message_data)
