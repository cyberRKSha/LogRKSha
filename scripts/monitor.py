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
# ALERTS_CONFIG_FILE = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux/alerts_config.json"

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

# critical_alerts = {
#     "Failed password": "Possible brute-force attack detected. Consider blocking offending IP.",
#     "Invalid user": "Possible scanning detected. Review firewall rules.",
#     "Kernel panic": "❗ CRITICAL: Kernel panic detected! Immediate attention required.",
#     "segfault": "⚠️ Warning: Application crashed with segmentation fault.",
#     "command not allowed": "🚨 Possible sudo misuse attempt detected.",
#     "sudo": "Review sudoers config.",
#     "su": "Review sudoers config."
# }

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

# def alert(file_path):
#     try:
#         subprocess.Popen(['paplay', file_path])
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
#     payload = {"log": log_text, "label": label_str}
#     try:
#         requests.post(f"{DASHBOARD_URL}/api/new_log",
#                       json=payload, timeout=1)
#     except Exception as e:
#         log_warning(f"Failed to send to dashboard: {e}")

# def send_alert(log_text, advice):
#     try:
#         requests.post(f"{DASHBOARD_URL}/api/new_alert",
#                       json={"log": log_text, "advice": advice}, timeout=1)
#         print(f"\033[93m🚨 Alert sent: {advice}\033[0m")
#         alert(ALERT_SOUND)
#     except Exception as e:
#         log_warning(f"Failed to send alert: {e}")

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

#     if label_str == 'anomaly':
#         for keyword, advice in critical_alerts.items():
#             if keyword.lower() in line.lower():
#                 send_alert(line, advice)

# class LogHandler(FileSystemEventHandler):
#     def __init__(self, file_path):
#         super().__init__()
#         self.file_path = file_path
#         self._last_size = os.path.getsize(file_path)

#     def on_modified(self, event):
#         if event.src_path == self.file_path:
#             new_size = os.path.getsize(self.file_path)
#             if new_size > self._last_size:
#                 with open(self.file_path, 'r') as f:
#                     f.seek(self._last_size)
#                     for line in f.read().splitlines():
#                         process_log(os.path.basename(self.file_path), line.strip())
#                 self._last_size = new_size

# def watch_journalctl():
#     log_info("🚀 Started journalctl monitoring...")
#     process = subprocess.Popen(['journalctl', '-f', '-o', 'short'],
#                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
#     for line in process.stdout:
#         process_log('journalctl', line.strip())

# if __name__ == "__main__":
#     observer = Observer()
#     threading.Thread(target=save_hashes_periodically, daemon=True).start()

#     for file_path in LOG_FILES:
#         if os.path.exists(file_path):
#             observer.schedule(LogHandler(file_path), path=file_path, recursive=False)
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









import joblib
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import subprocess
import threading
import time
import os
import csv
from datetime import datetime
import requests
import hashlib
from sentence_transformers import SentenceTransformer
import json # Ensure this is imported
import smtplib # Ensure this is imported
from email.mime.text import MIMEText # Ensure this is imported

# === Colors helpers ===
def log_info(msg): print(f"\033[94mℹ️ {msg}\033[0m")
def log_success(msg): print(f"\033[92m✅ {msg}\033[0m")
def log_warning(msg): print(f"\033[93m⚠️ {msg}\033[0m")
def log_error(msg): print(f"\033[91m❗ {msg}\033[0m")
def log_dim(msg): print(f"\033[90m{msg}\033[0m")

# === Load embedder & model ===
embedder = joblib.load("/home/rksha/Documents/Projects/log-anamoly-detector/Linux/model/sentence_embedder.pkl")
model = joblib.load("/home/rksha/Documents/Projects/log-anamoly-detector/Linux/model/sgd_embedder.pkl")

