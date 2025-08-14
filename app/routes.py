# app/routes.py (Final Fixes for Timezones and Paths)
from fastapi import APIRouter, Request, Response, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.concurrency import run_in_threadpool
from app.websocket import broadcast
from datetime import datetime, timezone, timedelta
from scripts.update import trigger_model_update
import sqlite3
import pandas as pd
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from pathlib import Path
import dill
from sklearn.pipeline import make_pipeline
import joblib
import traceback

# --- DYNAMIC PATH CONFIGURATION ---
current_dir = Path(__file__).parent
project_root = current_dir.parent
DATABASE_FILE = project_root / "log_database.db"
TEMPLATES_PATH = current_dir / "templates"
EMBEDDER_PATH = project_root / "model/sentence_embedder.pkl"
SUPERVISED_MODEL_PATH = project_root / "model/sgd_embedder.pkl"
EXPLAINER_PATH = project_root / "model/lime_explainer.pkl"

embedder = joblib.load(EMBEDDER_PATH)
supervised_model = joblib.load(SUPERVISED_MODEL_PATH)
with open(EXPLAINER_PATH, 'rb') as f:
    explainer = dill.load(f)

# --- Logging Helpers ---
def log_info(msg): print(f"\033[94mℹ️ {msg}\033[0m")
def log_error(msg): print(f"\033[91m❗ {msg}\033[0m")


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

class AlertStatusUpdate(BaseModel):
    status: str

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

def generate_simple_explanation_html(explanation_list: list) -> str:
    """Takes a LIME explanation list and returns a simple, clean HTML snippet."""
    if not explanation_list:
        return "<p class='explanation-error'>LIME was unable to find significant features for this log.</p>"

    # Filter for only the words that POSITIVELY contribute to the anomaly score
    positive_contributors = [item for item in explanation_list if item[1] > 0]
    positive_contributors.sort(key=lambda x: x[1], reverse=True)

    if not positive_contributors:
        return "<p class='explanation-error'>LIME found no features that point towards an anomaly.</p>"

    html = "<div><p>The model flagged this log as an anomaly primarily because of these words:</p>"
    html += '<div class="explanation-words">'
    for word, score in positive_contributors:
        # Use opacity to show the "weight" or importance of the word
        opacity = max(0.2, min(1.0, score * 5))
        html += f'<span style="background-color: rgba(220, 53, 69, {opacity}); padding: 2px 5px; border-radius: 4px; margin: 2px; display: inline-block; color: white;">{word}</span>'
    html += "</div></div>"
    return html

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
# @router.post("/api/search_logs", response_model=List[dict])
# async def search_logs(query: SearchQuery):
#     try:
#         conn = sqlite3.connect(DATABASE_FILE)
#         conn.row_factory = sqlite3.Row
#         sql_query = "SELECT id, timestamp, source, content, final_label, risk_score FROM logs WHERE 1=1"
#         params = []
#         if query.keyword:
#             sql_query += " AND content LIKE ?"
#             params.append(f"%{query.keyword}%")
#         if query.start_time:
#             sql_query += " AND timestamp >= ?"
#             # We pass the naive local time string directly to the query
#             params.append(query.start_time)
#         if query.end_time:
#             sql_query += " AND timestamp <= ?"
#             # We pass the naive local time string directly to the query
#             params.append(query.end_time)
#         if query.label is not None:
#             sql_query += " AND final_label = ?"
#             params.append(query.label)
#         if query.source:
#             sql_query += " AND source LIKE ?"
#             params.append(f"%{query.source}%")
#         sql_query += " ORDER BY timestamp DESC LIMIT 500;"
#         cursor = conn.cursor()
#         cursor.execute(sql_query, params)
#         results = [dict(row) for row in cursor.fetchall()]
#         conn.close()
#         return results
#     except Exception as e:
#         log_error(f"Error during log search: {e}")
#         return []

