# app/routes.py (Final Fixes for Timezones and Paths)
# from app.config import settings
# from fastapi import APIRouter, Request, Response, BackgroundTasks
# from fastapi.templating import Jinja2Templates
# from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
# from fastapi.exceptions import HTTPException
# from fastapi.concurrency import run_in_threadpool
# from sentence_transformers import SentenceTransformer
# from scripts.review_manager import prepare_review_session
# from app.websocket import broadcast
# from datetime import datetime, timezone, timedelta
# from scripts.update import trigger_model_update
# from fastapi import Depends, Form, status
# from fastapi.security import OAuth2PasswordRequestForm
# from jose import jwt, JWTError
# from . import auth
# import sqlite3
# import pandas as pd
# from pydantic import BaseModel
# from typing import Optional, List, Dict, Any
# from pathlib import Path
# import dill
# from sklearn.pipeline import make_pipeline
# import joblib
# import traceback
# import io
# import qrcode
# import json
# import base64
# import re
# from collections import Counter

# --- DYNAMIC PATH CONFIGURATION ---
# current_dir = Path(__file__).parent
# project_root = current_dir.parent
# DATABASE_FILE = project_root / "log_database.db"
# TEMPLATES_PATH = current_dir / "templates"
# EMBEDDER_PATH = project_root / "model/sentence_embedder.pkl"
# SUPERVISED_MODEL_PATH = project_root / "model/sgd_embedder.pkl"
# EXPLAINER_PATH = project_root / "model/lime_explainer.pkl"
# STATUS_FILE = project_root / "monitoring_status.json"

# embedder = SentenceTransformer(str(settings.EMBEDDER_PATH))
# supervised_model = joblib.load(settings.SUPERVISED_MODEL_PATH)
# with open(settings.EXPLAINER_PATH, 'rb') as f:
#     explainer = dill.load(f)

# --- Logging Helpers ---
# def log_info(msg): print(f"\033[94mℹ️ {msg}\033[0m")
# def log_error(msg): print(f"\033[91m❗ {msg}\033[0m")


# router = APIRouter()
# templates = Jinja2Templates(directory=settings.TEMPLATES_PATH)

# --- Pydantic Models ---
# class SearchQuery(BaseModel):
#     keyword: Optional[str] = None
#     start_time: Optional[str] = None
#     end_time: Optional[str] = None
#     label: Optional[int] = None
#     source: Optional[str] = None

# class ReviewUpdateItem(BaseModel):
#     id: int
#     new_label: int

# class AlertStatusUpdate(BaseModel):
#     status: str

# def flexible_date_parser(date_string):
#     try:
#         # errors='raise' will trigger the 'except' block if it fails.
#         return pd.to_datetime(date_string, errors='raise')
#     except (ValueError, TypeError):
#         # If the standard parser fails, try our custom format.
#         try:
#             # This is the format for 'Jul 19, 2025 10:42:57'
#             return datetime.strptime(str(date_string), '%b %d, %Y %H:%M:%S')
#         except (ValueError, TypeError):
#             # If all attempts fail, return NaT (Not a Time) so it can be dropped.
#             return pd.NaT

# class BulkLabelUpdate(BaseModel):
#     new_label: int

# class ManualLogsQuery(BaseModel):
#     sort_by: str = "timestamp"
#     sort_order: str = "desc"

# task_status = {
#     "retrain": {"status": "idle", "message": "No active task."}
# }

# def run_update_and_set_status():
#     try:
#         trigger_model_update()
#         task_status["retrain"] = {"status": "completed", "message": "Model retraining completed successfully."}
#     except Exception as e:
#         log_error(f"Model retraining failed: {e}")
#         task_status["retrain"] = {"status": "failed", "message": f"Error during retraining: {e}"}

# def generate_simple_explanation_html(explanation_list: list) -> str:
#     """Takes a LIME explanation list and returns a simple, clean HTML snippet."""
#     if not explanation_list:
#         return "<p class='explanation-error'>LIME was unable to find significant features for this log.</p>"

#     # Filter for only the words that POSITIVELY contribute to the anomaly score
#     positive_contributors = [item for item in explanation_list if item[1] > 0]
#     positive_contributors.sort(key=lambda x: x[1], reverse=True)

