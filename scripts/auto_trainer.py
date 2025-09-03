# scripts/auto_trainer.py
import sys
import os
import json
import psycopg2, psycopg2.extras

# Add project root to path to allow imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.config import settings
from scripts.update import trigger_model_update, get_last_processed_id

def log_info(msg): print(f"\033[94mℹ️ {msg}\033[0m")
def log_success(msg): print(f"\033[92m✅ {msg}\033[0m")
def log_error(msg): print(f"\033[91m❗ {msg}\033[0m")
def log_warn(msg): print(f"\033[93m⚠️ {msg}\033[0m")

# --- CONFIGURATION ---
MIN_TRAINING_THRESHOLD = 5000
# MAX_TRAINING_THRESHOLD = 10000
WORKER_LOCK_FILE = os.path.join(project_root, "worker.lock")
MONITOR_LOCK_FILE = os.path.join(project_root, "monitor.lock")
WEBAPP_LOCK_FILE = os.path.join(project_root, "webapp.lock")

def can_train():
    """Checks if the monitoring/worker scripts are running."""
    webapp_is_active = os.path.exists(WEBAPP_LOCK_FILE)
    worker_is_active = os.path.exists(WORKER_LOCK_FILE)
    monitor_is_active = os.path.exists(MONITOR_LOCK_FILE)

    is_monitor_paused = False
    if os.path.exists(settings.STATUS_FILE):
        try:
            with open(settings.STATUS_FILE, 'r') as f:
                # 'is_active' will be False if the toggle is off (paused)
                if not json.load(f).get("is_active", True):
                    is_monitor_paused = True
                    log_info("Dashboard monitoring is currently paused.")
        except (json.JSONDecodeError, IOError):
            pass # Ignore errors and assume it's not paused

    if webapp_is_active and not worker_is_active and (not monitor_is_active or is_monitor_paused):
        log_info("System is in the correct idle state. It is safe to check for training.")
        return True
    else:
        log_info("System is not in the correct idle state for training.")
        if not webapp_is_active:
            log_warn("Reason: Webapp (run.py) is not running.")
        if worker_is_active:
            log_warn("Reason: Worker process (worker.lock) is active.")
        if monitor_is_active and not is_monitor_paused:
            log_warn("Reason: Monitor process (monitor.lock) is active and not paused.")
        return False

# def check_and_train():

#     if not can_train():
#         return

#     log_info("Checking for new reviewed logs...")
#     last_id = get_last_processed_id() # We'd need to create this helper in update.py
    
#     conn = psycopg2.connect(settings.DATABASE_FILE)
#     cursor = conn.cursor()
    
#     query = f"SELECT COUNT(id) FROM logs WHERE is_reviewed = 1 AND id > ?"
#     new_log_count = cursor.execute(query, (last_id,)).fetchone()[0]
#     conn.close()
    
#     log_info(f"Found {new_log_count} new reviewed logs. Required range: {MIN_TRAINING_THRESHOLD}.")
    
#     if new_log_count >= MIN_TRAINING_THRESHOLD:
#         log_success("Logs Threshold met! Triggering model update process...")
#         try:
#             trigger_model_update()
#             log_success("Model update process completed successfully.")
#         except Exception as e:
#             log_error(f"Model update process failed: {e}")
#     else:
#         log_info("Log count is not par the required range. No training will occur.")

def check_and_train():
    if not can_train():
        return

    log_info("Checking for new reviewed logs...")
    last_id = get_last_processed_id()
    
    conn = None # Initialize to None for robust error handling
    try:
        # 1. Connect using the DATABASE_URL from your settings
        conn = psycopg2.connect(settings.DATABASE_URL)
        cursor = conn.cursor()
        
        # 2. Use %s for the placeholder, not ?
        query = "SELECT COUNT(id) FROM logs WHERE is_reviewed = 1 AND id > %s"
        
        # 3. Execute the query and fetch the result in two separate steps
        cursor.execute(query, (last_id,))
        result = cursor.fetchone()
        new_log_count = result[0] if result else 0
        
        cursor.close()
        
    except (Exception, psycopg2.DatabaseError) as error:
        log_error(f"Database error in check_and_train: {error}")
        new_log_count = 0 # Default to 0 on error
    finally:
        if conn is not None:
            conn.close()
      
    log_info(f"Found {new_log_count} new reviewed logs. Required: {MIN_TRAINING_THRESHOLD}.")
      
    if new_log_count >= MIN_TRAINING_THRESHOLD:
        log_success("Log threshold met! Triggering model update process...")
        try:
            trigger_model_update()
            log_success("Model update process completed successfully.")
        except Exception as e:
            log_error(f"Model update process failed: {e}")
    else:
        log_info("Log count not in required range. No training will occur.")

if __name__ == "__main__":
    check_and_train()
