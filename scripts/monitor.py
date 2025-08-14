# monitor.py
# import os
# import joblib
# import sqlite3
# from datetime import datetime
# import numpy as np
# import json
# import hashlib
# import requests
# import threading
# import time
# import subprocess
# from sentence_transformers import SentenceTransformer
# from drain3 import TemplateMiner
# from drain3.template_miner_config import TemplateMinerConfig
# import tensorflow as tf

# # --- Configuration ---
# # --- (Keep your existing configuration for paths, URLs, etc.) ---
# BASE_DIR = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux" # Example path
# DATABASE_FILE = os.path.join(BASE_DIR, "log_database.db")
# EMBEDDER_PATH = os.path.join(BASE_DIR, "model/sentence_embedder.pkl")
# MODEL_PATH = os.path.join(BASE_DIR, "model/sgd_embedder.pkl")
# KNOWN_HASHES_FILE = os.path.join(BASE_DIR, "logs/kwnhashes.txt")
# ALERTS_CONFIG_FILE = os.path.join(BASE_DIR, "scripts/alerts_config.json")
# ALERT_SOUND = os.path.join(BASE_DIR, "logs/alert.wav")
# DASHBOARD_URL = "http://127.0.0.1:8000"
# LOG_FILES = [
#     "/var/log/mp-auth.log",
#     "/var/log/mp-kern.log",
#     "/var/log/pacman.log",
#     "/var/log/Xorg.0.log",
# ]

# IGNORED_PATTERNS = [
#     "ACPI group/action undefined: button/",
#     "ACPI group/action undefined: video/",
# ]
# # --- (Keep the rest of your existing configuration) ---

# # === Colors helpers ===
# def log_info(msg): print(f"\033[94mℹ️ {msg}\033[0m")
# def log_success(msg): print(f"\032[92m✅ {msg}\033[0m")
# def log_warning(msg): print(f"\033[93m⚠️ {msg}\033[0m")
# def log_error(msg): print(f"\033[91m❗ {msg}\033[0m")
# def log_dim(msg): print(f"\033[90m{msg}\033[0m")


# # === Load Models ===
# log_info("Loading embedding and prediction models...")
# embedder = joblib.load(EMBEDDER_PATH)
# model = joblib.load(MODEL_PATH)
# log_success("Models loaded successfully.")

# # === Load Alert Configuration ===
# try:
#     with open(ALERTS_CONFIG_FILE, 'r') as f:
#         alert_config = json.load(f)
#     log_success("✅ Loaded alerts_config.json successfully.")
# except FileNotFoundError:
#     log_error(f"{ALERTS_CONFIG_FILE} not found! External alerts will not be sent.")
#     alert_config = {"rules": [], "notifications": {}}
# except json.JSONDecodeError:
#     log_error(f"Error decoding {ALERTS_CONFIG_FILE}. Please check its format.")
#     alert_config = {"rules": [], "notifications": {}}

# # === Load known hashes ===
# if os.path.exists(KNOWN_HASHES_FILE):
#     with open(KNOWN_HASHES_FILE, 'r') as f:
#         known_hashes = set(line.strip() for line in f)
# else:
#     known_hashes = set()

# # === NEW DATABASE FUNCTION ===
# def insert_log_to_db(source: str, content: str, predicted_label: int):
#     """Inserts a new, unreviewed log into the database."""
#     try:
#         conn = sqlite3.connect(DATABASE_FILE)
#         cursor = conn.cursor()
#         timestamp = datetime.now().isoformat()

#         # The final_label defaults to the predicted_label initially.
#         # is_reviewed defaults to 0 (pending review).
#         cursor.execute("""
#             INSERT INTO logs (timestamp, source, content, predicted_label, final_label, is_reviewed)
#             VALUES (?, ?, ?, ?, ?, 0)
#         """, (timestamp, source, content, predicted_label, predicted_label))

#         conn.commit()
#         conn.close()
#     except Exception as e:
#         log_error(f"Database write failed: {e}")

# # --- (Keep your existing functions like play_alert_sound, send_to_dashboard, send_slack_alert, etc.) ---

