# app/api/dashboard.py
from fastapi import APIRouter, Request, Response, BackgroundTasks, Depends, Form, status, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.concurrency import run_in_threadpool
from fastapi.templating import Jinja2Templates
from sentence_transformers import SentenceTransformer
import joblib, dill, psycopg2, psycopg2.extras, pandas as pd, json, re, traceback, io
from collections import Counter
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine, text
import geoip2.database
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from playwright.async_api import async_playwright
from PyPDF2 import PdfWriter, PdfReader
import base64, logging

from app.config import settings
from app import auth_utils
from app.websocket import broadcast
from app.websocket import broadcast
from scripts.update import trigger_model_update
from .models import SearchQuery, AlertStatusUpdate
from app.services.cache import cache

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Dashboard"])

embedder = None
supervised_model = None
explainer = None

def get_models():
    """Loads the ML models on first use and caches them."""
    global embedder, supervised_model, explainer

    if embedder is None:
        logger.info("Loading SentenceTransformer model for the first time...")
        embedder = SentenceTransformer(str(settings.EMBEDDER_PATH))
        logger.info("Model loaded.")

    if supervised_model is None:
        supervised_model = joblib.load(settings.SUPERVISED_MODEL_PATH)

    if explainer is None:
        with open(settings.EXPLAINER_PATH, 'rb') as f:
            explainer = dill.load(f)

    return embedder, supervised_model, explainer

# embedder = SentenceTransformer(str(settings.EMBEDDER_PATH))
# supervised_model = joblib.load(settings.SUPERVISED_MODEL_PATH)
# with open(settings.EXPLAINER_PATH, 'rb') as f:
#     explainer = dill.load(f)
templates = Jinja2Templates(directory=settings.TEMPLATES_PATH)
GEOIP_DB_PATH = settings.GEOIP_PATH
try:
    geoip_reader = geoip2.database.Reader(GEOIP_DB_PATH)
except FileNotFoundError:
    logger.error(f"GeoIP database not found at {GEOIP_DB_PATH}. The threat map will not work.")
    geoip_reader = None

task_status = {
    "retrain": {"status": "idle", "message": "No active task."}
}

def run_update_and_set_status():
    try:
        trigger_model_update()
        task_status["retrain"] = {"status": "completed", "message": "Model retraining completed successfully."}
    except Exception as e:
        logger.error(f"Model retraining failed: {e}")
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
        opacity = max(0.2, min(1.0, score * 5))
        html += f'<span style="background-color: rgba(220, 53, 69, {opacity}); padding: 2px 5px; border-radius: 4px; margin: 2px; display: inline-block; color: white;">{word}</span>'
    html += "</div></div>"
    return html

