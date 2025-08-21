# import os
# import joblib
# import sqlite3
# from datetime import datetime, timezone
# import numpy as np
# import json
# import hashlib
# import requests
# import threading
# import time
# import subprocess
# import dill
# import queue
# import threading
# from watchdog.observers import Observer
# from watchdog.events import FileSystemEventHandler
# from sentence_transformers import SentenceTransformer
# from drain3 import TemplateMiner
# # from sklearn.pipeline import make_pipeline
# import tensorflow as tf

# # --- Configuration ---
# BASE_DIR = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux"
# DATABASE_FILE = os.path.join(BASE_DIR, "log_database.db")
# # Models
# EMBEDDER_PATH = os.path.join(BASE_DIR, "model/sentence_embedder.pkl")
# DRAIN_PATH = os.path.join(BASE_DIR, "model/template_miner.pkl")
# # This is your ORIGINAL supervised model
# SUPERVISED_MODEL_PATH = os.path.join(BASE_DIR, "model/sgd_embedder.pkl")
# # This is your NEW unsupervised model
# AUTOENCODER_PATH = os.path.join(BASE_DIR, "model/autoencoder_model.keras")
# THRESHOLD_PATH = os.path.join(BASE_DIR, "model/autoencoder_threshold.json")
# # Other Configs
# DASHBOARD_URL = "http://127.0.0.1:8000"
# KNOWN_HASHES_FILE = os.path.join(BASE_DIR, "logs/kwnhashes.txt")
# ALERT_SOUND = os.path.join(BASE_DIR, "logs/alert.wav")
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
# # EXPLAINER_PATH = os.path.join(BASE_DIR, "model/lime_explainer.pkl")

# # --- Logging Helpers ---
# def log_info(msg): print(f"\033[94mℹ️ {msg}\033[0m")
# def log_success(msg): print(f"\033[92m✅ {msg}\033[0m")
# def log_error(msg): print(f"\033[91m❗ {msg}\033[0m")
# def log_dim(msg): print(f"\033[90m{msg}\033[0m")
# def log_warning(msg): print(f"\033[93m⚠️ {msg}\033[0m")

# # === Load ALL Models at Startup ===
# log_info("Loading all models for hybrid analysis...")
# embedder = joblib.load(EMBEDDER_PATH)
# template_miner = joblib.load(DRAIN_PATH)
# supervised_model = joblib.load(SUPERVISED_MODEL_PATH)
# unsupervised_model = tf.keras.models.load_model(AUTOENCODER_PATH)
# with open(THRESHOLD_PATH, 'r') as f:
#     unsupervised_threshold = json.load(f)['threshold']
# log_success("✅ All models loaded successfully.")

# # === Load known hashes ===
# if os.path.exists(KNOWN_HASHES_FILE):
#     with open(KNOWN_HASHES_FILE, 'r') as f:
#         known_hashes = set(line.strip() for line in f)
# else:
#     known_hashes = set()

# # === Helper Functions ===
# def insert_log_to_db(source: str, content: str, predicted_label: int, risk_score: float, is_reviewed: int = 0, explanation: str = ""):
#     """Inserts a new log with its risk score into the database."""
#     try:
#         conn = sqlite3.connect(DATABASE_FILE)
#         cursor = conn.cursor()
#         timestamp = datetime.now().isoformat(timespec='milliseconds')
        
#         cursor.execute("""
#             INSERT INTO logs (timestamp, source, content, predicted_label, final_label, is_reviewed, risk_score, explanation)
#             VALUES (?, ?, ?, ?, ?, ?, ?, ?)
#         """, (timestamp, source, content, predicted_label, predicted_label, is_reviewed, risk_score, explanation))
        
#         new_log_id = cursor.lastrowid
#         conn.commit()
#         conn.close()
#         return new_log_id
    
#     except Exception as e:
#         log_error(f"Database write failed: {e}")


# def play_alert_sound():
#     try:
#         subprocess.Popen(['paplay', ALERT_SOUND])
#     except Exception as e:
#         log_warning(f"Sound playback failed: {e}")