# def play_alert_sound():
#     try:
#         subprocess.Popen(['paplay', ALERT_SOUND])
#     except Exception as e:
#         log_warning(f"Sound playback failed: {e}")

# def send_to_dashboard(log_text, label_str):
#     payload = {"log": log_text, "label": label_str, "timestamp": datetime.now().isoformat()}
#     try:
#         requests.post(f"{DASHBOARD_URL}/api/new_log", json=payload, timeout=1)
#     except Exception as e:
#         log_warning(f"Failed to send to dashboard: {e}")

# def is_new_log_and_save_hash(log_text):
#     h = hashlib.sha256(log_text.encode('utf-8')).hexdigest()
#     if h not in known_hashes:
#         known_hashes.add(h)
#         with open(KNOWN_HASHES_FILE, 'a') as f:
#             f.write(h + '\n')
#         return True
#     return False

# def save_hashes_periodically(interval=60):
#     while True:
#         time.sleep(interval)
#         try:
#             with open(KNOWN_HASHES_FILE, 'w') as f:
#                 for h in known_hashes:
#                     f.write(h + '\n')
#             log_dim(f"💾 Periodic save of known hashes ({len(known_hashes)})")
#         except Exception as e:
#             log_error(f"Failed to save known hashes: {e}")

# def process_log(source, line):
#     # --- (Keep your existing IGNORED_PATTERNS logic) ---
#     if any(p in line for p in IGNORED_PATTERNS):
#         log_dim(f"⏩ Ignored harmless log in {source}: {line}")
#         return

#     # NLP embedding prediction
#     embedding = embedder.encode([line])
#     pred = model.predict(embedding)[0]
#     label_str = 'anomaly' if pred == 1 else 'normal'

#     if label_str == 'anomaly':
#         log_error(f"Anomaly detected in {source}: {line}")
#     else:
#         log_success(f"Normal in {source}: {line}")

#     # Send to dashboard for real-time view
#     send_to_dashboard(line, label_str)

#     # If the log is unique, add it to the database for review
#     if is_new_log_and_save_hash(line):
#         insert_log_to_db(source, line, int(pred))
#         log_info(f"New unique log added to database for review.")
#     else:
#         log_dim(f"Duplicate log detected. Skipped database insertion.")

#     # This block now handles all alert logic.
#     if label_str == 'anomaly':
#         # STEP 1: Always send a generic alert to the dashboard for ANY anomaly.
#         try:
#             advice = "Anomaly detected by ML model. Review for details."
#             requests.post(f"{DASHBOARD_URL}/api/new_alert", json={"log": line, "advice": advice}, timeout=1)
#             play_alert_sound() # Play sound for any anomaly
#         except Exception as e:
#             log_warning(f"Failed to send generic alert to dashboard: {e}")
#     # --- (Keep your existing alert logic for sending notifications) ---


# # --- (Keep your existing LogHandler class, watch_journalctl function, and the main execution block) ---
# class LogHandler(FileSystemEventHandler):
#     def __init__(self, file_path):
#         super().__init__()
#         self.file_path = file_path
#         self._last_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

#     def on_modified(self, event):
#         if event.src_path == self.file_path:
#             try:
#                 new_size = os.path.getsize(self.file_path)
#                 if new_size > self._last_size:
#                     with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
#                         f.seek(self._last_size)
#                         for line in f:
#                             if line.strip():
#                                 process_log(os.path.basename(self.file_path), line.strip())
#                     self._last_size = new_size
#             except FileNotFoundError:
#                 log_warning(f"File vanished, skipping: {self.file_path}")
#                 self._last_size = 0
#             except Exception as e:
#                 log_error(f"Error processing modified file {self.file_path}: {e}")

# def watch_journalctl():
#     log_info("🚀 Started journalctl monitoring...")
#     process = subprocess.Popen(['journalctl', '-f', '-o', 'cat'],
#                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='ignore')
#     for line in process.stdout:
#         if line.strip():
#             process_log('journalctl', line.strip())

# if __name__ == "__main__":
#     observer = Observer()
#     threading.Thread(target=save_hashes_periodically, daemon=True).start()