def extract_ip_from_string(log_line: str):
    match = re.search(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", log_line)
    return match.group(0) if match else None

def get_search_results(query: SearchQuery):

    engine = create_engine(settings.DATABASE_URL)
    
    base_query = """
        SELECT l.id, l.timestamp, l.source, l.content, l.final_label, l.risk_score, l.sequence_risk, l.threat_intel, a.status
        FROM logs l LEFT JOIN alerts a ON l.id = a.log_id
    """
    
    # List to hold all final WHERE conditions
    all_conditions = []
    params = {}

    # --- Step 1: Handle Keyword Search Separately ---
    if query.keyword:
        keywords = [kw for kw in query.keyword.strip().split() if kw]
        if keywords:
            keyword_clauses = []
            for i, keyword in enumerate(keywords):
                param_name = f"keyword_{i}"
                keyword_clauses.append(f"l.content ILIKE :{param_name}")
                params[param_name] = f"%{keyword}%"
            # Create a self-contained, parenthesized block for keywords
            all_conditions.append(f"({' AND '.join(keyword_clauses)})")

    # --- Step 2: Handle all other filters ---
    other_filters = []
    if query.ip_address:
        other_filters.append("l.content LIKE :ip_address")
        params["ip_address"] = f"%{query.ip_address}%"
    
    if query.source:
        other_filters.append("l.source ILIKE :source")
        params["source"] = f"%{query.source}%"

    if query.detection_method:
        other_filters.append("l.verdict = :detection_method")
        params["detection_method"] = query.detection_method

    if query.risk_score_min is not None:
        other_filters.append("l.risk_score >= :risk_score_min")
        params["risk_score_min"] = query.risk_score_min

    if query.start_time:
        other_filters.append("l.timestamp >= :start_time")
        params["start_time"] = query.start_time

    if query.end_time:
        other_filters.append("l.timestamp <= :end_time")
        params["end_time"] = query.end_time
    
    # --- Step 3: Combine 'other_filters' based on logic ---
    if other_filters:
        joiner = " AND " if query.filter_logic == 'and' else " OR "
        if len(other_filters) > 1:
             all_conditions.append(f"({joiner.join(other_filters)})")
        else:
            all_conditions.append(other_filters[0])

    # --- Step 4: Build the final query string ---
    full_query_str = base_query
    if all_conditions:
        # Always join the main blocks (keywords and other_filters) with AND
        full_query_str += f" WHERE {' AND '.join(all_conditions)}"

    full_query_str += " ORDER BY l.timestamp DESC LIMIT 500"
    
    try:
        with engine.connect() as connection:
            result = connection.execute(text(full_query_str), params).fetchall()
            return [dict(row._mapping) for row in result]
    except Exception as error:
        print(f"Database error in get_search_results: {error}")
        # Re-raising helps FastAPI show a proper server error during development
        raise error

def flexible_date_parser(date_string):
    if not date_string:
        return pd.NaT
    try:
        return pd.to_datetime(date_string, errors='coerce')
    except (ValueError, TypeError):
        return pd.NaT

# --- Main Dashboard Route ---
@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, user: dict = Depends(auth_utils.get_current_user)):
    # user = await auth_utils.get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    total_logs, normal_count, anomaly_count = 0, 0, 0
    try:
        engine = create_engine(settings.DATABASE_URL)
        query = "SELECT final_label FROM logs WHERE is_reviewed = 1"
        df = pd.read_sql_query(query, engine)
        # engine.close()
        if not df.empty:
            total_logs = len(df)
            normal_count = df[df['final_label'] == 0].shape[0]
            anomaly_count = df[df['final_label'] == 1].shape[0]
    except Exception as e:
        logger.error(f"Could not read from database to get stats: {e}")
    last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    response = templates.TemplateResponse(request, "dashboard.html", {
        # "request": request,
        "total_logs": total_logs,
        "normal_count": normal_count,
        "anomaly_count": anomaly_count,
        "last_updated": last_updated
    })
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response

@router.post("/api/search_logs", response_model=List[dict])
async def search_logs(query: SearchQuery, user: dict = Depends(auth_utils.get_current_user)):

    if not user:
        return RedirectResponse(url="/login")
    try:
        return await run_in_threadpool(get_search_results, query)
    except Exception as e:
        logger.error(f"Error during log search: {e}")
        return []

@router.get("/api/historical_trends")
async def get_historical_trends(response: Response, interval: str = "h", user: dict = Depends(auth_utils.get_current_user)):
    if not user:
        return RedirectResponse(url="/login")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    try:
        engine = create_engine(settings.DATABASE_URL)
        query = "SELECT timestamp FROM logs WHERE is_reviewed = 1 AND final_label = 1"
        df = pd.read_sql_query(query, engine)
        
        if df.empty:
            return []

        # Convert timestamp column using the robust helper function
        df['timestamp'] = df['timestamp'].apply(flexible_date_parser)
        df.dropna(subset=['timestamp'], inplace=True) # Remove rows where parsing failed

        if df.empty:
            return []
        
        # Make timestamps timezone-naive for resampling
        df['timestamp'] = df['timestamp'].dt.tz_localize(None)
        
        df.set_index('timestamp', inplace=True)
        anomaly_logs = df.resample(interval).size()
        
        trends_df = pd.DataFrame({'anomalies': anomaly_logs}).fillna(0)
        trends_df.reset_index(inplace=True)
        trends_df['timestamp'] = trends_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M')
        
        return trends_df.to_dict(orient='records')
        
    except Exception as e:
        logger.error(f"Error generating historical trends: {e}")
        return []