# def send_to_dashboard(log_text, label_str, verdict="", risk_score=0.0):
#     """Sends log data, including the risk score, to the dashboard via WebSocket."""
#     try:
#         payload = {
#             "log": log_text,
#             "label": label_str,
#             "timestamp": datetime.now(timezone.utc).isoformat(timespec='milliseconds'),
#             "verdict": verdict,
#             "risk_score": risk_score, # Add the risk score to the payload
#         }
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

# # === REVISED process_log FUNCTION FOR HYBRID ANALYSIS ===
# def process_log(source, line):
#     if any(p in line for p in IGNORED_PATTERNS):
#         return

#     embedding = embedder.encode([line])
#     supervised_pred = supervised_model.predict(embedding)[0]
#     reconstruction = unsupervised_model.predict(embedding, verbose=0)
#     reconstruction_loss = tf.keras.losses.mae(reconstruction, embedding)[0].numpy()
#     risk_score = min(1.0, reconstruction_loss / unsupervised_threshold)
#     unsupervised_pred = 1 if reconstruction_loss > unsupervised_threshold else 0

#     verdict = "Normal"
#     is_anomaly = False
#     if supervised_pred == 1:
#         verdict = "Known Anomaly (Supervised)"
#         is_anomaly = True

#     elif unsupervised_pred == 1:
#         verdict = "Novelty Detected (Unsupervised)"
#         is_anomaly = True

#     if not is_anomaly:
#         risk_score = 0.0

#     log_info(f"Verdict: [{verdict}] | RiskScore: {risk_score} | Loss: {reconstruction_loss:.4f} | Log: {line}")

#     label_str = 'anomaly' if is_anomaly else 'normal'
#     send_to_dashboard(line, label_str, verdict, risk_score)

#     # if is_new_log_and_save_hash(line):
#     #     insert_log_to_db(source, line, int(is_anomaly), risk_score)

#     is_unique_for_review = is_new_log_and_save_hash(line)
#     log_is_reviewed_status = 0 if is_unique_for_review else 1
#     new_log_id = insert_log_to_db(source, line, int(is_anomaly), risk_score, log_is_reviewed_status, "")


#     if is_anomaly:
#         # Create a formal alert in the DB that can be managed
#         conn = sqlite3.connect(DATABASE_FILE)
#         cursor = conn.cursor()
#         cursor.execute("""
#             INSERT INTO alerts (log_id, timestamp, rule_name, status)
#             VALUES (?, ?, ?, 'New')
#         """, (new_log_id, datetime.now(timezone.utc).isoformat(), verdict))
#         alert_id = cursor.lastrowid # Get the new alert's ID
#         conn.commit()
#         conn.close()

#         # Send a rich alert object to the frontend to be added to the anomaly feed
#         alert_payload = {
#             "id": alert_id, "status": "New", "rule_name": verdict,
#             "timestamp": datetime.now(timezone.utc).isoformat(),
#             "content": line, "risk_score": risk_score
#         }
#         requests.post(f"{DASHBOARD_URL}/api/new_alert_entry", json=alert_payload, timeout=1)

#     if is_anomaly and risk_score >= 0.78:
#         try:
#             advice = f"CRITICAL: ({verdict}) | Risk: {risk_score:.2f}. Review for details."
#             requests.post(f"{DASHBOARD_URL}/api/new_alert", json={"log": line, "advice": advice, "status": "New"}, timeout=1)
#             play_alert_sound()
#         except Exception as e:
#             log_warning(f"Failed to send alert to dashboard: {e}")

# # === (The rest of your script: LogHandler class, watch_journalctl, main block, etc. remains the same) ===
# class LogHandler(FileSystemEventHandler):
#     def __init__(self, file_path, log_queue):
#         super().__init__()
#         self.file_path = file_path
#         self.log_queue = log_queue
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
#                                 self.log_queue.put(('file', os.path.basename(self.file_path), line.strip()))
#                                 # process_log(os.path.basename(self.file_path), line.strip())
#                     self._last_size = new_size
#             except FileNotFoundError:
#                 log_warning(f"File vanished, skipping: {self.file_path}")
#                 self._last_size = 0
#             except Exception as e:
#                 log_error(f"Error processing modified file {self.file_path}: {e}")