#     for file_path in LOG_FILES:
#         if os.path.exists(file_path):
#             event_handler = LogHandler(file_path)
#             observer.schedule(event_handler, os.path.dirname(file_path), recursive=False)
#             log_info(f"📄 Watching {file_path}")
#         else:
#             log_warning(f"❗ File not found (skipped): {file_path}")

#     threading.Thread(target=watch_journalctl, daemon=True).start()

#     observer.start()
#     log_info("🚀 Monitoring logs: Press CTRL+C to stop.")

#     try:
#         while True:
#             time.sleep(1)
#     except KeyboardInterrupt:
#         observer.stop()
#         print("\n🛑 Stopped monitoring.")

#     observer.join()














































































# monitor.py (ULTIMATE HYBRID VERSION - Supervised + Autoencoder)

import os
import joblib
import sqlite3
from datetime import datetime, timezone
import numpy as np
import json
import hashlib
import requests
import threading
import time
import subprocess
import dill
import queue
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from sentence_transformers import SentenceTransformer
from drain3 import TemplateMiner
# from sklearn.pipeline import make_pipeline
import tensorflow as tf

# --- Configuration ---
BASE_DIR = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux"
DATABASE_FILE = os.path.join(BASE_DIR, "log_database.db")
# Models
EMBEDDER_PATH = os.path.join(BASE_DIR, "model/sentence_embedder.pkl")
DRAIN_PATH = os.path.join(BASE_DIR, "model/template_miner.pkl")
# This is your ORIGINAL supervised model
SUPERVISED_MODEL_PATH = os.path.join(BASE_DIR, "model/sgd_embedder.pkl")
# This is your NEW unsupervised model
AUTOENCODER_PATH = os.path.join(BASE_DIR, "model/autoencoder_model.keras")
THRESHOLD_PATH = os.path.join(BASE_DIR, "model/autoencoder_threshold.json")
# Other Configs
DASHBOARD_URL = "http://127.0.0.1:8000"
KNOWN_HASHES_FILE = os.path.join(BASE_DIR, "logs/kwnhashes.txt")
ALERT_SOUND = os.path.join(BASE_DIR, "logs/alert.wav")
LOG_FILES = [
    "/var/log/mp-auth.log",
    "/var/log/mp-kern.log",
    "/var/log/pacman.log",
    "/var/log/Xorg.0.log",
]
IGNORED_PATTERNS = [
    "ACPI group/action undefined: button/",
    "ACPI group/action undefined: video/",
]
# EXPLAINER_PATH = os.path.join(BASE_DIR, "model/lime_explainer.pkl")

# --- Logging Helpers ---
def log_info(msg): print(f"\033[94mℹ️ {msg}\033[0m")
def log_success(msg): print(f"\033[92m✅ {msg}\033[0m")
def log_error(msg): print(f"\033[91m❗ {msg}\033[0m")
def log_dim(msg): print(f"\033[90m{msg}\033[0m")
def log_warning(msg): print(f"\033[93m⚠️ {msg}\033[0m")

# === Load ALL Models at Startup ===
log_info("Loading all models for hybrid analysis...")
embedder = joblib.load(EMBEDDER_PATH)
template_miner = joblib.load(DRAIN_PATH)
supervised_model = joblib.load(SUPERVISED_MODEL_PATH)
unsupervised_model = tf.keras.models.load_model(AUTOENCODER_PATH)
with open(THRESHOLD_PATH, 'r') as f:
    unsupervised_threshold = json.load(f)['threshold']
# with open(EXPLAINER_PATH, 'rb') as f:
#     explainer = dill.load(f)
log_success("✅ All models loaded successfully.")

# === Load known hashes ===
if os.path.exists(KNOWN_HASHES_FILE):
    with open(KNOWN_HASHES_FILE, 'r') as f:
        known_hashes = set(line.strip() for line in f)
else:
    known_hashes = set()