# --- Training Stats API Route ---
@router.get("/api/training_stats")
async def get_training_stats(user: dict = Depends(auth_utils.get_current_user)):
    if not user:
        return RedirectResponse(url="/login")
    
    # Check cache first
    cached_stats = cache.get_json("stats:training")
    if cached_stats:
        return cached_stats

    try:
        engine = create_engine(settings.DATABASE_URL)
        query = "SELECT final_label FROM logs WHERE is_reviewed = 1"
        df = pd.read_sql_query(query, engine)
        
        result = {"total": 0, "normal": 0, "anomaly": 0}
        if not df.empty:
            result = {
                "total": len(df),
                "normal": df[df['final_label'] == 0].shape[0],
                "anomaly": df[df['final_label'] == 1].shape[0],
            }
        
        # Cache for 5 minutes
        cache.set_json("stats:training", result, ttl=300)
        return result
        
    except Exception as e:
        logger.error(f"Error fetching training stats: {e}")
        return {"total": 0, "normal": 0, "anomaly": 0}

@router.get("/api/logs/context", response_model=List[Dict[str, Any]])
async def get_log_context(timestamp: str, user: dict = Depends(auth_utils.get_current_user)):
    if not user:
        return RedirectResponse(url="/login")

    def get_context_from_db():
        engine = create_engine(settings.DATABASE_URL)
        try:
            center_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            start_time = center_time - timedelta(seconds=10)
            end_time = center_time + timedelta(seconds=10)
            
            query = text("SELECT * FROM logs WHERE timestamp BETWEEN :start AND :end ORDER BY timestamp ASC")
            
            with engine.connect() as connection:
                result = connection.execute(query, {"start": start_time, "end": end_time}).fetchall()
                return [dict(row._mapping) for row in result]
        except Exception as e:
            logger.error(f"Error fetching log context: {e}")
            return []

    return await run_in_threadpool(get_context_from_db)

@router.post("/api/model/retrain")
async def retrain_model(background_tasks: BackgroundTasks, user: dict = Depends(auth_utils.get_current_user)):
    if not user:
        return RedirectResponse(url="/login")
    if task_status["retrain"]["status"] == "running":
        return {"message": "Retraining is already in progress."}
    
    logger.info("Received request to retrain model. Starting as a background task.")
    task_status["retrain"] = {"status": "running", "message": "Retraining in progress..."}
    
    background_tasks.add_task(run_update_and_set_status)
    
    return {"message": "Model retraining has been initiated."}

@router.get("/api/model/retrain/status")
async def get_retrain_status():
    return task_status["retrain"]

