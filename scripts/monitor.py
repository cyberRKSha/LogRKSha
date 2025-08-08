# import joblib
# from watchdog.observers import Observer
# from watchdog.events import FileSystemEventHandler
# import subprocess
# import threading
# import time
# import os
# import csv
# from datetime import datetime
# import requests
# import hashlib
# from sentence_transformers import SentenceTransformer
# import json # Ensure this is imported
# import smtplib # Ensure this is imported
# from email.mime.text import MIMEText # Ensure this is imported


# # === Colors helpers ===
# def log_info(msg): print(f"\033[94mℹ️ {msg}\033[0m")
# def log_success(msg): print(f"\033[92m✅ {msg}\033[0m")
# def log_warning(msg): print(f"\033[93m⚠️ {msg}\033[0m")
# def log_error(msg): print(f"\033[91m❗ {msg}\033[0m")
# def log_dim(msg): print(f"\033[90m{msg}\033[0m")

# # === Load embedder & model ===
# embedder = joblib.load("/home/rksha/Documents/Projects/log-anamoly-detector/Linux/model/sentence_embedder.pkl")
# model = joblib.load("/home/rksha/Documents/Projects/log-anamoly-detector/Linux/model/sgd_embedder.pkl")

# # Files & paths
# PENDING_CSV = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux/logs/review.csv"
# prediction_log = '/home/rksha/Documents/Projects/log-anamoly-detector/Linux/logs/prediction.log'
# ALERT_SOUND = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux/logs/alert.wav"
# KNOWN_HASHES_FILE = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux/logs/kwnhashes.txt"
# REAL_LOG_CSV = '/home/rksha/Documents/Projects/log-anamoly-detector/Linux/logs/real_log.csv'
# DASHBOARD_URL = "http://127.0.0.1:8000"
# ALERTS_CONFIG_FILE = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux/scripts/alerts_config.json" # Define path for config

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

# # === Ensure CSV exists ===
# if not os.path.exists(PENDING_CSV):
#     with open(PENDING_CSV, 'w', newline='', encoding='utf-8') as f:
#         csv.writer(f).writerow(['timestamp', 'source', 'content', 'label'])

# def play_alert_sound():
#     try:
#         subprocess.Popen(['paplay', ALERT_SOUND])
#     except Exception as e:
#         log_warning(f"Sound playback failed: {e}")

# def log_to_csv(source, content, label):
#     timestamp = datetime.now().isoformat()
#     with open(PENDING_CSV, 'a', newline='', encoding='utf-8') as f:
#         csv.writer(f).writerow([timestamp, source, content, label])

# def log_prediction(label_str, log_text):
#     timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
#     with open(prediction_log, 'a') as pf:
#         pf.write(f"{timestamp},{label_str},{log_text}\n")

# def send_to_dashboard(log_text, label_str):
#     payload = {"log": log_text, "label": label_str, "timestamp": datetime.now().isoformat()}
#     try:
#         requests.post(f"{DASHBOARD_URL}/api/new_log", json=payload, timeout=1)
#     except Exception as e:
#         log_warning(f"Failed to send to dashboard: {e}")

# # === Start: New Notification Functions ===
# def send_slack_alert(title, log_line, webhook_url):
#     payload = {
#         "text": f"🚨 *{title}*",
#         "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": f"🚨 *{title}*\n*Log Entry:*\n```{log_line}```"}}]
#     }
#     try:
#         requests.post(webhook_url, json=payload, timeout=5)
#         log_success(f"Slack notification sent for: {title}")
#     except Exception as e:
#         log_warning(f"Failed to send Slack alert: {e}")

# def send_email_alert(title, log_line, config):
#     msg = MIMEText(f"An alert was triggered for: {title}\n\nLog Entry:\n{log_line}")
#     msg['Subject'] = f"Log Anomaly Alert: {title}"
#     msg['From'] = config['smtp_user']
#     msg['To'] = config['recipient']
#     try:
#         with smtplib.SMTP(config['smtp_server'], config['smtp_port']) as server:
#             server.starttls()
#             server.login(config['smtp_user'], config['smtp_password'])
#             server.send_message(msg)
#             log_success(f"Email notification sent for: {title}")
#     except Exception as e:
#         log_warning(f"Failed to send email alert: {e}")
# # === End: New Notification Functions ===

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
#     if any(p in line for p in IGNORED_PATTERNS):
#         log_dim(f"⏩ Ignored harmless log in {source}: {line}")
#         return