# === Helper Functions ===
def insert_log_to_db(source: str, content: str, predicted_label: int, risk_score: float, is_reviewed: int = 0, explanation: str = ""):
    """Inserts a new log with its risk score into the database."""
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        timestamp = datetime.now().isoformat(timespec='milliseconds')
        
        cursor.execute("""
            INSERT INTO logs (timestamp, source, content, predicted_label, final_label, is_reviewed, risk_score, explanation)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (timestamp, source, content, predicted_label, predicted_label, is_reviewed, risk_score, explanation))
        
        new_log_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return new_log_id
    
    except Exception as e:
        log_error(f"Database write failed: {e}")


def play_alert_sound():
    try:
        subprocess.Popen(['paplay', ALERT_SOUND])
    except Exception as e:
        log_warning(f"Sound playback failed: {e}")

def send_to_dashboard(log_text, label_str, verdict="", risk_score=0.0):
    """Sends log data, including the risk score, to the dashboard via WebSocket."""
    try:
        payload = {
            "log": log_text,
            "label": label_str,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec='milliseconds'),
            "verdict": verdict,
            "risk_score": risk_score, # Add the risk score to the payload
        }
        requests.post(f"{DASHBOARD_URL}/api/new_log", json=payload, timeout=1)
    except Exception as e:
        log_warning(f"Failed to send to dashboard: {e}")

def is_new_log_and_save_hash(log_text):
    h = hashlib.sha256(log_text.encode('utf-8')).hexdigest()
    if h not in known_hashes:
        known_hashes.add(h)
        with open(KNOWN_HASHES_FILE, 'a') as f:
            f.write(h + '\n')
        return True
    return False

# === REVISED process_log FUNCTION FOR HYBRID ANALYSIS ===
def process_log(source, line):
    if any(p in line for p in IGNORED_PATTERNS):
        return

    embedding = embedder.encode([line])
    # cluster = template_miner.add_log_message(line)
    # log_template = cluster["template_mined"]
    supervised_pred = supervised_model.predict(embedding)[0]
    reconstruction = unsupervised_model.predict(embedding, verbose=0)
    reconstruction_loss = tf.keras.losses.mae(reconstruction, embedding)[0].numpy()
    risk_score = min(1.0, reconstruction_loss / unsupervised_threshold)
    unsupervised_pred = 1 if reconstruction_loss > unsupervised_threshold else 0

    # explanation_html = ""
    verdict = "Normal"
    is_anomaly = False
    if supervised_pred == 1:
        verdict = "Known Anomaly (Supervised)"
        is_anomaly = True
        # try:
        #     # Recreate the pipeline for prediction probabilities
        #     def predictor_fn(text_list):
        #         embeddings = embedder.encode(text_list)
        #         return supervised_model.predict_proba(embeddings)
        #     # Now, we pass our custom function to the explainer
        #     exp = explainer.explain_instance(
        #         line, 
        #         predictor_fn, 
        #         num_features=6, 
        #         labels=[1]
        #     )
        #     explanation_html = exp.as_html()
        # except Exception as e:
        #     log_warning(f"Could not generate LIME explanation: {e}")

    elif unsupervised_pred == 1:
        verdict = "Novelty Detected (Unsupervised)"
        is_anomaly = True

    if not is_anomaly:
        risk_score = 0.0

    log_info(f"Verdict: [{verdict}] | RiskScore: {risk_score} | Loss: {reconstruction_loss:.4f} | Log: {line}")

    label_str = 'anomaly' if is_anomaly else 'normal'
    send_to_dashboard(line, label_str, verdict, risk_score)

    # if is_new_log_and_save_hash(line):
    #     insert_log_to_db(source, line, int(is_anomaly), risk_score)

    is_unique_for_review = is_new_log_and_save_hash(line)
    log_is_reviewed_status = 0 if is_unique_for_review else 1
    new_log_id = insert_log_to_db(source, line, int(is_anomaly), risk_score, log_is_reviewed_status, "")


    if is_anomaly:
        # Create a formal alert in the DB that can be managed
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO alerts (log_id, timestamp, rule_name, status)
            VALUES (?, ?, ?, 'New')
        """, (new_log_id, datetime.now(timezone.utc).isoformat(), verdict))
        alert_id = cursor.lastrowid # Get the new alert's ID
        conn.commit()
        conn.close()

        # Send a rich alert object to the frontend to be added to the anomaly feed
        alert_payload = {
            "id": alert_id, "status": "New", "rule_name": verdict,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "content": line, "risk_score": risk_score
        }
        requests.post(f"{DASHBOARD_URL}/api/new_alert_entry", json=alert_payload, timeout=1)

    if is_anomaly and risk_score >= 0.78:
        try:
            advice = f"CRITICAL: ({verdict}) | Risk: {risk_score:.2f}. Review for details."
            requests.post(f"{DASHBOARD_URL}/api/new_alert", json={"log": line, "advice": advice, "status": "New"}, timeout=1)
            play_alert_sound()
        except Exception as e:
            log_warning(f"Failed to send alert to dashboard: {e}")