@router.get("/api/alerts")
async def get_alerts(user: dict = Depends(auth_utils.get_current_user)):
    """Fetches all open alerts (status is 'New' or 'Acknowledged') from PostgreSQL."""
    if not user:
        return RedirectResponse(url="/login")
        
    def get_alerts_from_db():
        # 1. Connect using the DATABASE_URL
        engine = create_engine(settings.DATABASE_URL)
        # 2. Create a cursor that returns dictionary-like rows
        # cursor = engine.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        query = """
            SELECT a.id, a.status, a.rule_name, a.rule_description, a.mitre_tactic, a.mitre_technique, l.timestamp, l.content, l.risk_score, l.threat_intel, l.id as log_id
            FROM alerts a JOIN logs l ON a.log_id = l.id
            WHERE a.status IN ('New', 'Acknowledged')
            ORDER BY l.timestamp DESC LIMIT 100
        """     
        try:
            with engine.connect() as connection:
                result = connection.execute(text(query))
                # The new way to convert rows to dictionaries
                alerts = [dict(row._mapping) for row in result]
                return alerts
        except Exception as e:
            print(f"Database error in get_alerts: {e}")
            return []
                
    return await run_in_threadpool(get_alerts_from_db)

@router.post("/api/alerts/{alert_id}/status")
async def update_alert_status(alert_id: int, update: AlertStatusUpdate, user: dict = Depends(auth_utils.get_current_user)):
    """Updates an alert's status and broadcasts the change using PostgreSQL."""
    if not user:
        return RedirectResponse(url="/login")
    
    VALID_STATUSES = {"New", "Acknowledged", "Closed", "Resolved"}
    if update.status not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail="Invalid status provided.")

    def update_and_get_log_id():
        engine = create_engine(settings.DATABASE_URL)
        query = text("UPDATE alerts SET status = :status WHERE id = :alert_id RETURNING log_id")
        try:
            with engine.connect() as connection:
                with connection.begin() as transaction:
                    result = connection.execute(query, {"status": update.status, "alert_id": alert_id}).scalar_one_or_none()
                    return result
        except Exception as error:
            print(f"Database error in update_alert_status: {error}")
            return None

    log_id = await run_in_threadpool(update_and_get_log_id)
    
    if log_id is not None:
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
    else:
        return {"message": "Failed to update alert status or find log ID"}

@router.get("/api/anomalies/all")
async def get_all_anomalies(user: dict = Depends(auth_utils.get_current_user)):
    """Fetches ALL open anomalies, regardless of risk score."""
    if not user:
        return RedirectResponse(url="/login")
        
    def get_anomalies_from_db():
        engine = create_engine(settings.DATABASE_URL)
        query = text("""
            SELECT a.id, a.status, a.rule_name, a.rule_description, a.mitre_tactic, a.mitre_technique, l.timestamp, l.content, l.risk_score, l.threat_intel, l.id as log_id
            FROM alerts a JOIN logs l ON a.log_id = l.id
            WHERE a.status IN ('New', 'Acknowledged') AND l.risk_score >= 0.79
            ORDER BY l.timestamp DESC LIMIT 100
        """)
        try:
            with engine.connect() as connection:
                result = connection.execute(query).fetchall()
                return [dict(row._mapping) for row in result]
        except Exception as error:
            print(f"Database error in get_all_anomalies: {error}")
            return []
                
    return await run_in_threadpool(get_anomalies_from_db)

@router.get("/api/logs/{log_id}/explain")
async def get_explanation(log_id: int, user: dict = Depends(auth_utils.get_current_user)):

    if not user:
        return RedirectResponse(url="/login")

    def get_explanation_from_db():
        # 1. Check Redis Cache
        cache_key = f"lime:v1:{log_id}"
        cached_html = cache.get_json(cache_key)
        if cached_html:
            return {"explanation_html": cached_html}

        engine = create_engine(settings.DATABASE_URL)
        line = None
        
        # 2. Check Database (Column: explanation)
        try:
            with engine.connect() as connection:
                result = connection.execute(text("SELECT content, explanation FROM logs WHERE id = :log_id"), {"log_id": log_id}).fetchone()
                if not result:
                    raise HTTPException(status_code=404, detail="Log not found")
                
                row_dict = dict(result._mapping)
                line = row_dict['content']
                if row_dict.get('explanation'):
                    # Found in DB! Cache it and return.
                    cache.set_json(cache_key, row_dict['explanation'], ttl=86400) # 24h cache from DB
                    return {"explanation_html": row_dict['explanation']}
        
            logger.info(f"Generating LIME explanation for log ID: {log_id}")
            embedder, supervised_model, explainer = get_models()

            # Step 3: Generate the explanation on the fly
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
        except Exception as e:
            logger.error(f"Error generating LIME explanation for log ID {log_id}: {e}")
            traceback.print_exc()
            return {"error": f"Could not generate explanation: {e}"}

        # Step 4: Save to DB and Cache
        if html:
            try:
                # Save to Redis
                cache.set_json(cache_key, html, ttl=86400 * 7) # 7 days
                
                # Save to DB
                with engine.connect() as connection:
                    with connection.begin() as transaction:
                        connection.execute(text("UPDATE logs SET explanation = :html WHERE id = :log_id"), {"html": html, "log_id": log_id})
                logger.info(f"Saved new explanation for log ID: {log_id}")

            except Exception as e:
                logger.error(f"Error saving LIME explanation for log ID {log_id}: {e}")

            return {"explanation_html": html}
        else:
            return {"explanation_html": "<p class='explanation-error'>Explanation not available for this log.</p>"}

    return await run_in_threadpool(get_explanation_from_db)