# Files & paths
PENDING_CSV = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux/logs/review.csv"
prediction_log = '/home/rksha/Documents/Projects/log-anamoly-detector/Linux/logs/prediction.log'
ALERT_SOUND = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux/logs/alert.wav"
KNOWN_HASHES_FILE = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux/logs/kwnhashes.txt"
REAL_LOG_CSV = '/home/rksha/Documents/Projects/log-anamoly-detector/Linux/logs/real_log.csv'
DASHBOARD_URL = "http://127.0.0.1:8000"
ALERTS_CONFIG_FILE = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux/scripts/alerts_config.json" # Define path for config

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

# === Load Alert Configuration ===
try:
    with open(ALERTS_CONFIG_FILE, 'r') as f:
        alert_config = json.load(f)
    log_success("✅ Loaded alerts_config.json successfully.")
except FileNotFoundError:
    log_error(f"{ALERTS_CONFIG_FILE} not found! External alerts will not be sent.")
    alert_config = {"rules": [], "notifications": {}}
except json.JSONDecodeError:
    log_error(f"Error decoding {ALERTS_CONFIG_FILE}. Please check its format.")
    alert_config = {"rules": [], "notifications": {}}

# === Load known hashes ===
if os.path.exists(KNOWN_HASHES_FILE):
    with open(KNOWN_HASHES_FILE, 'r') as f:
        known_hashes = set(line.strip() for line in f)
else:
    known_hashes = set()

# === Ensure CSV exists ===
if not os.path.exists(PENDING_CSV):
    with open(PENDING_CSV, 'w', newline='', encoding='utf-8') as f:
        csv.writer(f).writerow(['timestamp', 'source', 'content', 'label'])

def play_alert_sound():
    try:
        subprocess.Popen(['paplay', ALERT_SOUND])
    except Exception as e:
        log_warning(f"Sound playback failed: {e}")

def log_to_csv(source, content, label):
    timestamp = datetime.now().isoformat()
    with open(PENDING_CSV, 'a', newline='', encoding='utf-8') as f:
        csv.writer(f).writerow([timestamp, source, content, label])

def log_prediction(label_str, log_text):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(prediction_log, 'a') as pf:
        pf.write(f"{timestamp},{label_str},{log_text}\n")

def send_to_dashboard(log_text, label_str):
    payload = {"log": log_text, "label": label_str, "timestamp": datetime.now().isoformat()}
    try:
        requests.post(f"{DASHBOARD_URL}/api/new_log", json=payload, timeout=1)
    except Exception as e:
        log_warning(f"Failed to send to dashboard: {e}")

# === Start: New Notification Functions ===
def send_slack_alert(title, log_line, webhook_url):
    payload = {
        "text": f"🚨 *{title}*",
        "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": f"🚨 *{title}*\n*Log Entry:*\n```{log_line}```"}}]
    }
    try:
        requests.post(webhook_url, json=payload, timeout=5)
        log_success(f"Slack notification sent for: {title}")
    except Exception as e:
        log_warning(f"Failed to send Slack alert: {e}")

def send_email_alert(title, log_line, config):
    msg = MIMEText(f"An alert was triggered for: {title}\n\nLog Entry:\n{log_line}")
    msg['Subject'] = f"Log Anomaly Alert: {title}"
    msg['From'] = config['smtp_user']
    msg['To'] = config['recipient']
    try:
        with smtplib.SMTP(config['smtp_server'], config['smtp_port']) as server:
            server.starttls()
            server.login(config['smtp_user'], config['smtp_password'])
            server.send_message(msg)
            log_success(f"Email notification sent for: {title}")
    except Exception as e:
        log_warning(f"Failed to send email alert: {e}")
# === End: New Notification Functions ===

def is_new_log_and_save_hash(log_text):
    h = hashlib.sha256(log_text.encode('utf-8')).hexdigest()
    if h not in known_hashes:
        known_hashes.add(h)
        with open(KNOWN_HASHES_FILE, 'a') as f:
            f.write(h + '\n')
        return True
    return False

def save_hashes_periodically(interval=60):
    while True:
        time.sleep(interval)
        try:
            with open(KNOWN_HASHES_FILE, 'w') as f:
                for h in known_hashes:
                    f.write(h + '\n')
            log_dim(f"💾 Periodic save of known hashes ({len(known_hashes)})")
        except Exception as e:
            log_error(f"Failed to save known hashes: {e}")

