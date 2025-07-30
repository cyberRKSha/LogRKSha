# from fastapi import APIRouter, WebSocket, WebSocketDisconnect
# import asyncio

# router = APIRouter()
# clients = set()

# # Broadcast message to all connected clients
# async def broadcast(message):
#     disconnected = set()
#     for client in clients:
#         try:
#             await client.send_json(message)
#         except:
#             disconnected.add(client)
#     clients.difference_update(disconnected)

# @router.websocket("/ws")
# async def websocket_endpoint(websocket: WebSocket):
#     await websocket.accept()
#     clients.add(websocket)
#     await broadcast({"type": "session_update", "count": len(clients)})
#     try:
#         while True:
#             await asyncio.sleep(10)  # keep alive
#     except WebSocketDisconnect:
#         clients.remove(websocket)
#         await broadcast({"type": "session_update", "count": len(clients)})

# @router.post("/api/new_log")
# async def new_log(data: dict):
#     await broadcast({"type": "log", "data": data})
#     return {"status": "ok"}

# @router.post("/api/new_alert")
# async def new_alert(data: dict):
#     await broadcast({"type": "alert", "data": data})
#     return {"status": "ok"}



from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel 
import asyncio

router = APIRouter()
clients = set()

# Ensure correct capitalization: BaseModel
class LogData(BaseModel):
    log: str
    label: str
    timestamp: str

# Ensure correct capitalization: BaseModel
class AlertData(BaseModel):
    log: str
    advice: str

# Broadcast message to all connected clients
async def broadcast(message: dict):
    disconnected_clients = set()
    for client in clients:
        try:
            await client.send_json(message)
        except Exception:
            disconnected_clients.add(client)
    # Remove clients that have disconnected
    clients.difference_update(disconnected_clients)

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    clients.add(websocket)
    # Notify all clients about the new session count
    await broadcast({"type": "session_update", "count": len(clients)})
    try:
        while True:
            # Keep the connection alive
            await asyncio.sleep(60)
    except WebSocketDisconnect:
        clients.remove(websocket)
        # Notify remaining clients about the session count change
        await broadcast({"type": "session_update", "count": len(clients)})

@router.post("/api/new_log")
async def new_log(data: LogData):
    """Receives a new log and broadcasts it."""
    await broadcast({"type": "log", "data": data.dict()})
    return {"status": "ok"}

@router.post("/api/new_alert")
async def new_alert(data: AlertData):
    """Receives a new alert and broadcasts it."""
    await broadcast({"type": "alert", "data": data.dict()})
    return {"status": "ok"}
