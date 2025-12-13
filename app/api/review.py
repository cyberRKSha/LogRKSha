# app/api/review.py
from fastapi import APIRouter, BackgroundTasks
from fastapi.concurrency import run_in_threadpool
import psycopg2, psycopg2.extras
import base64
from typing import Optional, List, Dict, Any

from app.config import settings
from scripts.review_manager import prepare_review_session
from .models import ReviewUpdateItem, BulkLabelUpdate, ManualLogsQuery
from sqlalchemy import create_engine, text

task_status = {
    "prepare_clusters": {"status": "idle", "message": "No active task."}
}

router = APIRouter(prefix="/api/review", tags=["Review"])

def run_prepare_and_set_status():
    task_status["prepare_clusters"] = {"status": "running", "message": "Clustering in progress..."}
    try:
        result_message = prepare_review_session()
        task_status["prepare_clusters"] = {"status": "completed", "message": result_message}
    except Exception as e:
        task_status["prepare_clusters"] = {"status": "failed", "message": f"Error during clustering: {e}"}

@router.post("/prepare")
async def start_review_preparation(background_tasks: BackgroundTasks):
    if task_status["prepare_clusters"]["status"] == "running":
        return {"message": "Clustering is already in progress."}

    print("Received request to prepare review session.")
    background_tasks.add_task(prepare_review_session)
    return {"message": "Log clustering process has been started in the background."}

@router.get("/prepare/status")
async def get_prepare_status():
    return task_status["prepare_clusters"]

@router.get("/clusters")
async def get_review_clusters(sort_by: str = "log_count", sort_order: str = "desc"):
    def get_clusters():
        engine = create_engine(settings.DATABASE_URL)
        allowed_cols = {"log_count", "name", "first_seen", "last_seen", "confidence"}
        order_col = sort_by if sort_by in allowed_cols else "log_count"
        order_dir = "DESC" if sort_order == "desc" else "ASC"

        query = text(f"""
            SELECT * FROM cluster 
            WHERE status = 'pending' AND is_noise = 0
            ORDER BY {order_col} {order_dir}
        """)
        
        try:
            with engine.connect() as connection:
                db_rows = connection.execute(query).fetchall()

            clusters = []
            for row in db_rows:
                row_dict = dict(row._mapping)
                confidence = float(row_dict.get('confidence', 0.0))
                model_pred = 1 if confidence > 0.5 else 0 # Simple inference
                cluster_dict = {
                    'cluster_id': str(row_dict.get('cluster_id')),
                    'name': str(row_dict.get('name')),
                    'status': str(row_dict.get('status')),
                    'log_count': int(row_dict.get('log_count', 0)),
                    'representative_log': str(row_dict.get('representative_log')),
                    'first_seen': str(row_dict.get('first_seen')),
                    'last_seen': str(row_dict.get('last_seen')),
                    'centroid': base64.b64encode(row_dict['centroid']).decode('ascii') if row_dict.get('centroid') and isinstance(row_dict['centroid'], bytes) else None,
                    'is_noise': int(row_dict.get('is_noise', 0)),
                    'confidence': confidence,
                    'model_prediction': model_pred
                }
                clusters.append(cluster_dict)
            return clusters
        except Exception as error:
            print(f"Database error in get_review_clusters: {error}")
            return []
                
    return await run_in_threadpool(get_clusters)

@router.post("/clusters/{cluster_id}")
async def label_cluster(cluster_id: str, update: BulkLabelUpdate):
    """
    Applies a label to all logs within a cluster using SQLAlchemy.
    """
    def update_cluster_in_db():
        engine = create_engine(settings.DATABASE_URL)
        try:
            with engine.connect() as connection:
                with connection.begin() as transaction:
                    # Find all log IDs associated with this cluster
                    log_ids_result = connection.execute(
                        text("SELECT log_id FROM logCluster WHERE cluster_id = :cid"),
                        {"cid": cluster_id}
                    ).fetchall()
                    
                    if not log_ids_result:
                        return {"status": "error", "message": "Cluster not found or already processed."}
                    
                    log_ids = [item[0] for item in log_ids_result]

                    # Update all those logs in the 'logs' table
                    update_logs_query = text("UPDATE logs SET final_label = :new_label, is_reviewed = 1 WHERE id = ANY(:log_ids)")
                    connection.execute(update_logs_query, {"new_label": update.new_label, "log_ids": log_ids})

                    # Update the cluster's status to 'reviewed'
                    update_cluster_query = text("UPDATE cluster SET status = 'reviewed' WHERE cluster_id = :cid")
                    connection.execute(update_cluster_query, {"cid": cluster_id})
                    
                    return {"status": "ok", "updated_count": len(log_ids)}
        except Exception as error:
            print(f"Database error in label_cluster: {error}")
            return {"status": "error", "message": str(error)}

    return await run_in_threadpool(update_cluster_in_db)