@router.get("/api/monitoring/status")
async def get_monitoring_status(user: dict = Depends(auth_utils.get_current_user)):
    """Gets the current monitoring status (active or paused)."""
    if not user:
        return RedirectResponse(url="/login")
    if not settings.STATUS_FILE.exists():
        return {"is_active": True} # Default to active if file doesn't exist
    with open(settings.STATUS_FILE, 'r') as f:
        return json.load(f)

@router.post("/api/monitoring/toggle")
async def toggle_monitoring_status(request: Request, user: dict = Depends(auth_utils.get_current_user)):
    """Toggles the monitoring status between active and paused."""
    if not user:
        return RedirectResponse(url="/login")
    body = await request.json()
    new_status = body.get("is_active")
    with open(settings.STATUS_FILE, 'w') as f:
        json.dump({"is_active": new_status}, f)
    
    # Broadcast the status change to all connected clients
    await broadcast({"type": "monitoring_status_update", "data": {"is_active": new_status}})
    
    return {"status": "ok", "is_active": new_status}

@router.get("/api/stats/top_n")
async def get_top_n_stats(field: str = "verdict", limit: int = 5, user: dict = Depends(auth_utils.get_current_user)):
    """
    Gets the top N most frequent values for a given field from anomalous logs.
    Valid fields: 'verdict', 'ip', 'source'.
    """
    if not user:
        return RedirectResponse(url="/login")
    def get_data():
        # Check cache (include field and limit in key)
        cache_key = f"stats:top_n:{field}:{limit}"
        cached_val = cache.get_json(cache_key)
        if cached_val:
            return cached_val

        engine = create_engine(settings.DATABASE_URL)
        
        # Whitelist of allowed fields to query
        if field not in ["verdict", "ip", "source"]:
            # engine.close()
            return {"error": "Invalid field specified."}

        query = f"SELECT content, verdict, source FROM logs WHERE final_label = 1"
        df = pd.read_sql_query(query, engine)

        if df.empty:
            cache.set_json(cache_key, [], ttl=300)
            return []
        
        # For IPs, we need to extract them from the content
        target_column = field
        if field == 'ip':
            df['ip'] = df['content'].apply(extract_ip_from_string)

        if target_column not in df.columns:
            return []
        
        df.dropna(subset=[target_column], inplace=True)
        
        if df.empty:
            cache.set_json(cache_key, [], ttl=300)
            return []

        valid_items = [item for item in df[target_column] if pd.notna(item)]
        counts = Counter(valid_items).most_common(limit)
        
        # Format for Chart.js
        result = [{"item": item, "count": count} for item, count in counts]
        cache.set_json(cache_key, result, ttl=300)
        return result
        
    return await run_in_threadpool(get_data)