# if __name__ == "__main__":
    
#     # --- The new processing queue and worker setup ---
#     log_processing_queue = queue.Queue()

#     def worker():
#         """Worker thread that takes logs from the queue and processes them."""
#         while True:
#             source_type, source_name, line = log_processing_queue.get()
#             if line is None: # Sentinel for stopping
#                 break
#             try:
#                 process_log(source_name, line)
#             except Exception as e:
#                 log_error(f"Error processing log in worker: {e}")
#             finally:
#                 log_processing_queue.task_done()

#     # Start a pool of worker threads to handle the ML processing
#     num_worker_threads = 2 # You can adjust this number based on your CPU cores
#     threads = []
#     for i in range(num_worker_threads):
#         t = threading.Thread(target=worker)
#         t.daemon = True
#         t.start()
#         threads.append(t)
    
#     log_info(f"Started {num_worker_threads} worker threads for log processing.")

#     # --- The file and journalctl watchers ---
#     # They now put logs into the queue instead of processing them directly.
#     observer = Observer()
#     for file_path in LOG_FILES:
#         if os.path.exists(file_path):
#             event_handler = LogHandler(file_path, log_processing_queue)
#             observer.schedule(event_handler, os.path.dirname(file_path), recursive=False)
#             log_info(f"Watching {file_path}")
#         else:
#             log_warning(f"❗ File not found (skipped): {file_path}")

#     def watch_journalctl_to_queue():
#         log_info("🚀 Started journalctl monitoring...")
#         process = subprocess.Popen(['journalctl', '-f', '-o', 'cat'],
#                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
#                                    text=True, encoding='utf-8', errors='ignore')
#         for line in process.stdout:
#             if line.strip():
#                 log_processing_queue.put(('journalctl', 'journalctl', line.strip()))

#     threading.Thread(target=watch_journalctl_to_queue, daemon=True).start()

#     observer.start()
#     log_info("🚀 Monitoring logs: Press CTRL+C to stop.")

#     try:
#         while True:
#             time.sleep(1)
#     except KeyboardInterrupt:
#         print("\n🛑 Stopping monitor and workers...")
#         observer.stop()
#         # Stop worker threads gracefully
#         for _ in threads:
#             log_processing_queue.put((None, None, None))
    
#     observer.join()
































































































































































































import os
import pika
import json
import time
import queue
import threading
import subprocess
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import threading # Use threading for journalctl

# --- Configuration ---
LOG_FILES = [
    "/var/log/mp-auth.log",
    "/var/log/kern.log",
    "/var/log/mp-kern.log",
    "/var/log/pacman.log",
    "/var/log/Xorg.0.log",
    "simulation/auth.log",
    "simulation/kern.log",
    "simulation/nginx.log",
    "simulation/pacman.log",
    "simulation/system.log",
    "simulation/Xorg.0.log",
]
RABBITMQ_HOST = 'localhost'
LOG_QUEUE_NAME = 'log_queue'

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
STATUS_FILE = os.path.join(BASE_DIR, "monitoring_status.json")

# --- Logging Helpers ---
def log_info(msg): print(f"\033[94mℹ️ {msg}\033[0m")
def log_warning(msg): print(f"\033[93m⚠️ {msg}\033[0m")
def log_error(msg): print(f"\033[91m❗ {msg}\033[0m")


# def publish_log(channel, source, line):
#     """Publishes a log message to the RabbitMQ queue."""
#     message = {
#         'source': source,
#         'content': line
#     }
#     try:
#         channel.basic_publish(
#             exchange='',
#             routing_key=LOG_QUEUE_NAME,
#             body=json.dumps(message),
#             properties=pika.BasicProperties(delivery_mode=2)
#         )
#     except Exception as e:
#         log_warning(f"Failed to publish message to RabbitMQ: {e}")

def is_monitoring_active():
    """Checks the status file. Defaults to True if file not found."""
    if not os.path.exists(STATUS_FILE):
        return True
    try:
        with open(STATUS_FILE, 'r') as f:
            return json.load(f).get("is_active", True)
    except (json.JSONDecodeError, IOError):
        return True # Default to active on error
    
