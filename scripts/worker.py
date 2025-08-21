import os
import re
import sys
import dill
import pika
import json
import time
import joblib
import hashlib
import sqlite3
import requests
import subprocess
import numpy as np
import tensorflow as tf
from tensorflow.keras.preprocessing.sequence import pad_sequences
from datetime import datetime, timezone
from sklearn.pipeline import make_pipeline
from sentence_transformers import SentenceTransformer

# --- Configuration and Model Loading ---
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATABASE_FILE = os.path.join(BASE_DIR, "log_database.db")
DASHBOARD_URL = "http://127.0.0.1:8000"
RABBITMQ_HOST = 'localhost'
LOG_QUEUE_NAME = 'log_queue'

IGNORED_PATTERNS = [
    "ACPI group/action undefined: button/",
    "ACPI group/action undefined: video/",
]

# --- Logging Helpers ---
def log_info(msg): print(f"\033[94mℹ️ {msg}\033[0m")
def log_success(msg): print(f"\033[92m✅ {msg}\033[0m")
def log_warning(msg): print(f"\033[93m⚠️ {msg}\033[0m")
def log_error(msg): print(f"\033[91m❗ {msg}\033[0m")

# --- Load ALL Models at Startup ---
log_info("Worker starting up. Loading models...")
EMBEDDER_PATH = os.path.join(BASE_DIR, "model/sentence_embedder.pkl")
SUPERVISED_MODEL_PATH = os.path.join(BASE_DIR, "model/sgd_embedder.pkl")
AUTOENCODER_PATH = os.path.join(BASE_DIR, "model/autoencoder_model.keras")
THRESHOLD_PATH = os.path.join(BASE_DIR, "model/autoencoder_threshold.json")
EXPLAINER_PATH = os.path.join(BASE_DIR, "model/lime_explainer.pkl")
KNOWN_HASHES_FILE = os.path.join(BASE_DIR, "logs/kwnhashes.txt")
ALERT_SOUND = os.path.join(BASE_DIR, "logs/alert.wav")
STATUS_FILE = os.path.join(BASE_DIR, "monitoring_status.json")
LSTM_MODEL_PATH = os.path.join(BASE_DIR, "model/lstm_classifier_model.keras")

embedder = SentenceTransformer(str(EMBEDDER_PATH))
supervised_model = joblib.load(SUPERVISED_MODEL_PATH)
unsupervised_model = tf.keras.models.load_model(AUTOENCODER_PATH)
with open(THRESHOLD_PATH, 'r') as f:
    unsupervised_threshold = json.load(f)['threshold']
with open(EXPLAINER_PATH, 'rb') as f:
    explainer = dill.load(f)
lstm_model = tf.keras.models.load_model(LSTM_MODEL_PATH)
log_success("✅ All models loaded successfully.")

if os.path.exists(KNOWN_HASHES_FILE):
    with open(KNOWN_HASHES_FILE, 'r') as f:
        known_hashes = set(line.strip() for line in f)
else:
    known_hashes = set()

active_sessions = {}
SEQUENCE_LEN = 20

# --- All Processing Logic (moved from monitor.py) ---

def parse_timestamp_from_log(log_line: str) -> str:

    match = re.search(
        r"^(?P<month>\w{3})\s+(?P<day>\d{1,2})\s+(?P<time>\d{2}:\d{2}:\d{2})",
        log_line
    )
    if not match:
        # If no timestamp is found, fallback to the current time
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds")

    log_time_data = match.groupdict()
    current_year = datetime.now().year

    datetime_str = f"{log_time_data['month']} {log_time_data['day']} {current_year} {log_time_data['time']}"
    
    try:
        # Parse the string into a datetime object
        dt_obj = datetime.strptime(datetime_str, "%b %d %Y %H:%M:%S")
        # Convert to UTC and format as ISO string
        return dt_obj.astimezone(timezone.utc).isoformat(timespec="milliseconds")
    except ValueError:
        # Fallback if parsing fails for any reason
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds")

def is_monitoring_active():
    """Checks the status file. Defaults to True if file not found."""
    if not os.path.exists(STATUS_FILE):
        return True
    try:
        with open(STATUS_FILE, 'r') as f:
            return json.load(f).get("is_active", True)
    except (json.JSONDecodeError, IOError):
        return True # Default to active on error

def play_alert_sound():
    try:
        subprocess.Popen(['paplay', ALERT_SOUND])
    except Exception as e:
        log_warning(f"Sound playback failed: {e}")