@router.get("/api/stats/detection_methods")
async def get_detection_method_stats(user: dict = Depends(auth_utils.get_current_user)):

    if not user:
        return RedirectResponse(url="/login")

    def get_data_from_db():
        engine = create_engine(settings.DATABASE_URL)
        # We only care about logs that were flagged as anomalies
        query = "SELECT verdict FROM logs WHERE final_label = 1"
        
        try:
            with engine.connect() as connection:
                df = pd.read_sql_query(query, connection)
        except Exception as e:
            logger.error(f"Database error in get_detection_method_stats: {e}")
            return {}

        if df.empty:
            return {}

        # Standardize the verdicts to count them
        def categorize_verdict(v):
            if not isinstance(v, str):
                return 'Other'
            v_lower = v.lower()
            if 'supervised' in v_lower:
                return 'Supervised'
            if 'novelty' in v_lower:
                return 'Unsupervised'
            if 'sequence' in v_lower:
                return 'Sequential (LSTM)'
            return 'Other'

        df['method'] = df['verdict'].apply(categorize_verdict)
        
        # Count the occurrences of each category and convert to a dictionary
        counts = df['method'].value_counts().to_dict()
        return counts

    return await run_in_threadpool(get_data_from_db)


@router.get("/api/stats/overview")
async def get_stats_overview(user: dict = Depends(auth_utils.get_current_user)):
    """
    Returns overview statistics for the Session Activity widget and Historical summary.
    - unique_ips_24h: Count of unique IPs in the last 24 hours
    - avg_risk_score: Average risk score of anomalies
    - today_anomalies: Count of anomalies today
    - peak_hour: Hour with most anomalies today
    - seven_day_trend: Trend compared to last 7 days
    """
    def get_overview_data():
        with psycopg2.connect(settings.DATABASE_URL) as conn:
            with conn.cursor() as cur:
                # Unique IPs in last 24 hours
                cur.execute("""
                    SELECT COUNT(DISTINCT 
                        CASE 
                            WHEN content ~ '\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}'
                            THEN (regexp_match(content, '(\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3})'))[1]
                            ELSE NULL
                        END
                    ) FROM logs 
                    WHERE timestamp >= NOW() - INTERVAL '24 hours'
                """)
                unique_ips = cur.fetchone()[0] or 0

                # Average risk score of anomalies
                cur.execute("""
                    SELECT AVG(risk_score) FROM logs 
                    WHERE final_label = 1 AND risk_score IS NOT NULL
                """)
                avg_risk = cur.fetchone()[0] or 0

                # Today's anomalies
                cur.execute("""
                    SELECT COUNT(*) FROM logs 
                    WHERE final_label = 1 
                    AND DATE(timestamp) = CURRENT_DATE
                """)
                today_anomalies = cur.fetchone()[0] or 0

                # Peak hour today
                cur.execute("""
                    SELECT EXTRACT(HOUR FROM timestamp) as hour, COUNT(*) as cnt
                    FROM logs 
                    WHERE final_label = 1 AND DATE(timestamp) = CURRENT_DATE
                    GROUP BY hour 
                    ORDER BY cnt DESC 
                    LIMIT 1
                """)
                peak_result = cur.fetchone()
                peak_hour = f"{int(peak_result[0]):02d}:00" if peak_result else "--"

                # 7-day trend (compare today vs avg of last 7 days)
                cur.execute("""
                    SELECT AVG(daily_count) FROM (
                        SELECT DATE(timestamp) as day, COUNT(*) as daily_count
                        FROM logs 
                        WHERE final_label = 1 
                        AND timestamp >= NOW() - INTERVAL '7 days'
                        AND DATE(timestamp) < CURRENT_DATE
                        GROUP BY day
                    ) subq
                """)
                avg_7d = cur.fetchone()[0] or 0
                
                if avg_7d > 0:
                    trend_pct = ((today_anomalies - avg_7d) / avg_7d) * 100
                    if trend_pct > 0:
                        seven_day_trend = f"+{trend_pct:.0f}%"
                    else:
                        seven_day_trend = f"{trend_pct:.0f}%"
                else:
                    seven_day_trend = "N/A"

                return {
                    "unique_ips_24h": unique_ips,
                    "avg_risk_score": float(avg_risk) if avg_risk else 0,
                    "today_anomalies": today_anomalies,
                    "peak_hour": peak_hour,
                    "seven_day_trend": seven_day_trend
                }

    return await run_in_threadpool(get_overview_data)