#     if not positive_contributors:
#         return "<p class='explanation-error'>LIME found no features that point towards an anomaly.</p>"

#     html = "<div><p>The model flagged this log as an anomaly primarily because of these words:</p>"
#     html += '<div class="explanation-words">'
#     for word, score in positive_contributors:
#         # Use opacity to show the "weight" or importance of the word
#         opacity = max(0.2, min(1.0, score * 5))
#         html += f'<span style="background-color: rgba(220, 53, 69, {opacity}); padding: 2px 5px; border-radius: 4px; margin: 2px; display: inline-block; color: white;">{word}</span>'
#     html += "</div></div>"
#     return html

# def extract_ip_from_string(log_line: str):
#     match = re.search(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", log_line)
#     return match.group(0) if match else None

# # --- Main Dashboard Route ---
# @router.get("/", response_class=HTMLResponse)
# async def dashboard(request: Request):
#     user = await auth.get_current_user(request)
#     if not user:
#         return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

#     total_logs, normal_count, anomaly_count = 0, 0, 0
#     try:
#         conn = sqlite3.connect(settings.DATABASE_FILE)
#         query = "SELECT final_label FROM logs WHERE is_reviewed = 1"
#         df = pd.read_sql_query(query, conn)
#         conn.close()
#         if not df.empty:
#             total_logs = len(df)
#             normal_count = df[df['final_label'] == 0].shape[0]
#             anomaly_count = df[df['final_label'] == 1].shape[0]
#     except Exception as e:
#         log_error(f"Could not read from database to get stats: {e}")
#     last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#     response = templates.TemplateResponse("dashboard.html", {
#         "request": request,
#         "total_logs": total_logs,
#         "normal_count": normal_count,
#         "anomaly_count": anomaly_count,
#         "last_updated": last_updated
#     })
#     response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
#     response.headers["Pragma"] = "no-cache"
#     response.headers["Expires"] = "0"
#     return response

# @router.post("/api/search_logs", response_model=List[dict])
# async def search_logs(query: SearchQuery):
#     def get_search_results():
#         conn = sqlite3.connect(settings.DATABASE_FILE)
#         conn.row_factory = sqlite3.Row
#         # THE FIX: Use a LEFT JOIN to get the alert status if it exists
#         sql_query = """
#             SELECT l.id, l.timestamp, l.source, l.content, l.final_label, l.risk_score, l.sequence_risk, a.status
#             FROM logs l
#             LEFT JOIN alerts a ON l.id = a.log_id
#             WHERE 1=1
#         """
#         params = []
        
#         # ... (The rest of the query building with params is the same as before)
#         if query.keyword:
#             sql_query += " AND l.content LIKE ?"
#             params.append(f"%{query.keyword}%")
#         if query.start_time:
#             sql_query += " AND l.timestamp >= ?"
#             params.append(query.start_time)
#         if query.end_time:
#             sql_query += " AND l.timestamp <= ?"
#             params.append(query.end_time)
#         if query.label is not None:
#             sql_query += " AND l.final_label = ?"
#             params.append(query.label)
#         if query.source:
#             sql_query += " AND l.source LIKE ?"
#             params.append(f"%{query.source}%")

#         sql_query += " ORDER BY l.timestamp DESC LIMIT 500;"
        
#         results = [dict(row) for row in conn.execute(sql_query, params).fetchall()]
#         conn.close()
#         return results

#     try:
#         return await run_in_threadpool(get_search_results)
#     except Exception as e:
#         log_error(f"Error during log search: {e}")
#         return []

# # --- Historical Trends API Route (with Timezone and Cache-Busting Fix) ---

# @router.get("/api/historical-trends")
# async def get_historical_trends(response: Response, interval: str = 'h'):
#     response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
#     response.headers["Pragma"] = "no-cache"
#     response.headers["Expires"] = "0"
#     try:
#         conn = sqlite3.connect(settings.DATABASE_FILE)
#         query = "SELECT timestamp FROM logs WHERE is_reviewed = 1 AND final_label = 1"
#         df = pd.read_sql_query(query, conn)
#         conn.close()
        
