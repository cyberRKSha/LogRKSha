# app/routes.py (Final Fixes for Timezones and Paths)
from fastapi import APIRouter, Request, Response, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.concurrency import run_in_threadpool
from datetime import datetime, timezone, timedelta
from scripts.update import trigger_model_update
import sqlite3
import pandas as pd
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from pathlib import Path

# --- DYNAMIC PATH CONFIGURATION ---
current_dir = Path(__file__).parent
project_root = current_dir.parent
DATABASE_FILE = project_root / "log_database.db"
TEMPLATES_PATH = current_dir / "templates"

# --- Logging Helpers ---
def log_info(msg): print(f"\033[94mℹ️ {msg}\033[0m")
def log_error(msg): print(f"\033[91m❗ {msg}\033[0m")

def flexible_date_parser(date_string):
    try:
        # errors='raise' will trigger the 'except' block if it fails.
        return pd.to_datetime(date_string, errors='raise')
    except (ValueError, TypeError):
        # If the standard parser fails, try our custom format.
        try:
            # This is the format for 'Jul 19, 2025 10:42:57'
            return datetime.strptime(str(date_string), '%b %d, %Y %H:%M:%S')
        except (ValueError, TypeError):
            # If all attempts fail, return NaT (Not a Time) so it can be dropped.
            return pd.NaT

task_status = {
    "retrain": {"status": "idle", "message": "No active task."}
}

def run_update_and_set_status():
    try:
        trigger_model_update()
        task_status["retrain"] = {"status": "completed", "message": "Model retraining completed successfully."}
    except Exception as e:
        log_error(f"Model retraining failed: {e}")
        task_status["retrain"] = {"status": "failed", "message": f"Error during retraining: {e}"}

router = APIRouter()
templates = Jinja2Templates(directory=TEMPLATES_PATH)

# --- Pydantic Models ---
class SearchQuery(BaseModel):
    keyword: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    label: Optional[int] = None
    source: Optional[str] = None

class ReviewUpdateItem(BaseModel):
    id: int
    new_label: int

# --- Main Dashboard Route ---
@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    total_logs, normal_count, anomaly_count = 0, 0, 0
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        query = "SELECT final_label FROM logs WHERE is_reviewed = 1"
        df = pd.read_sql_query(query, conn)
        conn.close()
        if not df.empty:
            total_logs = len(df)
            normal_count = df[df['final_label'] == 0].shape[0]
            anomaly_count = df[df['final_label'] == 1].shape[0]
    except Exception as e:
        log_error(f"Could not read from database to get stats: {e}")
    last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "total_logs": total_logs,
        "normal_count": normal_count,
        "anomaly_count": anomaly_count,
        "last_updated": last_updated
    })

# --- Search API Route ---
@router.post("/api/search_logs", response_model=List[dict])
async def search_logs(query: SearchQuery):
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        conn.row_factory = sqlite3.Row
        sql_query = "SELECT id, timestamp, source, content, final_label FROM logs WHERE 1=1"
        params = []
        if query.keyword:
            sql_query += " AND content LIKE ?"
            params.append(f"%{query.keyword}%")
        if query.start_time:
            sql_query += " AND timestamp >= ?"
            # We pass the naive local time string directly to the query
            params.append(query.start_time)
        if query.end_time:
            sql_query += " AND timestamp <= ?"
            # We pass the naive local time string directly to the query
            params.append(query.end_time)
        if query.label is not None:
            sql_query += " AND final_label = ?"
            params.append(query.label)
        if query.source:
            sql_query += " AND source LIKE ?"
            params.append(f"%{query.source}%")
        sql_query += " ORDER BY timestamp DESC LIMIT 500;"
        cursor = conn.cursor()
        cursor.execute(sql_query, params)
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    except Exception as e:
        log_error(f"Error during log search: {e}")
        return []

# --- Historical Trends API Route (with Timezone and Cache-Busting Fix) ---