#     # === NLP embedding prediction ===
#     embedding = embedder.encode([line])
#     pred = model.predict(embedding)[0]
#     label_str = 'anomaly' if pred == 1 else 'normal'

#     if label_str == 'anomaly':
#         log_error(f" Anomaly detected in {source}: {line}")
#     else:
#         log_success(f" Normal in {source}: {line}")

#     log_prediction(label_str, line)
#     send_to_dashboard(line, label_str)

#     if is_new_log_and_save_hash(line):
#         log_to_csv(source, line, label_str)
#     else:
#         if not os.path.exists(REAL_LOG_CSV):
#             with open(REAL_LOG_CSV, 'w', newline='', encoding='utf-8') as f:
#                 csv.writer(f).writerow(['timestamp', 'source', 'content', 'label'])
#         timestamp = datetime.now().isoformat()
#         with open(REAL_LOG_CSV, 'a', newline='', encoding='utf-8') as f:
#             csv.writer(f).writerow([timestamp, source, line, label_str])
#         log_info(f"🔁 Duplicate text → skipped review, added to real_log.csv")

#     # === START: CORRECTED ALERT LOGIC ===
#     # This block now handles all alert logic.
#     if label_str == 'anomaly':
#         # STEP 1: Always send a generic alert to the dashboard for ANY anomaly.
#         try:
#             advice = "Anomaly detected by ML model. Review for details."
#             requests.post(f"{DASHBOARD_URL}/api/new_alert", json={"log": line, "advice": advice}, timeout=1)
#             play_alert_sound() # Play sound for any anomaly
#         except Exception as e:
#             log_warning(f"Failed to send generic alert to dashboard: {e}")

#         # STEP 2: Check for specific keywords to trigger EXTERNAL notifications.
#         for rule in alert_config.get('rules', []):
#             if rule.get('enabled') and rule.get('keyword', '').lower() in line.lower():
#                 # If a source is specified in the rule, it must match
#                 if 'source' in rule and rule.get('source') and rule['source'] != source:
#                     continue # Skip if source doesn't match this rule
                
#                 # If rule matches, trigger external notifications
#                 log_info(f"Matched alert rule: '{rule['name']}'. Triggering notifications.")
#                 notifications = alert_config.get('notifications', {})
#                 if notifications.get('slack', {}).get('enabled'):
#                     send_slack_alert(rule['name'], line, notifications['slack']['webhook_url'])
#                 if notifications.get('email', {}).get('enabled'):
#                     send_email_alert(rule['name'], line, notifications['email'])
                
#                 break # Stop after the first matching rule
#     # === END: CORRECTED ALERT LOGIC ===


# class LogHandler(FileSystemEventHandler):
#     def __init__(self, file_path):
#         super().__init__()
#         self.file_path = file_path
#         self._last_size = os.path.getsize(file_path)

#     def on_modified(self, event):
#         if event.src_path == self.file_path:
#             try:
#                 new_size = os.path.getsize(self.file_path)
#                 if new_size > self._last_size:
#                     with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
#                         f.seek(self._last_size)
#                         for line in f:
#                             if line.strip(): # process only non-empty lines
#                                 process_log(os.path.basename(self.file_path), line.strip())
#                     self._last_size = new_size
#             except FileNotFoundError:
#                 log_warning(f"File vanished, skipping: {self.file_path}")
#                 self._last_size = 0 # Reset size
#             except Exception as e:
#                 log_error(f"Error processing modified file {self.file_path}: {e}")


# def watch_journalctl():
#     log_info("🚀 Started journalctl monitoring...")
#     process = subprocess.Popen(['journalctl', '-f', '-o', 'cat'],
#                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='ignore')
#     for line in process.stdout:
#         if line.strip(): # process only non-empty lines
#             process_log('journalctl', line.strip())

# if __name__ == "__main__":
#     observer = Observer()
#     threading.Thread(target=save_hashes_periodically, daemon=True).start()

#     for file_path in LOG_FILES:
#         if os.path.exists(file_path):
#             observer.schedule(LogHandler(file_path), path=os.path.dirname(file_path), recursive=False)
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
from datetime import datetime
import numpy as np
import json
import hashlib
import requests
import threading
import time
import subprocess
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from sentence_transformers import SentenceTransformer
from drain3 import TemplateMiner
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

# --- Logging Helpers ---
def log_info(msg): print(f"\033[94mℹ️ {msg}\033[0m")
def log_success(msg): print(f"\032[92m✅ {msg}\033[0m")
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
log_success("✅ All models loaded successfully.")