@router.post("/api/search_logs", response_model=List[dict])
async def search_logs(query: SearchQuery):
    def get_search_results():
        conn = sqlite3.connect(DATABASE_FILE)
        conn.row_factory = sqlite3.Row
        # THE FIX: Use a LEFT JOIN to get the alert status if it exists
        sql_query = """
            SELECT l.id, l.timestamp, l.source, l.content, l.final_label, l.risk_score, a.status
            FROM logs l
            LEFT JOIN alerts a ON l.id = a.log_id
            WHERE 1=1
        """
        params = []
        
        # ... (The rest of the query building with params is the same as before)
        if query.keyword:
            sql_query += " AND l.content LIKE ?"
            params.append(f"%{query.keyword}%")
        if query.start_time:
            sql_query += " AND l.timestamp >= ?"
            params.append(query.start_time)
        if query.end_time:
            sql_query += " AND l.timestamp <= ?"
            params.append(query.end_time)
        if query.label is not None:
            sql_query += " AND l.final_label = ?"
            params.append(query.label)
        if query.source:
            sql_query += " AND l.source LIKE ?"
            params.append(f"%{query.source}%")

        sql_query += " ORDER BY l.timestamp DESC LIMIT 500;"
        
        results = [dict(row) for row in conn.execute(sql_query, params).fetchall()]
        conn.close()
        return results

    try:
        return await run_in_threadpool(get_search_results)
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
        # query = "SELECT id, timestamp, source, content, predicted_label, final_label, risk_score FROM logs WHERE is_reviewed = 0"
        
        query = """
            SELECT l.*, a.status
            FROM logs l
            LEFT JOIN alerts a ON l.id = a.log_id
            WHERE l.is_reviewed = 0
        """
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
            # Step 1: Parse the incoming UTC timestamp string from the browser
            center_time_utc = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            
            # Step 2: Convert the UTC time to the server's local timezone (e.g., IST)
            center_time_local_aware = center_time_utc.astimezone()
            
            # Step 3: Make it timezone-naive to match the strings stored in the database
            center_time_local_naive = center_time_local_aware.replace(tzinfo=None)

            # Step 4: Define the time window using the corrected local time
            start_time = center_time_local_naive - timedelta(seconds=10)
            end_time = center_time_local_naive + timedelta(seconds=10)

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

@router.get("/api/alerts")
async def get_alerts():
    """Fetches all open alerts (status is 'New' or 'Acknowledged')."""
    def get_alerts_from_db():
        conn = sqlite3.connect(DATABASE_FILE, timeout=10)
        conn.row_factory = sqlite3.Row
        query = """
            SELECT a.id, a.status, a.rule_name, l.timestamp, l.content, l.risk_score
            FROM alerts a JOIN logs l ON a.log_id = l.id
            WHERE a.status IN ('New', 'Acknowledged')
            ORDER BY l.timestamp DESC LIMIT 100
        """
        alerts = [dict(row) for row in conn.execute(query).fetchall()]
        conn.close()
        return alerts
    return await run_in_threadpool(get_alerts_from_db)

@router.post("/api/alerts/{alert_id}/status")
async def update_alert_status(alert_id: int, update: AlertStatusUpdate):
    """Updates an alert's status and broadcasts the change."""
    
    def update_and_get_log_id():
        conn = sqlite3.connect(DATABASE_FILE, timeout=10)
        # First, update the status
        conn.execute("UPDATE alerts SET status = ? WHERE id = ?", (update.status, alert_id))
        conn.commit()
        # Now, get the associated log_id to broadcast it
        log_id = conn.execute("SELECT log_id FROM alerts WHERE id = ?", (alert_id,)).fetchone()
        conn.close()
        return log_id[0] if log_id else None

    log_id = await run_in_threadpool(update_and_get_log_id)
    
    # After updating the database, broadcast the change to all clients
    await broadcast({
        "type": "alert_status_update",
        "data": {
            "alert_id": alert_id,
            "log_id": log_id,
            "new_status": update.status
        }
    })
    
    return {"message": "Alert status updated successfully"}


@router.get("/api/logs/{log_id}/explain")
async def get_explanation(log_id: int):

    def generate_lime_explanation():
        conn = sqlite3.connect(DATABASE_FILE, timeout=10)
        
        try:
            log_content = conn.execute("SELECT content FROM logs WHERE id = ?", (log_id,)).fetchone()

            if not log_content:
                return {"error": "Log not found"}

            line = log_content[0]
        
        
            log_info(f"Generating LIME explanation for log ID: {log_id}")
            def predictor_fn(text_list):
                embeddings = embedder.encode(text_list)
                return supervised_model.predict_proba(embeddings)

            exp = explainer.explain_instance(
                line, 
                predictor_fn, 
                num_features=6, 
                labels=[1]
            )
            explanation_list = exp.as_list(label=1)
            html = generate_simple_explanation_html(explanation_list)

            if html:
                conn.execute("UPDATE logs SET explanation = ? WHERE id = ?", (html, log_id))
                conn.commit()
                # log_info(f"Saved new explanation for log ID: {log_id}")

            return {"explanation_html": html}
        
        except Exception as e:
            log_error(f"Error generating LIME explanation for log ID {log_id}: {e}")
            traceback.print_exc()
            return {"error": f"Could not generate explanation: {e}"}
        finally:
            if conn:
                conn.close()
                log_info(f"Database connection closed for log ID: {log_id}.")

    return await run_in_threadpool(generate_lime_explanation)