#         if df.empty:
#             return []

#         # === THE FIX: Apply our new flexible parser to the timestamp column ===
#         df['timestamp'] = df['timestamp'].apply(flexible_date_parser)
#         # === END FIX ===

#         if df.empty:
#             return []
        
#         df['timestamp'] = df['timestamp'].dt.tz_localize(None)
        
#         df.set_index('timestamp', inplace=True)
#         anomaly_logs = df.resample(interval).size()
        
#         trends_df = pd.DataFrame({'anomalies': anomaly_logs}).fillna(0)
#         trends_df.reset_index(inplace=True)
#         trends_df['timestamp'] = trends_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M')
        
#         return trends_df.to_dict(orient='records')
        
#     except Exception as e:
#         log_error(f"Error generating historical trends: {e}")
#         return []

# # --- Training Stats API Route ---
# @router.get("/api/training_stats")
# async def get_training_stats():
#     try:
#         conn = sqlite3.connect(settings.DATABASE_FILE)
#         query = "SELECT final_label FROM logs WHERE is_reviewed = 1"
#         df = pd.read_sql_query(query, conn)
#         conn.close()
#         if df.empty:
#             return {"total": 0, "normal": 0, "anomaly": 0}
#         return {
#             "total": len(df),
#             "normal": df[df['final_label'] == 0].shape[0],
#             "anomaly": df[df['final_label'] == 1].shape[0],
#         }
#     except Exception as e:
#         log_error(f"Error fetching training stats: {e}")
#         return {"total": 0, "normal": 0, "anomaly": 0}


# @router.get("/api/review/pending", response_model=List[Dict[str, Any]])
# async def get_pending_logs_api(sort_by: Optional[str] = None):
#     """
#     API endpoint to get pending logs as JSON data.
#     """
#     def get_logs_from_db():
#         conn = sqlite3.connect(settings.DATABASE_FILE)
#         conn.row_factory = sqlite3.Row
#         # query = "SELECT id, timestamp, source, content, predicted_label, final_label, risk_score FROM logs WHERE is_reviewed = 0"
        
#         query = """
#             SELECT l.*, a.status
#             FROM logs l
#             LEFT JOIN alerts a ON l.id = a.log_id
#             WHERE l.is_reviewed = 0
#         """
#         if sort_by == '1':
#             query += " ORDER BY predicted_label DESC, timestamp DESC"
#         elif sort_by == '0':
#             query += " ORDER BY predicted_label ASC, timestamp DESC"
#         else:
#             query += " ORDER BY timestamp DESC " # Limit to 200 to keep it fast
        
#         entries = [dict(row) for row in conn.execute(query).fetchall()]
#         conn.close()
#         return entries

#     return await run_in_threadpool(get_logs_from_db)


# # This API endpoint receives the corrections from the review interface.
# @router.post("/api/review/update")
# async def update_reviews_api(updates: List[ReviewUpdateItem]):
#     """
#     API endpoint to receive and process reviewed logs.
#     """
#     def update_database():
#         conn = sqlite3.connect(settings.DATABASE_FILE)
#         for item in updates:
#             conn.execute(
#                 "UPDATE logs SET final_label = ?, is_reviewed = 1 WHERE id = ?",
#                 (item.new_label, item.id)
#             )
#         conn.commit()
#         conn.close()
#         return {"status": "ok", "updated_count": len(updates)}

#     return await run_in_threadpool(update_database)


# @router.get("/api/logs/context", response_model=List[Dict[str, Any]])
# async def get_log_context(timestamp: str):

#     def get_context_from_db():
#         try:
#             # Step 1: Parse the incoming UTC timestamp string from the browser
#             center_time_utc = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            
#             # Step 2: Convert the UTC time to the server's local timezone (e.g., IST)
#             center_time_local_aware = center_time_utc.astimezone()
            
#             # Step 3: Make it timezone-naive to match the strings stored in the database
#             center_time_local_naive = center_time_local_aware.replace(tzinfo=None)

#             # Step 4: Define the time window using the corrected local time
#             start_time = center_time_local_naive - timedelta(seconds=10)
#             end_time = center_time_local_naive + timedelta(seconds=10)