# === (The rest of your script: LogHandler class, watch_journalctl, main block, etc. remains the same) ===
class LogHandler(FileSystemEventHandler):
    def __init__(self, file_path, log_queue):
        super().__init__()
        self.file_path = file_path
        self.log_queue = log_queue
        self._last_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

    def on_modified(self, event):
        if event.src_path == self.file_path:
            try:
                new_size = os.path.getsize(self.file_path)
                if new_size > self._last_size:
                    with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        f.seek(self._last_size)
                        for line in f:
                            if line.strip():
                                self.log_queue.put(('file', os.path.basename(self.file_path), line.strip()))
                                # process_log(os.path.basename(self.file_path), line.strip())
                    self._last_size = new_size
            except FileNotFoundError:
                log_warning(f"File vanished, skipping: {self.file_path}")
                self._last_size = 0
            except Exception as e:
                log_error(f"Error processing modified file {self.file_path}: {e}")

# def watch_journalctl():
#     log_info("Started journalctl monitoring...")
#     process = subprocess.Popen(['journalctl', '-f', '-o', 'cat'],
#                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='ignore')
#     for line in process.stdout:
#         if line.strip():
#             process_log('journalctl', line.strip())

if __name__ == "__main__":
    
    # --- The new processing queue and worker setup ---
    log_processing_queue = queue.Queue()

    def worker():
        """Worker thread that takes logs from the queue and processes them."""
        while True:
            source_type, source_name, line = log_processing_queue.get()
            if line is None: # Sentinel for stopping
                break
            try:
                process_log(source_name, line)
            except Exception as e:
                log_error(f"Error processing log in worker: {e}")
            finally:
                log_processing_queue.task_done()

    # Start a pool of worker threads to handle the ML processing
    num_worker_threads = 2 # You can adjust this number based on your CPU cores
    threads = []
    for i in range(num_worker_threads):
        t = threading.Thread(target=worker)
        t.daemon = True
        t.start()
        threads.append(t)
    
    log_info(f"Started {num_worker_threads} worker threads for log processing.")

    # --- The file and journalctl watchers ---
    # They now put logs into the queue instead of processing them directly.
    observer = Observer()
    for file_path in LOG_FILES:
        if os.path.exists(file_path):
            event_handler = LogHandler(file_path, log_processing_queue)
            observer.schedule(event_handler, os.path.dirname(file_path), recursive=False)
            log_info(f"Watching {file_path}")
        else:
            log_warning(f"❗ File not found (skipped): {file_path}")

    def watch_journalctl_to_queue():
        log_info("🚀 Started journalctl monitoring...")
        process = subprocess.Popen(['journalctl', '-f', '-o', 'cat'],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                   text=True, encoding='utf-8', errors='ignore')
        for line in process.stdout:
            if line.strip():
                log_processing_queue.put(('journalctl', 'journalctl', line.strip()))

    threading.Thread(target=watch_journalctl_to_queue, daemon=True).start()

    observer.start()
    log_info("🚀 Monitoring logs: Press CTRL+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping monitor and workers...")
        observer.stop()
        # Stop worker threads gracefully
        for _ in threads:
            log_processing_queue.put((None, None, None))
    
    observer.join()