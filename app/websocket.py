from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
from fastapi.exceptions import RequestValidationError # <-- ADD THIS
from fastapi.responses import JSONResponse # <-- ADD THIS
from pydantic import BaseModel
from typing import Optional
import asyncio
import hashlib
import time


router = APIRouter()
clients = set()
recent_alerts_cache = {}

class LogData(BaseModel):
    log: str
    label: str
    timestamp: str
    verdict: Optional[str] = None
    risk_score: Optional[float] = 0.0
    explanation: Optional[str] = ""
    is_alert: bool = False # Add this
    alert_info: Optional[dict] = None
    sequence_risk: Optional[float] = 0.0

class AlertData(BaseModel):
    log: str
    advice: str
    status: Optional[str] = None
    id: Optional[int] = None

class AlertEntryData(BaseModel):
    id: int
    status: str
    rule_name: str
    timestamp: str
    content: str
    risk_score: float

async def broadcast(message: dict):
    disconnected_clients = set()
    for client in clients.copy():
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

# @router.post("/api/new_log")
# async def new_log(data: LogData):
#     await broadcast({"type": "log", "data": data.dict()})
#     return {"status": "ok"}

@router.post("/api/new_log")
async def new_log(request: Request):
    try:
        # We try to parse the JSON and validate it with our model
        data_dict = await request.json()
        data = LogData(**data_dict)
        
        # If successful, broadcast and return ok
        await broadcast({"type": "log", "data": data.dict()})
        return {"status": "ok"}
        
    except RequestValidationError as e:
        # --- THIS IS THE DEBUGGING BLOCK ---
        # If validation fails, print the detailed error to your terminal
        print("\n--- VALIDATION ERROR ---")
        print(e.errors())
        print("--- END VALIDATION ERROR ---\n")
        # Still return a 422 so the worker knows it failed
        return JSONResponse(status_code=422, content={"detail": e.errors()})

@router.post("/api/new_alert")
async def new_alert(data: AlertData):
    """
    Receives a critical alert notification, aggregates it, and broadcasts intelligently.
    """
    log_content = data.log
    # Create a unique key for this type of alert (e.g., based on the first 50 chars)
    alert_key = hashlib.sha256(log_content[:50].encode()).hexdigest()
    current_time = time.time()

    if alert_key in recent_alerts_cache and (current_time - recent_alerts_cache[alert_key]['timestamp'] < 60):
        # --- This is a REPEATING alert ---
        # Increment the count
        recent_alerts_cache[alert_key]['count'] += 1
        recent_alerts_cache[alert_key]['timestamp'] = current_time
        
        # Broadcast an 'alert_update' message with the new count
        await broadcast({
            "type": "alert_update",
            "data": {
                "id": alert_key,
                "count": recent_alerts_cache[alert_key]['count']
            }
        })
    else:
        # --- This is a NEW alert ---
        # Add it to the cache with a count of 1
        recent_alerts_cache[alert_key] = {
            'count': 1,
            'timestamp': current_time,
            'log': log_content,
            'advice': data.advice
        }
        
        # Broadcast a 'new_alert' message with all the details
        await broadcast({
            "type": "new_alert",
            "data": data.dict()
        })

    return {"status": "ok"}

@router.post("/api/new_alert_entry")
async def new_alert_entry(data: AlertEntryData):
    """Receives a new actionable alert and broadcasts it to the anomaly feed."""
    await broadcast({"type": "new_actionable_alert", "data": data.dict()})
    return {"status": "ok"}