#             conn = sqlite3.connect(settings.DATABASE_FILE)
#             conn.row_factory = sqlite3.Row
            
#             # Query for all logs within the time window, sorted chronologically
#             query = "SELECT * FROM logs WHERE timestamp BETWEEN ? AND ? ORDER BY timestamp ASC"
#             params = (start_time.isoformat(), end_time.isoformat())
            
#             # Convert the database rows to a list of dictionaries
#             entries = [dict(row) for row in conn.execute(query, params).fetchall()]
#             conn.close()
#             return entries
#         except Exception as e:
#             log_error(f"Error fetching log context: {e}")
#             return []

#     return await run_in_threadpool(get_context_from_db)

# @router.post("/api/model/retrain")
# async def retrain_model(background_tasks: BackgroundTasks):

#     if task_status["retrain"]["status"] == "running":
#         return {"message": "Retraining is already in progress."}
    
#     log_info("Received request to retrain model. Starting as a background task.")
#     task_status["retrain"] = {"status": "running", "message": "Retraining in progress..."}
    
#     background_tasks.add_task(run_update_and_set_status)
    
#     return {"message": "Model retraining has been initiated."}

# @router.get("/api/model/retrain/status")
# async def get_retrain_status():

#     return task_status["retrain"]

# @router.get("/api/alerts")
# async def get_alerts():
#     """Fetches all open alerts (status is 'New' or 'Acknowledged')."""
#     def get_alerts_from_db():
#         conn = sqlite3.connect(settings.DATABASE_FILE, timeout=10)
#         conn.row_factory = sqlite3.Row
#         query = """
#             SELECT a.id, a.status, a.rule_name, l.timestamp, l.content, l.risk_score
#             FROM alerts a JOIN logs l ON a.log_id = l.id
#             WHERE a.status IN ('New', 'Acknowledged')
#             ORDER BY l.timestamp DESC LIMIT 100
#         """
#         alerts = [dict(row) for row in conn.execute(query).fetchall()]
#         conn.close()
#         return alerts
#     return await run_in_threadpool(get_alerts_from_db)

# @router.post("/api/alerts/{alert_id}/status")
# async def update_alert_status(alert_id: int, update: AlertStatusUpdate):
#     """Updates an alert's status and broadcasts the change."""
    
#     def update_and_get_log_id():
#         conn = sqlite3.connect(settings.DATABASE_FILE, timeout=10)
#         # First, update the status
#         conn.execute("UPDATE alerts SET status = ? WHERE id = ?", (update.status, alert_id))
#         conn.commit()
#         # Now, get the associated log_id to broadcast it
#         log_id = conn.execute("SELECT log_id FROM alerts WHERE id = ?", (alert_id,)).fetchone()
#         conn.close()
#         return log_id[0] if log_id else None

#     log_id = await run_in_threadpool(update_and_get_log_id)
    
#     # After updating the database, broadcast the change to all clients
#     await broadcast({
#         "type": "alert_status_update",
#         "data": {
#             "alert_id": alert_id,
#             "log_id": log_id,
#             "new_status": update.status
#         }
#     })
    
#     return {"message": "Alert status updated successfully"}

# @router.get("/api/anomalies/all")
# async def get_all_anomalies():
#     """Fetches ALL open anomalies, regardless of risk score."""
#     def get_anomalies_from_db():
#         conn = sqlite3.connect(settings.DATABASE_FILE, timeout=10)
#         conn.row_factory = sqlite3.Row
#         # This query is the same but WITH the risk score filter
#         query = """
#             SELECT a.id, a.status, a.rule_name, l.timestamp, l.content, l.risk_score
#             FROM alerts a JOIN logs l ON a.log_id = l.id
#             WHERE a.status IN ('New', 'Acknowledged')
#             AND l.risk_score >= 0.78
#             ORDER BY l.timestamp DESC LIMIT 100
#         """
#         anomalies = [dict(row) for row in conn.execute(query).fetchall()]
#         conn.close()
#         return anomalies
#     return await run_in_threadpool(get_anomalies_from_db)

# @router.get("/api/logs/{log_id}/explain")
# async def get_explanation(log_id: int):