def process_log(source, line):
    if any(p in line for p in IGNORED_PATTERNS):
        log_dim(f"⏩ Ignored harmless log in {source}: {line}")
        return

    # === NLP embedding prediction ===
    embedding = embedder.encode([line])
    pred = model.predict(embedding)[0]
    label_str = 'anomaly' if pred == 1 else 'normal'

    if label_str == 'anomaly':
        log_error(f" Anomaly detected in {source}: {line}")
    else:
        log_success(f" Normal in {source}: {line}")

    log_prediction(label_str, line)
    send_to_dashboard(line, label_str)

    if is_new_log_and_save_hash(line):
        log_to_csv(source, line, label_str)
    else:
        if not os.path.exists(REAL_LOG_CSV):
            with open(REAL_LOG_CSV, 'w', newline='', encoding='utf-8') as f:
                csv.writer(f).writerow(['timestamp', 'source', 'content', 'label'])
        timestamp = datetime.now().isoformat()
        with open(REAL_LOG_CSV, 'a', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow([timestamp, source, line, label_str])
        log_info(f"🔁 Duplicate text → skipped review, added to real_log.csv")

    # === START: CORRECTED ALERT LOGIC ===
    # This block now handles all alert logic.
    if label_str == 'anomaly':
        # STEP 1: Always send a generic alert to the dashboard for ANY anomaly.
        try:
            advice = "Anomaly detected by ML model. Review for details."
            requests.post(f"{DASHBOARD_URL}/api/new_alert", json={"log": line, "advice": advice}, timeout=1)
            play_alert_sound() # Play sound for any anomaly
        except Exception as e:
            log_warning(f"Failed to send generic alert to dashboard: {e}")

        # STEP 2: Check for specific keywords to trigger EXTERNAL notifications.
        for rule in alert_config.get('rules', []):
            if rule.get('enabled') and rule.get('keyword', '').lower() in line.lower():
                # If a source is specified in the rule, it must match
                if 'source' in rule and rule.get('source') and rule['source'] != source:
                    continue # Skip if source doesn't match this rule
                
                # If rule matches, trigger external notifications
                log_info(f"Matched alert rule: '{rule['name']}'. Triggering notifications.")
                notifications = alert_config.get('notifications', {})
                if notifications.get('slack', {}).get('enabled'):
                    send_slack_alert(rule['name'], line, notifications['slack']['webhook_url'])
                if notifications.get('email', {}).get('enabled'):
                    send_email_alert(rule['name'], line, notifications['email'])
                
                break # Stop after the first matching rule
    # === END: CORRECTED ALERT LOGIC ===


class LogHandler(FileSystemEventHandler):
    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path
        self._last_size = os.path.getsize(file_path)

    def on_modified(self, event):
        if event.src_path == self.file_path:
            try:
                new_size = os.path.getsize(self.file_path)
                if new_size > self._last_size:
                    with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        f.seek(self._last_size)
                        for line in f:
                            if line.strip(): # process only non-empty lines
                                process_log(os.path.basename(self.file_path), line.strip())
                    self._last_size = new_size
            except FileNotFoundError:
                log_warning(f"File vanished, skipping: {self.file_path}")
                self._last_size = 0 # Reset size
            except Exception as e:
                log_error(f"Error processing modified file {self.file_path}: {e}")


def watch_journalctl():
    log_info("🚀 Started journalctl monitoring...")
    process = subprocess.Popen(['journalctl', '-f', '-o', 'cat'],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='ignore')
    for line in process.stdout:
        if line.strip(): # process only non-empty lines
            process_log('journalctl', line.strip())

if __name__ == "__main__":
    observer = Observer()
    threading.Thread(target=save_hashes_periodically, daemon=True).start()

    for file_path in LOG_FILES:
        if os.path.exists(file_path):
            observer.schedule(LogHandler(file_path), path=os.path.dirname(file_path), recursive=False)
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