@router.get("/api/historical-trends")
async def get_historical_trends(response: Response, interval: str = 'h'):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        query = "SELECT timestamp FROM logs WHERE is_reviewed = 1 AND final_label = 1"
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if df.empty:
            return []

        # === THE FIX: Apply our new flexible parser to the timestamp column ===
        df['timestamp'] = df['timestamp'].apply(flexible_date_parser)
        # === END FIX ===

        if df.empty:
            return []
        
        df['timestamp'] = df['timestamp'].dt.tz_localize(None)
        
        df.set_index('timestamp', inplace=True)
        anomaly_logs = df.resample(interval).size()
        
        trends_df = pd.DataFrame({'anomalies': anomaly_logs}).fillna(0)
        trends_df.reset_index(inplace=True)
        trends_df['timestamp'] = trends_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M')
        
        return trends_df.to_dict(orient='records')
        
    except Exception as e:
        log_error(f"Error generating historical trends: {e}")
        return []

# --- Training Stats API Route ---
@router.get("/api/training_stats")
async def get_training_stats():
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        query = "SELECT final_label FROM logs WHERE is_reviewed = 1"
        df = pd.read_sql_query(query, conn)
        conn.close()
        if df.empty:
            return {"total": 0, "normal": 0, "anomaly": 0}
        return {
            "total": len(df),
            "normal": df[df['final_label'] == 0].shape[0],
            "anomaly": df[df['final_label'] == 1].shape[0],
        }
    except Exception as e:
        log_error(f"Error fetching training stats: {e}")
        return {"total": 0, "normal": 0, "anomaly": 0}


@router.get("/api/review/pending", response_model=List[Dict[str, Any]])
async def get_pending_logs_api(sort_by: Optional[str] = None):
    """
    API endpoint to get pending logs as JSON data.
    """
    def get_logs_from_db():
        conn = sqlite3.connect(DATABASE_FILE)
        conn.row_factory = sqlite3.Row
        query = "SELECT id, timestamp, source, content, predicted_label, final_label FROM logs WHERE is_reviewed = 0"
        if sort_by == '1':
            query += " ORDER BY predicted_label DESC, timestamp DESC"
        elif sort_by == '0':
            query += " ORDER BY predicted_label ASC, timestamp DESC"
        else:
            query += " ORDER BY timestamp DESC " # Limit to 200 to keep it fast
        
        entries = [dict(row) for row in conn.execute(query).fetchall()]
        conn.close()
        return entries

    return await run_in_threadpool(get_logs_from_db)


# This API endpoint receives the corrections from the review interface.
@router.post("/api/review/update")
async def update_reviews_api(updates: List[ReviewUpdateItem]):
    """
    API endpoint to receive and process reviewed logs.
    """
    def update_database():
        conn = sqlite3.connect(DATABASE_FILE)
        for item in updates:
            conn.execute(
                "UPDATE logs SET final_label = ?, is_reviewed = 1 WHERE id = ?",
                (item.new_label, item.id)
            )
        conn.commit()
        conn.close()
        return {"status": "ok", "updated_count": len(updates)}

    return await run_in_threadpool(update_database)


@router.get("/api/logs/context", response_model=List[Dict[str, Any]])
async def get_log_context(timestamp: str):

    def get_context_from_db():
        try:
            
            center_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            
            # Define the 20-second window
            start_time = center_time - timedelta(seconds=10)
            end_time = center_time + timedelta(seconds=10)

            conn = sqlite3.connect(DATABASE_FILE)
            conn.row_factory = sqlite3.Row
            
            # Query for all logs within the time window, sorted chronologically
            query = "SELECT * FROM logs WHERE timestamp BETWEEN ? AND ? ORDER BY timestamp ASC"
            params = (start_time.isoformat(), end_time.isoformat())
            
            # Convert the database rows to a list of dictionaries
            entries = [dict(row) for row in conn.execute(query, params).fetchall()]
            conn.close()
            return entries
        except Exception as e:
            log_error(f"Error fetching log context: {e}")
            return []

    return await run_in_threadpool(get_context_from_db)

@router.post("/api/model/retrain")
async def retrain_model(background_tasks: BackgroundTasks):

    if task_status["retrain"]["status"] == "running":
        return {"message": "Retraining is already in progress."}
    
    log_info("Received request to retrain model. Starting as a background task.")
    task_status["retrain"] = {"status": "running", "message": "Retraining in progress..."}
    
    background_tasks.add_task(run_update_and_set_status)
    
    return {"message": "Model retraining has been initiated."}

@router.get("/api/model/retrain/status")
async def get_retrain_status():

    return task_status["retrain"]