@router.get("/api/stats/alert_breakdown")
async def get_alert_breakdown(user: dict = Depends(auth_utils.get_current_user)):
    """
    Returns alert counts by status for the Alert Breakdown widget.
    """
    def get_breakdown_data():
        with psycopg2.connect(settings.DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT status, COUNT(*) as cnt
                    FROM alerts
                    GROUP BY status
                """)
                rows = cur.fetchall()
                
                result = {"new": 0, "acknowledged": 0, "closed": 0}
                for row in rows:
                    status = row[0].lower() if row[0] else "new"
                    if status in result:
                        result[status] = row[1]
                
                return result

    return await run_in_threadpool(get_breakdown_data)


@router.get("/api/stats/model_drift")
async def get_model_drift_stats(user: dict = Depends(auth_utils.get_current_user)):
    """Fetches historical model metrics for drift visualization."""
    if not user:
        return RedirectResponse(url="/login")
    
    def get_data():
        engine = create_engine(settings.DATABASE_URL)
        query = text("""
            SELECT timestamp, accuracy, precision, recall, f1_score 
            FROM model_metrics 
            WHERE model_type = 'supervised_sgd' 
            ORDER BY timestamp ASC LIMIT 50
        """)
        try:
            with engine.connect() as connection:
                result = connection.execute(query).fetchall()
                data = []
                for row in result:
                    item = dict(row._mapping)
                    # Convert timestamp to string
                    item['timestamp'] = item['timestamp'].strftime('%Y-%m-%d %H:%M')
                    data.append(item)
                return data
        except Exception as e:
            logger.error(f"Error fetching drift stats: {e}")
            return []

    return await run_in_threadpool(get_data)

@router.get("/api/stats/anomalous_ips_locations")
async def get_anomalous_ips_locations(user: dict = Depends(auth_utils.get_current_user)):
    """
    Finds recent anomalous IPs, geolocates them, and returns their coordinates.
    """
    if not user:
        return RedirectResponse(url="/login")
    if not geoip_reader:
        raise HTTPException(status_code=500, detail="GeoIP database is not configured.")

    def get_locations_from_db():
        engine = create_engine(settings.DATABASE_URL)
        # Get logs from the last 24 hours that were anomalies
        query = """
            SELECT content FROM logs 
            WHERE final_label = 1 AND timestamp >= NOW() - INTERVAL '24 hours'
        """
        try:
            with engine.connect() as connection:
                df = pd.read_sql_query(query, connection)
        except Exception as e:
            logger.error(f"DB error in get_anomalous_ips_locations: {e}")
            return []

        if df.empty:
            return []

        locations = []
        seen_ips = set()
        
        for log_content in df['content']:
            ip = extract_ip_from_string(log_content)
            if ip and ip not in seen_ips:
                seen_ips.add(ip)
                
                # Check Cache for IP Location
                geo_cache_key = f"geo:{ip}"
                cached_geo = cache.get_json(geo_cache_key)
                if cached_geo:
                    locations.append(cached_geo)
                    continue

                try:
                    response = geoip_reader.city(ip)
                    if response and response.location and response.location.latitude and response.location.longitude:
                        geo_data = {
                            "ip": ip,
                            "lat": response.location.latitude,
                            "lon": response.location.longitude,
                            "city": response.city.name if response.city else "Unknown City",
                            "country": response.country.name if response.country else "Unknown Country"
                        }
                        locations.append(geo_data)
                        cache.set_json(geo_cache_key, geo_data, ttl=86400) # Cache for 24 hours
                except geoip2.errors.AddressNotFoundError:
                    # This happens for private IPs (e.g., 192.168.x.x), which is normal.
                    # We can optionally cache the "not found" state to avoid re-querying private IPs
                    cache.set_json(geo_cache_key, None, ttl=86400)
                    pass
                except Exception as e:
                    logger.warning(f"Could not geolocate IP {ip}: {e}")
        return locations

    return await run_in_threadpool(get_locations_from_db)

@router.post("/api/export/pdf")
async def export_pdf_report(query: SearchQuery, user: dict = Depends(auth_utils.get_current_user)):
    """
    Generates a comprehensive PDF report including charts, a map, and search results.
    """
    if not user:
        return RedirectResponse(url="/login")

    # --- PART 1: Generate PDF with Text and Tables ---
    logs = await run_in_threadpool(get_search_results, query)
    text_buffer = io.BytesIO()
    doc_text = SimpleDocTemplate(text_buffer, pagesize=landscape(letter))
    styles = getSampleStyleSheet()
    story_text = []

    story_text.append(Paragraph("Log Anomaly Dashboard Report", styles['h1']))
    story_text.append(Spacer(1, 12))
    story_text.append(Paragraph(f"Report generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    story_text.append(Spacer(1, 24))

    # Add log search results table (same as before)
    if logs:
        header = ["Timestamp", "Source", "Label", "Risk", "Content"]
        data = [header]
        
        for log in logs:
            content = str(log.get('content', 'N/A'))
            if len(content) > 100:
                content = content[:100] + "..."
            data.append([
                str(log.get('timestamp', 'N/A')),
                str(log.get('source', 'N/A')),
                "Anomaly" if log.get('final_label') == 1 else "Normal",
                f"{log.get('risk_score', 0.0):.2f}",
                content
            ])
        table = Table(data, colWidths=[120, 80, 60, 40, 450])
        style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4a4a8a')), # Header color
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#e0e0f0')),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ])
        table.setStyle(style) # Make sure you have your style defined
        story_text.append(table)
    
    doc_text.build(story_text)
    text_buffer.seek(0)

    # --- PART 2: Generate PDF with Visual Widgets and Map ---
    visual_buffer = io.BytesIO()
    doc_visuals = SimpleDocTemplate(visual_buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story_visuals = []

    story_visuals.append(Paragraph("Dashboard Visuals", styles['h1']))
    story_visuals.append(Spacer(1, 24))

    # Add chart images received from the frontend
    if query.chart_images:
        for title, base64_image in query.chart_images.items():
            story_visuals.append(Paragraph(title, styles['h2']))
            # Decode the base64 string and add the image
            img_data = base64.b64decode(base64_image.split(',')[1])
            story_visuals.append(Image(io.BytesIO(img_data), width=450, height=225))
            story_visuals.append(Spacer(1, 12))

    doc_visuals.build(story_visuals)
    visual_buffer.seek(0)
    
    # --- PART 3: Merge the two PDFs ---
    merger = PdfWriter()
    if visual_buffer.getbuffer().nbytes > 0:
        merger.append(fileobj=visual_buffer)
    if text_buffer.getbuffer().nbytes > 0:
        merger.append(fileobj=text_buffer)

    final_buffer = io.BytesIO()
    merger.write(final_buffer)
    merger.close()
    final_buffer.seek(0)

    return StreamingResponse(
        final_buffer,
        media_type='application/pdf',
        headers={'Content-Disposition': 'attachment; filename="dashboard_report.pdf"'}
    )

@router.get("/playbooks", response_class=HTMLResponse)
async def playbooks_page(request: Request, user: dict = Depends(auth_utils.get_current_user)):
    """Serves the Playbooks management page."""
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(request, "playbooks.html")

@router.get("/review", response_class=HTMLResponse)
async def review_page(request: Request, user: dict = Depends(auth_utils.get_current_user)):
    """Serves the dedicated log review page."""
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(request, "review.html")