#     def generate_lime_explanation():
#         conn = sqlite3.connect(settings.DATABASE_FILE, timeout=10)
        
#         try:
#             log_content = conn.execute("SELECT content FROM logs WHERE id = ?", (log_id,)).fetchone()

#             if not log_content:
#                 return {"error": "Log not found"}

#             line = log_content[0]
        
        
#             log_info(f"Generating LIME explanation for log ID: {log_id}")
#             def predictor_fn(text_list):
#                 embeddings = embedder.encode(text_list)
#                 return supervised_model.predict_proba(embeddings)

#             exp = explainer.explain_instance(
#                 line, 
#                 predictor_fn, 
#                 num_features=6, 
#                 labels=[1]
#             )
#             explanation_list = exp.as_list(label=1)
#             html = generate_simple_explanation_html(explanation_list)

#             if html:
#                 conn.execute("UPDATE logs SET explanation = ? WHERE id = ?", (html, log_id))
#                 conn.commit()
#                 # log_info(f"Saved new explanation for log ID: {log_id}")

#             return {"explanation_html": html}
        
#         except Exception as e:
#             log_error(f"Error generating LIME explanation for log ID {log_id}: {e}")
#             traceback.print_exc()
#             return {"error": f"Could not generate explanation: {e}"}
#         finally:
#             if conn:
#                 conn.close()
#                 log_info(f"Database connection closed for log ID: {log_id}.")

#     return await run_in_threadpool(generate_lime_explanation)

# @router.get("/login", response_class=HTMLResponse)
# async def login_page(request: Request):
#     user = await auth.get_current_user(request)
#     if user:
#         return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
#     # return templates.TemplateResponse("login.html", {"request": request})
#     response = templates.TemplateResponse("login.html", {"request": request})
#     response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
#     response.headers["Pragma"] = "no-cache"
#     response.headers["Expires"] = "0"
#     return response

# @router.post("/login", response_class=HTMLResponse)
# async def login_form_post(request: Request, username: str = Form(...), password: str = Form(...)):
#     user = auth.get_user(username)
#     if not user or not auth.verify_password(password, user["hashed_password"]):
#         return templates.TemplateResponse("login.html", {"request": request, "error": "Incorrect username or password"})

#     if user.get("is_two_factor_enabled"):
#         temp_token = auth.create_access_token(
#             data={"sub": user["username"], "type": "pre-2fa"}, 
#             expires_delta=timedelta(minutes=5)
#         )
#         response = RedirectResponse(url="/login/verify-2fa", status_code=status.HTTP_303_SEE_OTHER)
#         response.set_cookie(key="temp_token", value=f"Bearer {temp_token}", httponly=True, samesite="strict", path="/")
#         return response
#     else:
#         access_token = auth.create_access_token(data={"sub": user["username"]}, expires_delta=timedelta(minutes=auth.settings.ACCESS_TOKEN_EXPIRE_MINUTES))
#         response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
#         response.set_cookie(key="access_token", value=f"Bearer {access_token}", httponly=True, samesite="strict", path="/")
#         return response

# @router.get("/login/verify-2fa", response_class=HTMLResponse)
# async def get_verify_2fa_page(request: Request):
#     response = templates.TemplateResponse("verify_2fa.html", {"request": request})
#     response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
#     response.headers["Pragma"] = "no-cache"
#     response.headers["Expires"] = "0"
#     return response

# @router.post("/login/verify-2fa", response_class=HTMLResponse)
# async def post_verify_2fa_page(request: Request, code: str = Form(...)):
#     temp_token = request.cookies.get("temp_token")
#     if not temp_token:
#         return RedirectResponse(url="/login")
    
#     try:
#         payload = jwt.decode(temp_token.split(" ")[1], auth.settings.SECRET_KEY, algorithms=[auth.settings.ALGORITHM])
#         if payload.get("type") != "pre-2fa": raise JWTError
#         username = payload.get("sub")
#         if not isinstance(username, str) or not username:
#             return RedirectResponse(url="/login")
#         user = auth.get_user(username)
#     except JWTError:
#         return RedirectResponse(url="/login")

