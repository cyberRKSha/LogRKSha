from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Optional
import asyncio

router = APIRouter()
clients = set()

class LogData(BaseModel):
    log: str
    label: str
    timestamp: str
    verdict: Optional[str] = None

class AlertData(BaseModel):
    log: str
    advice: str

async def broadcast(message: dict):
    disconnected_clients = set()
    for client in clients:
        try:
            await client.send_json(message)
        except Exception:
            disconnected_clients.add(client)
    clients.difference_update(disconnected_clients)

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    clients.add(websocket)
    await broadcast({"type": "session_update", "count": len(clients)})
    try:
        while True:
            await asyncio.sleep(60)
    except WebSocketDisconnect:
        clients.remove(websocket)
        await broadcast({"type": "session_update", "count": len(clients)})

@router.post("/api/new_log")
async def new_log(data: LogData):
    await broadcast({"type": "log", "data": data.dict()})
    return {"status": "ok"}

@router.post("/api/new_alert")
async def new_alert(data: AlertData):
    await broadcast({"type": "alert", "data": data.dict()})
    return {"status": "ok"}