def rabbitmq_publisher(log_queue: queue.Queue):

    connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
    channel = connection.channel()
    channel.queue_declare(queue=LOG_QUEUE_NAME, durable=True)
    log_info(" Publisher thread connected to RabbitMQ.")

    while True:
        try:
            # Get a log from the thread-safe in-memory queue
            log_message = log_queue.get()
            if log_message is None: # Sentinel to stop the thread
                break
            
            # Safely publish the message
            channel.basic_publish(
                exchange='',
                routing_key=LOG_QUEUE_NAME,
                body=json.dumps(log_message),
                properties=pika.BasicProperties(delivery_mode=2)
            )
            log_queue.task_done()
        except pika.exceptions.StreamLostError:
            log_error("RabbitMQ connection lost. Reconnecting...")
            time.sleep(5)
            # Re-establish connection
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
            channel = connection.channel()
            channel.queue_declare(queue=LOG_QUEUE_NAME, durable=True)
        except pika.exceptions.AMQPConnectionError:
            log_error("Could not connect to RabbitMQ. Retrying in 5 seconds...")
            time.sleep(5)
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
            channel = connection.channel()
            channel.queue_declare(queue=LOG_QUEUE_NAME, durable=True)
        except Exception as e:
            log_error(f"Error in publisher thread: {e}")

    connection.close()
    log_info("Publisher thread shut down.")


class LogHandler(FileSystemEventHandler):
    def __init__(self, file_path, log_queue):
        super().__init__()
        self.file_path = file_path
        # self.channel = channel
        self.log_queue = log_queue
        self._last_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

    def on_modified(self, event):
        if event.src_path == self.file_path and is_monitoring_active():
            try:
                new_size = os.path.getsize(self.file_path)
                if new_size > self._last_size:
                    with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        f.seek(self._last_size)
                        for line in f:
                            if line.strip():
                                # publish_log(self.channel, os.path.basename(self.file_path), line.strip())
                                self.log_queue.put({'source': os.path.basename(self.file_path), 'content': line.strip()})
                    self._last_size = new_size
            except FileNotFoundError:
                log_warning(f"File vanished- LogHandler: {self.file_path}")
                self._last_size = 0
            except Exception as e:
                log_error(f"Error processing modified file {self.file_path}: {e}")


def watch_journalctl(log_queue):
    log_info("🚀 Started journalctl monitoring...")
    process = subprocess.Popen(['journalctl', '-f', '-o', 'cat'],
                               stdout=subprocess.PIPE, text=True, encoding='utf-8', errors='ignore')
    for line in process.stdout:
        if line.strip() and is_monitoring_active():
            # publish_log(channel, 'journalctl', line.strip())
            log_queue.put({'source': 'journalctl', 'content': line.strip()})


if __name__ == "__main__":
    # try:
    #     connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
    #     channel = connection.channel()
    #     channel.queue_declare(queue=LOG_QUEUE_NAME, durable=True)
    #     log_info("RabbitMQ connection successful.")
    # except Exception as e:
    #     log_warning(f"Could not connect to RabbitMQ: {e}. Please ensure the server is running.")
    #     exit()

    log_queue = queue.Queue()

    # Start the single, dedicated publisher thread
    publisher_thread = threading.Thread(target=rabbitmq_publisher, args=(log_queue,), daemon=True)
    publisher_thread.start()

    observer = Observer()
    for file_path in LOG_FILES:
        if os.path.exists(file_path):
            observer.schedule(LogHandler(file_path, log_queue), os.path.dirname(file_path), recursive=False)
            log_info(f"Watching {file_path}")
        else:
            log_warning(f"File not found (skipped): {file_path}")

    journal_thread = threading.Thread(target=watch_journalctl, args=(log_queue,), daemon=True)
    journal_thread.start()
    
    observer.start()
    log_info("Monitoring logs and publishing to queue. Press CTRL+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping monitor.")
        observer.stop()
        log_queue.put(None)
    
    observer.join()
    # connection.close()
    publisher_thread.join()