def insert_log_to_db(source: str, content: str, p_label: int, risk: float, seq_risk: float, reviewed: int = 0, explanation: str = ""):
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        timestamp = datetime.now().isoformat(timespec="milliseconds")
        cursor.execute("""
            INSERT INTO logs (timestamp, source, content, predicted_label, final_label, is_reviewed, risk_score, sequence_risk, explanation)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (timestamp, source, content, p_label, p_label, reviewed, risk, seq_risk, explanation))
        new_log_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return new_log_id
    
    except Exception as e:
        log_error(f"Database write failed: {e}")

def send_to_dashboard(payload: dict):
    try:    
        # payload = {
        #     # "log": log_text,
        #     # "label": label_str,
        #     "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        #     # "verdict": verdict,
        #     # "risk_score": risk_score,
        # }
        # payload["timestamp"] = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        requests.post(f"{DASHBOARD_URL}/api/new_log", json=payload, timeout=2)

    except TypeError as e:
        log_error(f"Failed to serialize payload to JSON: {e}. Payload: {payload}")
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

def get_session_key(log_line: str) -> str | None:
    """
    Extracts a session key from a log line in a prioritized order.
    1. IP Address
    2. Username
    3. Process ID (PID)
    """
    # 1. Try to find an IP address
    ip_match = re.search(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", log_line)
    if ip_match:
        return f"ip_{ip_match.group(0)}"

    # 2. If no IP, try to find a common username pattern
    user_match = re.search(r"\buser[= ](\w+)", log_line) # e.g., "user=root" or "user root"
    if user_match:
        return f"user_{user_match.group(1)}"
        
    # 3. If no user, try to find a Process ID (PID)
    pid_match = re.search(r"\[(\d+)\]:", log_line) # e.g., "sshd[12345]:"
    if pid_match:
        return f"pid_{pid_match.group(1)}"
        
    return None

def update_and_predict_sequence(log_line, embedding):
    """
    Manages active log sequences and predicts anomaly score using the LSTM model.
    """
    session_key = get_session_key(log_line)
    if not session_key:
        return 0.0 # Cannot perform sequence analysis without a session key (IP)

    now = datetime.now()
    
    # Get the current session for this IP or create a new one
    session = active_sessions.get(session_key, {'embeddings': [], 'last_seen': now})
    
    # Add the new log's embedding to the sequence
    session['embeddings'].append(embedding[0]) # embedding is shape (1, 384), we want (384,)
    session['last_seen'] = now
    
    # Keep the sequence at a maximum length
    if len(session['embeddings']) > SEQUENCE_LEN:
        session['embeddings'].pop(0)
    
    active_sessions[session_key] = session
    
    # Prepare the sequence for the model
    sequence_for_model = [session['embeddings']] # Model expects a batch
    padded_sequence = pad_sequences(sequence_for_model, maxlen=SEQUENCE_LEN, dtype='float32', padding='pre')
    
    # Predict with the LSTM model
    sequence_risk_score = lstm_model.predict(padded_sequence, verbose=0)[0][0]

    # --- Cleanup: Periodically remove old, inactive sessions to save memory ---
    # (This is a simple cleanup, a more robust version might use a separate thread)
    if np.random.rand() < 0.1: # Run cleanup randomly on 10% of calls
        inactive_ips = [
            k for k, v in active_sessions.items() 
            if (now - v['last_seen']).total_seconds() > 300 # 5-minute timeout
        ]
        for k in inactive_ips:
            del active_sessions[k]
            
    return float(sequence_risk_score)

def process_log(source, line):

    if any(p in line for p in IGNORED_PATTERNS):
        return
    
    h = hashlib.sha256(line.encode('utf-8')).hexdigest()
    if h in known_hashes:
        log_info(f"Skipping duplicate log: {line}")
        return # Exit the function early

    # If it's new, add it to our known hashes and proceed with processing.
    known_hashes.add(h)
    with open(KNOWN_HASHES_FILE, 'a') as f:
        f.write(h + '\n')

    # This is the full, final version of your processing logic
    embedding = embedder.encode([line])
    supervised_pred = supervised_model.predict(embedding)[0]
    reconstruction = unsupervised_model.predict(embedding, verbose=0)
    reconstruction_loss = tf.keras.losses.mae(reconstruction, embedding)[0].numpy()
    risk_score = float(min(1.0, reconstruction_loss / unsupervised_threshold))
    unsupervised_pred = 1 if reconstruction_loss > unsupervised_threshold else 0
    sequence_risk = update_and_predict_sequence(line, embedding)
    
    verdict = "Normal"
    is_anomaly = False

    if supervised_pred == 1:
        is_anomaly = True
        verdict = "Supervised"

    elif sequence_risk > 0.9: # High-confidence sequence anomaly
        is_anomaly = True
        verdict = f"Malicious Sequence Detected (Score: {sequence_risk:.2f})"
        risk_score = max(risk_score, sequence_risk) # Elevate the risk score

    elif unsupervised_pred == 1:
        is_anomaly = True
        verdict = "Novelty Detected"

    if not is_anomaly: 
        risk_score = 0.0
    
    label_str = 'anomaly' if is_anomaly else 'normal'

    original_timestamp = parse_timestamp_from_log(line)
    dashboard_payload = {
        "log": line,
        "label": label_str,
        "verdict": verdict,
        "risk_score": risk_score,
        "is_alert": False, # Default to false
        "timestamp": original_timestamp,
        "sequence_risk": sequence_risk
    }

    
    # is_unique_for_review = is_new_log_and_save_hash(line)
    # log_is_reviewed_status = 0 if is_unique_for_review else 1
    new_log_id = insert_log_to_db(source, line, int(is_anomaly), risk_score, sequence_risk, 0, "")
    
    if is_anomaly:
        try:
            conn = sqlite3.connect(DATABASE_FILE)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO alerts (log_id, timestamp, rule_name, status) VALUES (?, ?, ?, 'New')",
                         (new_log_id, datetime.now(timezone.utc).isoformat(), verdict))
            alert_id = cursor.lastrowid
            conn.commit()
            conn.close()

            dashboard_payload["is_alert"] = True
            dashboard_payload["alert_info"] = {
            "id": alert_id, "status": "New", "rule_name": verdict,
            "timestamp": original_timestamp,
            "content": line, "risk_score": risk_score
            }
            # requests.post(f"{DASHBOARD_URL}/api/new_alert_entry", json=dashboard_payload, timeout=1)

            if risk_score >= 0.75:
                advice = f"({verdict}) | Risk: {risk_score:.2f}"
                requests.post(f"{DASHBOARD_URL}/api/new_alert", json={"log": line, "advice": advice, "status": "New", "id": alert_id}, timeout=1)
                play_alert_sound()
        except Exception as e:
            log_warning(f"Failed to send alert to dashboard: {e}")

    log_info(f"Verdict: [{verdict}] | RiskScore: {risk_score} | Loss: {reconstruction_loss:.4f} | Log: {line}")
    # send_to_dashboard(line, label_str, verdict, risk_score)
    send_to_dashboard(dashboard_payload)

# --- Main Worker Loop ---
def main():
    while True:
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
            channel = connection.channel()
            channel.queue_declare(queue=LOG_QUEUE_NAME, durable=True)

            def callback(ch, method, properties, body):
                try:
                    message = json.loads(body)
                    process_log(message.get('source'), message.get('content'))
                except Exception as e:
                    log_warning(f"Error processing message: {e}")
                finally:
                    ch.basic_ack(delivery_tag=method.delivery_tag)

            channel.basic_qos(prefetch_count=1)
            # channel.basic_consume(queue=LOG_QUEUE_NAME, on_message_callback=callback)
            log_success('Worker connected to RabbitMQ.')
            log_info(' [*] Worker is waiting for logs. To exit press CTRL+C')
            # channel.start_consuming()
            while True:
                if is_monitoring_active():
                    # Get one message from the queue (if available)
                    method_frame, _, body = channel.basic_get(queue=LOG_QUEUE_NAME)
                    if method_frame:
                        # If a message was received, process it
                        callback(channel, method_frame, None, body)
                    else:
                        # If the queue is empty, wait a bit before checking again
                        time.sleep(1)
                else:
                    # If monitoring is paused, sleep for longer before checking the status again
                    time.sleep(5)

        except (pika.exceptions.StreamLostError, pika.exceptions.AMQPConnectionError) as e:
                # 3. Catch connection errors and wait before retrying
                log_error(f"❗ Connection to RabbitMQ lost: {e}. Retrying in 5 seconds...")
                time.sleep(5)

        except KeyboardInterrupt:
            print('Interrupted')
            break # Exit the outer loop on Ctrl+C

        except Exception as e:
            # Catch any other unexpected errors
            log_error(f"❗ An unexpected error occurred: {e}. Retrying in 10 seconds...")
            time.sleep(10)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Interrupted')
        sys.exit(0)




























































































































































































































































































































# def insert_logs_batch(log_batch):
#     """Inserts a batch of logs into the database."""
#     conn = sqlite3.connect(DATABASE_FILE, timeout=10)
#     cursor = conn.cursor()
#     # executemany is much faster for bulk inserts
#     cursor.executemany("""
#         INSERT INTO logs (timestamp, source, content, predicted_label, final_label, is_reviewed, risk_score, explanation)
#         VALUES (?, ?, ?, ?, ?, ?, ?, ?)
#     """, log_batch)
#     conn.commit()
#     conn.close()

# def create_alerts_batch(alert_batch):
#     """Inserts a batch of alerts into the database."""
#     conn = sqlite3.connect(DATABASE_FILE, timeout=10)
#     cursor = conn.cursor()
#     cursor.executemany("""
#         INSERT INTO alerts (log_id, timestamp, rule_name, status)
#         VALUES (?, ?, ?, 'New')
#     """, alert_batch)
#     conn.commit()
#     conn.close()

# # The main processing logic, now for a BATCH of logs
# def process_batch(batch):
#     if not batch:
#         return

#     log_info(f"Processing a batch of {len(batch)} logs...")
    
#     # 1. Prepare batch data
#     log_contents = [item['content'] for item in batch]
#     log_sources = [item['source'] for item in batch]

#     # 2. Run ML models ONCE on the entire batch
#     embeddings = embedder.encode(log_contents, batch_size=len(batch))
#     supervised_preds = supervised_model.predict(embeddings)
#     reconstructions = unsupervised_model.predict(embeddings, verbose=0)
#     reconstruction_losses = tf.keras.losses.mae(reconstructions, embeddings).numpy()
    
#     # 3. Process results for each log in the batch
#     logs_to_db = []
#     alerts_to_db = []
    
#     for i in range(len(batch)):
#         risk_score = min(1.0, reconstruction_losses[i] / unsupervised_threshold)
#         unsupervised_pred = 1 if reconstruction_losses[i] > unsupervised_threshold else 0
        
#         verdict = "Normal"
#         is_anomaly = False
#         if supervised_preds[i] == 1:
#             is_anomaly, verdict = True, "Known Anomaly (Supervised)"
#         elif unsupervised_pred == 1:
#             is_anomaly, verdict = True, "Novelty Detected (Unsupervised)"
        
#         if not is_anomaly: risk_score = 0.0
#         label_str = 'anomaly' if is_anomaly else 'normal'

#         # Send individual logs to the dashboard in real-time
#         send_to_dashboard(log_contents[i], label_str, verdict, risk_score)

#         # Prepare data for bulk database insert
#         logs_to_db.append((
#             datetime.now(timezone.utc).isoformat(), log_sources[i], log_contents[i],
#             int(is_anomaly), int(is_anomaly), 0, risk_score, ""
#         ))
        
#     # 4. Insert logs into DB to get their IDs
#     # This part is slower as we need IDs back. We'll do it one by one for now.
#     # A more advanced solution would use a different DB that supports returning IDs from bulk inserts.
#     for i in range(len(logs_to_db)):
#         new_log_id = insert_log_to_db(*logs_to_db[i][1:]) # Pass tuple elements
        
#         # Check if this log should generate an alert
#         is_anomaly = logs_to_db[i][3] == 1
#         risk_score = logs_to_db[i][6]
#         verdict = "Anomaly Detected" # Simplified
#         if is_anomaly and risk_score >= 0.7:
#              alerts_to_db.append((new_log_id, datetime.now(timezone.utc).isoformat(), verdict))

#     # 5. Bulk insert alerts
#     if alerts_to_db:
#         create_alerts_batch(alerts_to_db)

#     log_success(f"Finished processing batch of {len(batch)} logs.")


# # --- Main Worker Loop (Now batch-oriented) ---
# def main():
#     connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
#     channel = connection.channel()
#     channel.queue_declare(queue=LOG_QUEUE_NAME, durable=True)
#     channel.basic_qos(prefetch_count=64) # Fetch up to 64 messages at once

#     log_info(' [*] Worker is waiting for logs. To exit press CTRL+C')

#     while True:
#         batch = []
#         batch_size = 32 # Process logs in batches of 32
        
#         # Try to gather a batch of logs for up to 2 seconds
#         start_time = time.time()
#         while len(batch) < batch_size and (time.time() - start_time) < 2:
#             method_frame, header_frame, body = channel.basic_get(queue=LOG_QUEUE_NAME)
#             if method_frame:
#                 batch.append(json.loads(body))
#                 channel.basic_ack(method_frame.delivery_tag)
#             else:
#                 break # No more messages in the queue
        
#         if batch:
#             process_batch(batch)
#         else:
#             time.sleep(1) # Wait a bit if the queue is empty


# if __name__ == '__main__':
#     try:
#         main()
#     except KeyboardInterrupt:
#         print('Interrupted')
#         sys.exit(0)