#     if not user or not user.get("two_factor_secret") or not auth.verify_2fa_code(user["two_factor_secret"], code):
#         return templates.TemplateResponse("verify_2fa.html", {"request": request, "error": "Invalid code. Please try again."})

#     access_token = auth.create_access_token(data={"sub": user["username"]}, expires_delta=timedelta(minutes=auth.settings.ACCESS_TOKEN_EXPIRE_MINUTES))
#     response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
#     response.set_cookie(key="access_token", value=f"Bearer {access_token}", httponly=True, samesite="strict", path="/")
#     response.delete_cookie(key="temp_token", path="/")
#     return response

# @router.get("/security", response_class=HTMLResponse)
# async def security_page(request: Request):
#     user = await auth.get_current_user(request)
#     if not user:
#         return RedirectResponse(url="/login")
    
#     context = {"request": request, "user": user}
#     if not user.get("is_two_factor_enabled"):
#         secret = auth.generate_2fa_secret()
#         request.session['2fa_secret'] = secret
#         context["secret_key"] = secret
#     response = templates.TemplateResponse("security.html", context)
#     response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
#     response.headers["Pragma"] = "no-cache"
#     response.headers["Expires"] = "0"
#     return response

# @router.get("/security/2fa/qr-code", response_class=StreamingResponse)
# async def get_2fa_qr_code(request: Request):
#     secret = request.session.get('2fa_secret')
#     user = await auth.get_current_user(request)
#     if not secret or not user:
#         raise HTTPException(status_code=400, detail="Could not generate QR code.")

#     uri = auth.get_2fa_provisioning_uri(user["username"], secret)
#     img = qrcode.make(uri)
#     buf = io.BytesIO()
#     img.save(buf, "PNG")
#     buf.seek(0)
#     return StreamingResponse(buf, media_type="image/png")

# @router.post("/security/2fa/enable")
# async def enable_2fa(request: Request, code: str = Form(...)):
#     user = await auth.get_current_user(request)
#     secret_key = request.session.get('2fa_secret')
#     if not user or not secret_key:
#         return RedirectResponse(url="/login")

#     if auth.verify_2fa_code(secret_key, code):
#         conn = sqlite3.connect(settings.DATABASE_FILE, timeout=10)
#         conn.execute("UPDATE users SET two_factor_secret = ?, is_two_factor_enabled = 1 WHERE id = ?", (secret_key, user["id"]))
#         conn.commit()
#         conn.close()
#         return RedirectResponse(url="/security", status_code=status.HTTP_303_SEE_OTHER)
#     else:
#         context = {"request": request, "user": user, "secret_key": secret_key, "error": "Invalid code. Please try again."}
#         # return templates.TemplateResponse("security.html", context)
#         response = templates.TemplateResponse("security.html", context)
#         response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
#         response.headers["Pragma"] = "no-cache"
#         response.headers["Expires"] = "0"
#         return response

# @router.post("/security/2fa/disable")
# async def disable_2fa(request: Request):
#     user = await auth.get_current_user(request)
#     if not user:
#         return RedirectResponse(url="/login")
        
#     conn = sqlite3.connect(settings.DATABASE_FILE, timeout=10)
#     conn.execute("UPDATE users SET two_factor_secret = NULL, is_two_factor_enabled = 0 WHERE id = ?", (user["id"],))
#     conn.commit()
#     conn.close()
#     return RedirectResponse(url="/security", status_code=status.HTTP_303_SEE_OTHER)

# @router.get("/logout")
# async def logout():
#     response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
#     response.delete_cookie(key="access_token", path="/")
#     response.delete_cookie(key="temp_token", path="/")
#     return response




# @router.get("/api/monitoring/status")
# async def get_monitoring_status():
#     """Gets the current monitoring status (active or paused)."""
#     if not settings.STATUS_FILE.exists():
#         return {"is_active": True} # Default to active if file doesn't exist
#     with open(settings.STATUS_FILE, 'r') as f:
#         return json.load(f)

# @router.post("/api/monitoring/toggle")
# async def toggle_monitoring_status(request: Request):
#     """Toggles the monitoring status between active and paused."""
#     body = await request.json()
#     new_status = body.get("is_active")
#     with open(settings.STATUS_FILE, 'w') as f:
#         json.dump({"is_active": new_status}, f)
    