@router.get("/clusters/{cluster_id}/logs")
async def get_logs_in_cluster(cluster_id: str):
    """Fetches all individual logs that belong to a specific cluster using SQLAlchemy."""
    def get_logs():
        engine = create_engine(settings.DATABASE_URL)
        query = text("""
            SELECT l.id, l.timestamp, l.content, l.predicted_label, l.risk_score, l.sequence_risk
            FROM logs l
            JOIN logCluster lc ON l.id = lc.log_id
            WHERE lc.cluster_id = :cid
            ORDER BY l.timestamp DESC
        """)
        try:
            with engine.connect() as connection:
                result = connection.execute(query, {"cid": cluster_id}).fetchall()
                logs = [dict(row._mapping) for row in result]
                return logs
        except Exception as error:
            print(f"Database error in get_logs_in_cluster: {error}")
            return []
                
    return await run_in_threadpool(get_logs)

@router.post("/manual_logs")
async def get_manual_review_logs(query: ManualLogsQuery):
    """
    Fetches unreviewed logs for manual review using SQLAlchemy.
    """
    def get_logs_from_db():
        engine = create_engine(settings.DATABASE_URL)
        allowed_sort_columns = {"timestamp", "risk_score", "source", "predicted_label"}
        sort_by = query.sort_by if query.sort_by in allowed_sort_columns else "timestamp"
        sort_order = "DESC" if query.sort_order.lower() == "desc" else "ASC"

        sql_query = text(f"""
            SELECT id, timestamp, source, content, predicted_label, risk_score, sequence_risk
            FROM logs 
            WHERE is_reviewed = 0 
            ORDER BY {sort_by} {sort_order}
        """)
        
        try:
            with engine.connect() as connection:
                result = connection.execute(sql_query).fetchall()
                entries = [dict(row._mapping) for row in result]
                return entries
        except Exception as error:
            print(f"Database error in get_manual_review_logs: {error}")
            return []

    return await run_in_threadpool(get_logs_from_db)

@router.get("/noise")
async def get_noise_logs(sort_by: str = "last_seen", sort_order: str = "desc"):
    """Fetches all pending noise logs using SQLAlchemy."""
    def get_logs():
        engine = create_engine(settings.DATABASE_URL)
        allowed_cols = {"last_seen", "representative_log"}
        order_col = sort_by if sort_by in allowed_cols else "last_seen"
        order_dir = "DESC" if sort_order == "desc" else "ASC"

        query = text(f"""
            SELECT * FROM cluster 
            WHERE status = 'pending' AND is_noise = 1 
            ORDER BY {order_col} {order_dir}
        """)
        
        try:
            with engine.connect() as connection:
                db_rows = connection.execute(query).fetchall()

            noise_logs = []
            for row in db_rows:
                row_dict = dict(row._mapping)
                log_dict = {
                    'cluster_id': str(row_dict.get('cluster_id')),
                    'name': str(row_dict.get('name')),
                    'status': str(row_dict.get('status')),
                    'log_count': int(row_dict.get('log_count', 0)),
                    'representative_log': str(row_dict.get('representative_log')),
                    'first_seen': str(row_dict.get('first_seen')),
                    'last_seen': str(row_dict.get('last_seen')),
                    'centroid': base64.b64encode(row_dict['centroid']).decode('ascii') if row_dict.get('centroid') and isinstance(row_dict['centroid'], bytes) else None,
                    'is_noise': int(row_dict.get('is_noise', 0)),
                    'confidence': float(row_dict.get('confidence', 0.0)),
                    'predicted_label': int(row_dict['predicted_label']) if row_dict.get('predicted_label') is not None else 0
                }
                noise_logs.append(log_dict)
            return noise_logs
        except Exception as error:
            print(f"Database error in get_noise_logs: {error}")
            return []
        
    return await run_in_threadpool(get_logs)

@router.get("/pending", response_model=List[Dict[str, Any]])
async def get_pending_logs_api(sort_by: Optional[str] = None):
    """
    API endpoint to get pending logs as JSON data using SQLAlchemy.
    """
    def get_logs_from_db():
        engine = create_engine(settings.DATABASE_URL)
        query_str = """
            SELECT l.*, a.status
            FROM logs l
            LEFT JOIN alerts a ON l.id = a.log_id
            WHERE l.is_reviewed = 0
        """
        if sort_by == '1':
            query_str += " ORDER BY predicted_label DESC, timestamp DESC"
        elif sort_by == '0':
            query_str += " ORDER BY predicted_label ASC, timestamp DESC"
        else:
            query_str += " ORDER BY timestamp DESC"
        
        try:
            with engine.connect() as connection:
                result = connection.execute(text(query_str)).fetchall()
                entries = [dict(row._mapping) for row in result]
                return entries
        except Exception as error:
            print(f"Database error in get_pending_logs_api: {error}")
            return []

    return await run_in_threadpool(get_logs_from_db)

@router.post("/update")
async def update_reviews_api(updates: List[ReviewUpdateItem]):
    """
    API endpoint to receive and process reviewed logs using SQLAlchemy.
    """
    def update_database():
        engine = create_engine(settings.DATABASE_URL)
        query = text("UPDATE logs SET final_label = :new_label, is_reviewed = 1 WHERE id = :log_id")
        
        # Prepare data for executemany
        update_params = [{"new_label": item.new_label, "log_id": item.id} for item in updates]
        
        try:
            with engine.connect() as connection:
                with connection.begin() as transaction:
                    connection.execute(query, update_params)
            return {"status": "ok", "updated_count": len(updates)}
        except Exception as error:
            print(f"Database error in update_reviews_api: {error}")
            return {"status": "error", "message": str(error)}

    return await run_in_threadpool(update_database)