# === Load known hashes ===
if os.path.exists(KNOWN_HASHES_FILE):
    with open(KNOWN_HASHES_FILE, 'r') as f:
        known_hashes = set(line.strip() for line in f)
else:
    known_hashes = set()

# === Helper Functions ===
def insert_log_to_db(source: str, content: str, predicted_label: int):
    try:
        conn = sqlite3.connect(DATABASE_FILE)
        cursor = conn.cursor()
        timestamp = datetime.now().isoformat()
        cursor.execute("""
            INSERT INTO logs (timestamp, source, content, predicted_label, final_label, is_reviewed)
            VALUES (?, ?, ?, ?, ?, 0)
        """, (timestamp, source, content, predicted_label, predicted_label))
        conn.commit()
        conn.close()
    except Exception as e:
        log_error(f"Database write failed: {e}")

def play_alert_sound():
    try:
        subprocess.Popen(['paplay', ALERT_SOUND])
    except Exception as e:
        log_warning(f"Sound playback failed: {e}")

def send_to_dashboard(log_text, label_str, verdict=""):
    try:
        payload = {"log": log_text, "label": label_str, "timestamp": datetime.now().isoformat(), "verdict": verdict}
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

    # --- Step 1: Feature Engineering ---
    embedding = embedder.encode([line])
    cluster = template_miner.add_log_message(line)
    log_template = cluster["template_mined"]

    # --- Step 2: Run Parallel Predictions ---

    # Prediction A: Supervised Model (Your original model)
    # This model uses ONLY the sentence embedding.
    supervised_pred = supervised_model.predict(embedding)[0]

    # Prediction B: Unsupervised Autoencoder (for novelty detection)
    # This model also uses ONLY the sentence embedding.
    reconstruction = unsupervised_model.predict(embedding, verbose=0)
    reconstruction_loss = tf.keras.losses.mae(reconstruction, embedding)[0]
    unsupervised_pred = -1 if reconstruction_loss > unsupervised_threshold else 1

    # --- Step 3: Combine Results for Final Verdict ---
    verdict = "Normal"
    is_anomaly = False
    if supervised_pred == 1:
        verdict = "Known Anomaly (Supervised)"
        is_anomaly = True
    elif unsupervised_pred == -1:
        verdict = "Novelty Detected (Unsupervised)"
        is_anomaly = True

    log_info(f"Verdict: [{verdict}] | Loss: {reconstruction_loss:.4f} | Log: {line}")

    # --- Step 4: Act on the Verdict ---
    label_str = 'anomaly' if is_anomaly else 'normal'
    send_to_dashboard(line, label_str, verdict)

    if is_new_log_and_save_hash(line):
        insert_log_to_db(source, line, int(is_anomaly))

    if is_anomaly:
        try:
            advice = f"Anomaly detected by ML model ({verdict}). Review for details."
            requests.post(f"{DASHBOARD_URL}/api/new_alert", json={"log": line, "advice": advice}, timeout=1)
            play_alert_sound()
        except Exception as e:
            log_warning(f"Failed to send alert to dashboard: {e}")

# === (The rest of your script: LogHandler class, watch_journalctl, main block, etc. remains the same) ===
class LogHandler(FileSystemEventHandler):
    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path
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
                                process_log(os.path.basename(self.file_path), line.strip())
                    self._last_size = new_size
            except FileNotFoundError:
                log_warning(f"File vanished, skipping: {self.file_path}")
                self._last_size = 0
            except Exception as e:
                log_error(f"Error processing modified file {self.file_path}: {e}")

def watch_journalctl():
    log_info("🚀 Started journalctl monitoring...")
    process = subprocess.Popen(['journalctl', '-f', '-o', 'cat'],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='ignore')
    for line in process.stdout:
        if line.strip():
            process_log('journalctl', line.strip())

if __name__ == "__main__":
    observer = Observer()
    # threading.Thread(target=save_hashes_periodically, daemon=True).start() # Optional

    for file_path in LOG_FILES:
        if os.path.exists(file_path):
            event_handler = LogHandler(file_path)
            observer.schedule(event_handler, os.path.dirname(file_path), recursive=False)
            log_info(f"📄 Watching {file_path}")
        else:
            log_warning(f"❗ File not found (skipped): {file_path}")

    threading.Thread(target=watch_journalctl, daemon=True).start()

    observer.start()
    log_info("🚀 Monitoring logs: Press CTRL+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\n🛑 Stopped monitoring.")

    observer.join()