#     # Broadcast the status change to all connected clients
#     await broadcast({"type": "monitoring_status_update", "data": {"is_active": new_status}})
    
#     return {"status": "ok", "is_active": new_status}






# @router.post("/api/review/prepare")
# async def start_review_preparation(background_tasks: BackgroundTasks):

#     print("Received request to prepare review session.")
#     background_tasks.add_task(prepare_review_session)
#     return {"message": "Log clustering process has been started in the background."}

# @router.get("/api/review/clusters")
# async def get_review_clusters(sort_by: str = "log_count", sort_order: str = "desc"):

#     def get_clusters():
#         allowed_cols = {"log_count", "name", "first_seen", "last_seen", "confidence"}
#         order_col = sort_by if sort_by in allowed_cols else "log_count"
#         order_dir = "DESC" if sort_order == "desc" else "ASC"

#         conn = sqlite3.connect(settings.DATABASE_FILE)
#         conn.row_factory = sqlite3.Row
#         # Fetches pending clusters from the new 'cluster' table name
#         query = f"""
#             SELECT * FROM cluster 
#             WHERE status = 'pending' AND is_noise = 0
#             ORDER BY {order_col} {order_dir}
#         """
#         # clusters = [dict(row) for row in conn.execute(query).fetchall()]
#         db_rows = conn.execute(query).fetchall()
#         conn.close()

#         clusters = []
#         for row in db_rows:
#             cluster_dict = dict(row)
#             # Check if the centroid is not None and is of bytes type
#             if cluster_dict.get('centroid') and isinstance(cluster_dict['centroid'], bytes):
#                 # Encode the raw binary data into a safe base64 text string
#                 cluster_dict['centroid'] = base64.b64encode(cluster_dict['centroid']).decode('ascii')
#             clusters.append(cluster_dict)
#         return clusters
#     return await run_in_threadpool(get_clusters)

# @router.post("/api/review/clusters/{cluster_id}")
# async def label_cluster(cluster_id: str, update: BulkLabelUpdate):
#     """
#     Applies a label to all logs within a cluster and marks them as reviewed.
#     """
#     def update_cluster_in_db():
#         conn = sqlite3.connect(settings.DATABASE_FILE)
#         cur = conn.cursor()

#         # 1. Find all log IDs associated with this cluster
#         log_ids_to_update = cur.execute(
#             "SELECT log_id FROM logCluster WHERE cluster_id = ?", (cluster_id,)
#         ).fetchall()
        
#         if not log_ids_to_update:
#             return {"status": "error", "message": "Cluster not found or already processed."}
        
#         # The result is a list of tuples, e.g., [(123,), (124,)], so we flatten it
#         log_ids = [item[0] for item in log_ids_to_update]

#         # 2. Update all those logs in the 'logs' table
#         # We use a placeholder string '(?, ?, ...)' for the 'IN' clause
#         placeholders = ', '.join('?' for _ in log_ids)
#         update_query = f"UPDATE logs SET final_label = ?, is_reviewed = 1 WHERE id IN ({placeholders})"
        
#         # The parameters list must include the new_label first, then the log IDs
#         params = [update.new_label] + log_ids
#         cur.execute(update_query, params)

#         # 3. Update the cluster's status to 'reviewed'
#         cur.execute("UPDATE cluster SET status = 'reviewed' WHERE cluster_id = ?", (cluster_id,))
        
#         conn.commit()
#         conn.close()
#         return {"status": "ok", "updated_count": len(log_ids)}

#     return await run_in_threadpool(update_cluster_in_db)


# @router.get("/api/review/clusters/{cluster_id}/logs")
# async def get_logs_in_cluster(cluster_id: str):
#     """Fetches all individual logs that belong to a specific cluster."""
#     def get_logs():
#         conn = sqlite3.connect(settings.DATABASE_FILE)
#         conn.row_factory = sqlite3.Row
#         query = """
#             SELECT l.id, l.timestamp, l.content, l.predicted_label, l.risk_score, l.sequence_risk
#             FROM logs l
#             JOIN logCluster lc ON l.id = lc.log_id
#             WHERE lc.cluster_id = ?
#             ORDER BY l.timestamp DESC
#         """
#         logs = [dict(row) for row in conn.execute(query, (cluster_id,)).fetchall()]
#         conn.close()
#         return logs
#     return await run_in_threadpool(get_logs)

