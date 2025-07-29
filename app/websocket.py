from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio

router = APIRouter()
clients = set()

# Broadcast message to all connected clients
async def broadcast(message):
    disconnected = set()
    for client in clients:
        try:
            await client.send_json(message)
        except:
            disconnected.add(client)
    clients.difference_update(disconnected)

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    clients.add(websocket)
    await broadcast({"type": "session_update", "count": len(clients)})
    try:
        while True:
            await asyncio.sleep(10)  # keep alive
    except WebSocketDisconnect:
        clients.remove(websocket)
        await broadcast({"type": "session_update", "count": len(clients)})

@router.post("/api/new_log")
async def new_log(data: dict):
    await broadcast({"type": "log", "data": data})
    return {"status": "ok"}

@router.post("/api/new_alert")
async def new_alert(data: dict):
    await broadcast({"type": "alert", "data": data})
    return {"status": "ok"}