# @router.post("/api/review/manual_logs")
# async def get_manual_review_logs(query: ManualLogsQuery):

#     def get_logs_from_db():
#         # Whitelist of allowed columns to sort by to prevent SQL injection
#         allowed_sort_columns = {"timestamp", "risk_score", "source", "predicted_label"}
#         sort_by = "timestamp" # Default
#         if query.sort_by in allowed_sort_columns:
#             sort_by = query.sort_by

#         sort_order = "DESC" if query.sort_order.lower() == "desc" else "ASC"

#         conn = sqlite3.connect(settings.DATABASE_FILE)
#         conn.row_factory = sqlite3.Row
        
#         # The SQL query is dynamically built with the safe sort parameters
#         sql_query = f"""
#             SELECT id, timestamp, source, content, predicted_label, risk_score, sequence_risk
#             FROM logs 
#             WHERE is_reviewed = 0 
#             ORDER BY {sort_by} {sort_order}
#         """
        
#         entries = [dict(row) for row in conn.execute(sql_query).fetchall()]
#         conn.close()
#         return entries

#     return await run_in_threadpool(get_logs_from_db)

# @router.get("/api/review/noise")
# async def get_noise_logs(sort_by: str = "last_seen", sort_order: str = "desc"):
#     """Fetches all pending logs that were marked as noise (unclustered)."""
#     def get_logs():
#         allowed_cols = {"last_seen", "representative_log"} # Fewer options for noise
#         order_col = sort_by if sort_by in allowed_cols else "last_seen"
#         order_dir = "DESC" if sort_order == "desc" else "ASC"

#         conn = sqlite3.connect(settings.DATABASE_FILE)
#         conn.row_factory = sqlite3.Row
#         query = f"""
#             SELECT * FROM cluster 
#             WHERE status = 'pending' AND is_noise = 1 
#             ORDER BY {order_col} {order_dir}"""
        
#         db_rows = conn.execute(query).fetchall()
#         conn.close()

#         # --- FIX STARTS HERE ---
#         # Convert the rows to dictionaries and handle the binary centroid
#         noise_logs = []
#         for row in db_rows:
#             log_dict = dict(row)
#             # Check for and encode the binary centroid data
#             if log_dict.get('centroid') and isinstance(log_dict['centroid'], bytes):
#                 log_dict['centroid'] = base64.b64encode(log_dict['centroid']).decode('ascii')
#             noise_logs.append(log_dict)
#         # --- FIX ENDS HERE ---
            
#         return noise_logs
        
#     return await run_in_threadpool(get_logs)

# @router.get("/api/stats/top_n")
# async def get_top_n_stats(field: str = "verdict", limit: int = 5):
#     """
#     Gets the top N most frequent values for a given field from anomalous logs.
#     Valid fields: 'verdict', 'ip', 'source'.
#     """
#     def get_data():
#         conn = sqlite3.connect(settings.DATABASE_FILE)
        
#         # Whitelist of allowed fields to query
#         if field not in ["verdict", "ip", "source"]:
#             conn.close()
#             return {"error": "Invalid field specified."}

#         query = f"SELECT content, verdict, source FROM logs WHERE final_label = 1"
#         df = pd.read_sql_query(query, conn)
#         conn.close()

#         if df.empty:
#             return []
        
#         # For IPs, we need to extract them from the content
#         target_column = field
#         if field == 'ip':
#             df['ip'] = df['content'].apply(extract_ip_from_string)

#         if target_column not in df.columns:
#             return []
        
#         df.dropna(subset=[target_column], inplace=True)
        
#         if df.empty:
#             return []

#         valid_items = [item for item in df[target_column] if pd.notna(item)]
#         counts = Counter(valid_items).most_common(limit)
        
#         # Format for Chart.js
#         return [{"item": item, "count": count} for item, count in counts]
        
#     return await run_in_threadpool(get_data)