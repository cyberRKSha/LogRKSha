import os, re, sys, dill, pika, json, time, redis, pickle, joblib, hashlib, requests
import numpy as np
import tensorflow as tf
import logging
from typing import Dict, Any
from app.log_config import setup_logging
from tensorflow.keras.preprocessing.sequence import pad_sequences
from datetime import datetime, timezone, timedelta
from sklearn.pipeline import make_pipeline
from sentence_transformers import SentenceTransformer
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.config import settings
LOG_QUEUE_NAME = 'log_queue'

IGNORED_PATTERNS = [
    "ACPI group/action undefined: button/",
    "ACPI group/action undefined: video/",
]

attack_mappings = []

# logger.info("Worker starting up. Loading models...")

embedder = None
supervised_model = None
unsupervised_model = None
lstm_model = None
unsupervised_threshold = None
explainer = None

def load_models():
    """Loads all ML models on first use and caches them in global variables."""
    global embedder, supervised_model, unsupervised_model, lstm_model, unsupervised_threshold, explainer
    
    if embedder is None:
        logger.info("Loading ML models for the worker...")
        registry_path = os.path.join(settings.PROJECT_ROOT, "model_registry.json")
        with open(registry_path, 'r') as f:
            active_models = json.load(f)

        embedder = SentenceTransformer(str(settings.EMBEDDER_PATH))
        supervised_model = joblib.load(active_models["supervised_model"])
        unsupervised_model = tf.keras.models.load_model(active_models["autoencoder_model"])
        lstm_model = tf.keras.models.load_model(active_models["lstm_model"])
        
        with open(settings.THRESHOLD_PATH, 'r') as f:
            unsupervised_threshold = json.load(f)['threshold']

        with open(settings.EXPLAINER_PATH, 'rb') as f:
            explainer = dill.load(f)

        logger.info("All worker models loaded successfully.")

# registry_path = os.path.join(settings.PROJECT_ROOT, "model_registry.json")
# with open(registry_path, 'r') as f:
#     active_models = json.load(f)
# embedder = SentenceTransformer(str(settings.EMBEDDER_PATH))
# supervised_model = joblib.load(active_models["supervised_model"])
# unsupervised_model = tf.keras.models.load_model(active_models["autoencoder_model"])
# lstm_model = tf.keras.models.load_model(active_models["lstm_model"])
# with open(settings.THRESHOLD_PATH, 'r') as f:
#     unsupervised_threshold = json.load(f)['threshold']
# with open(settings.EXPLAINER_PATH, 'rb') as f:
#     explainer = dill.load(f)
# lstm_model = tf.keras.models.load_model(settings.LSTM_MODEL_PATH)
# logger.info("✅ All models loaded successfully.")

if os.path.exists(settings.KNOWN_HASHES_FILE):
    with open(settings.KNOWN_HASHES_FILE, 'r') as f:
        known_hashes = set(line.strip() for line in f)
else:
    known_hashes = set()

# active_sessions = {}
SEQUENCE_LEN = 20

# --- REDIS CONNECTION ---
redis_client = None
def get_redis_client():
    global redis_client
    if redis_client is None:
        try:
            redis_client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                decode_responses=False # We will handle decoding/encoding with pickle
            )
            redis_client.ping() # Check if the connection is successful
            logger.info("✅ Connected to Redis successfully.")
        except redis.exceptions.ConnectionError as e:
            logger.error(f"❗ Could not connect to Redis: {e}")
            sys.exit(1)
    return redis_client

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
    if not os.path.exists(settings.STATUS_FILE):
        return True
    try:
        with open(settings.STATUS_FILE, 'r') as f:
            return json.load(f).get("is_active", True)
    except (json.JSONDecodeError, IOError):
        return True # Default to active on error

def insert_log_to_db(source, content, p_label, risk, seq_risk, verdict_str, reviewed=0, explanation="", threat_intel=None):
    """Inserts a log into the database using SQLAlchemy."""
    engine = create_engine(settings.DATABASE_URL)
    query = text("""
        INSERT INTO logs (timestamp, source, content, predicted_label, final_label, is_reviewed, risk_score, sequence_risk, verdict, explanation, threat_intel)
        VALUES (:ts, :source, :content, :p_label, :f_label, :reviewed, :risk, :seq_risk, :verdict, :explanation, :threat_intel)
        RETURNING id, timestamp
    """)
    
    try:
        with engine.connect() as connection:
            # Begin a transaction
            with connection.begin() as transaction:
                result = connection.execute(query, {
                    "ts": datetime.now(timezone.utc),
                    "source": source,
                    "content": content,
                    "p_label": p_label,
                    "f_label": p_label, # final_label is same as predicted initially
                    "reviewed": reviewed,
                    "risk": risk,
                    "seq_risk": seq_risk,
                    "verdict": verdict_str,
                    "explanation": explanation,
                    "threat_intel": json.dumps(threat_intel) if threat_intel else None
                }).fetchone()

            if result:
                # The result object can be accessed by index
                return result[0], result[1]
            else:
                logger.error("Database insert did not return the new log ID and timestamp.")
                return None, None
                
    except Exception as error:
        logger.error(f"Database write failed: {error}")
        return None, None

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
        requests.post(f"{settings.DASHBOARD_URL}/api/new_log", json=payload, timeout=2)

    except TypeError as e:
        logger.error(f"Failed to serialize payload to JSON: {e}. Payload: {payload}")
    except Exception as e:
        logger.warning(f"Failed to send to dashboard: {e}")

def is_new_log_and_save_hash(log_text):
    h = hashlib.sha256(log_text.encode('utf-8')).hexdigest()
    if h not in known_hashes:
        known_hashes.add(h)
        with open(settings.KNOWN_HASHES_FILE, 'a') as f:
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
    user_match = re.search(r"\b(?:user=|for user )\b(\w+)", log_line) # e.g., "user=root" or "user root"
    if user_match:
        return f"user_{user_match.group(1)}"
        
    # 3. If no user, try to find a Process ID (PID)
    pid_match = re.search(r"\[(\d+)\]:", log_line) # e.g., "sshd[12345]:"
    if pid_match:
        return f"pid_{pid_match.group(1)}"
        
    return None

def update_and_predict_sequence(log_line, embedding):
    """
    Manages active log sequences in Redis and predicts anomaly score using the LSTM model.
    """
    session_key = get_session_key(log_line)
    if not session_key:
        return 0.0  # Cannot perform sequence analysis without a key

    # 1. Get the current sequence from Redis
    raw_sequence = redis_client.get(session_key)
    
    if raw_sequence:
        # If a sequence exists, decode it from bytes to a list of embeddings
        session_embeddings = pickle.loads(raw_sequence)
    else:
        # Otherwise, start a new empty list for the sequence
        session_embeddings = []

    # 2. Add the new log's embedding to the sequence
    # embedding is shape (1, 384), we want to append the inner array (384,)
    session_embeddings.append(embedding[0])
    
    # 3. Keep the sequence at the maximum length defined in your settings
    if len(session_embeddings) > settings.SEQUENCE_LEN:
        session_embeddings.pop(0)

    # 4. Save the updated sequence back to Redis
    # We use pickle.dumps to turn the Python list of arrays into bytes
    encoded_sequence = pickle.dumps(session_embeddings)
    # setex saves the value and sets an automatic expiration (timeout)
    redis_client.setex(session_key, settings.SESSION_TIMEOUT_SECONDS, encoded_sequence)
    
    # 5. Prepare the sequence for the model (this part is the same as before)
    padded_sequence = pad_sequences([session_embeddings], maxlen=settings.SEQUENCE_LEN, dtype='float32', padding='pre')
    
    # 6. Predict with the LSTM model
    sequence_risk_score = lstm_model.predict(padded_sequence, verbose=0)[0][0]
    
    # NOTE: The manual cleanup loop is no longer needed.
    # Redis's `setex` command automatically handles the expiration of old sessions.
            
    return float(sequence_risk_score)

def load_attack_mappings():
    """Loads the MITRE ATT&CK mapping rules from the JSON file."""
    global attack_mappings
    if not attack_mappings: # Only load once
        try:
            map_file_path = os.path.join(settings.PROJECT_ROOT, "attack_mapping.json")
            with open(map_file_path, 'r') as f:
                attack_mappings = json.load(f)
            logger.info(f"Loaded {len(attack_mappings)} MITRE ATT&CK mapping rules.")
        except Exception as e:
            logger.error(f"Failed to load attack_mapping.json: {e}")

def map_log_to_attack(log_content: str) -> Dict[str, Any] | None:
    """Checks a log against the loaded rules and returns the first match."""
    if not attack_mappings:
        load_attack_mappings()

    if not isinstance(log_content, str):
        return None

    log_content_lower = log_content.lower()
    logger.info(f"--- Attempting to map log: '{log_content_lower}' ---")
    for rule in attack_mappings:
        if all(keyword.lower() in log_content_lower for keyword in rule["keywords"]):
            logger.info(f"[+] SUCCESS: Log matched MITRE rule '{rule['name']}' (TTP: {rule['ttp']}).")
            return {
                "tactic": rule["tactic"],
                "technique": rule["ttp"],
                "description": rule["name"],
            }
    logger.warning(f"[-] FAILED: No MITRE rule matched for this log content.")
    return None

def extract_ip_from_log(log_line: str) -> str | None:
    """Extracts the first valid IPv4 address from a log line."""
    if not isinstance(log_line, str):
        return None
    match = re.search(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", log_line)
    return match.group(0) if match else None

def check_ip_abuseipdb(ip_address: str) -> dict | None:

    if not settings.ABUSEIPDB_API_KEY:
        logger.warning("AbuseIPDB API key is not set. Skipping threat intel check.")
        return None # Don't proceed if no API key is set

    r = get_redis_client()
    cache_key = f"ip_intel:{ip_address}"

    # 1. Check the cache first
    cached_result = r.get(cache_key)
    if cached_result:
        logger.info(f"Threat intel cache HIT for IP: {ip_address}")
        return json.loads(cached_result)

    logger.info(f"Threat intel cache MISS for IP: {ip_address}. Querying API...")
    
    # 2. If not in cache, query the API
    headers = {'Accept': 'application/json', 'Key': settings.ABUSEIPDB_API_KEY}
    params = {'ipAddress': ip_address, 'maxAgeInDays': '90'}
    
    try:
        response = requests.get('https://api.abuseipdb.com/api/v2/check', headers=headers, params=params, timeout=5)
        response.raise_for_status() # Raise an exception for bad status codes
        
        data = response.json().get('data')
        if not data:
            return None

        # 3. Store the result in Redis with a 24-hour expiration
        # We store a simplified version of the result
        result_to_cache = {
            'abuseConfidenceScore': data.get('abuseConfidenceScore'),
            'countryCode': data.get('countryCode'),
            'isp': data.get('isp'),
            'domain': data.get('domain'),
            'totalReports': data.get('totalReports'),
        }
        r.setex(cache_key, timedelta(hours=24), json.dumps(result_to_cache))
        
        return result_to_cache

    except requests.exceptions.RequestException as e:
        logger.error(f"Error querying AbuseIPDB API: {e}")
        return None

def process_log(source, line):
    load_models()
    if line.startswith("[LOG-WORKER]"):
        return
    
    line = line.replace('%', '%%')

    if any(p in line for p in IGNORED_PATTERNS):
        return
    
    h = hashlib.sha256(line.encode('utf-8')).hexdigest()
    if h in known_hashes:
        logger.info(f"Skipping duplicate log: {line}")
        return # Exit the function early

    # If it's new, add it to our known hashes and proceed with processing.
    known_hashes.add(h)
    with open(settings.KNOWN_HASHES_FILE, 'a') as f:
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

    threat_intel_data = None
    if is_anomaly:
        ip = extract_ip_from_log(line) # We can reuse this to find the IP
        if ip:
            logger.info(f"Found IP {ip} in anomalous log, checking threat intel...")
            threat_intel_data = check_ip_abuseipdb(ip)
            if threat_intel_data:
                logger.info(f"Enriched log with threat intel for IP {ip}: Score {threat_intel_data.get('abuseConfidenceScore')}")
        else:
            logger.info("Anomalous log detected, but no IP address found to enrich.")

    original_timestamp = parse_timestamp_from_log(line)
    dashboard_payload = {
        "log": line,
        "label": label_str,
        "verdict": verdict,
        "risk_score": risk_score,
        "is_alert": False, # Default to false
        "timestamp": original_timestamp,
        "sequence_risk": sequence_risk,
        "play_sound": False
    }

    
    # is_unique_for_review = is_new_log_and_save_hash(line)
    # log_is_reviewed_status = 0 if is_unique_for_review else 1
    new_log_id, new_log_timestamp = insert_log_to_db(source, line, int(is_anomaly), risk_score, sequence_risk, verdict, 0, "", threat_intel=threat_intel_data)
    
    if is_anomaly and new_log_id and new_log_timestamp:
        try:
            attack_info = map_log_to_attack(line)
            engine = create_engine(settings.DATABASE_URL)
            alert_query = text("""
                INSERT INTO alerts (log_id, log_timestamp, timestamp, rule_name, status, mitre_tactic, mitre_technique, rule_description) 
                VALUES (:log_id, :log_ts, :now_ts, :rule_name, 'New', :tactic, :technique, :desc)
                RETURNING id
            """)

            with engine.connect() as connection:
                with connection.begin() as transaction:
                    alert_result = connection.execute(alert_query, {
                        "log_id": new_log_id,
                        "log_ts": new_log_timestamp,
                        "now_ts": datetime.now(timezone.utc),
                        "rule_name": verdict,
                        "tactic": attack_info.get("tactic") if attack_info else None,
                        "technique": attack_info.get("technique") if attack_info else None,
                        "desc": attack_info.get("description") if attack_info else None
                    }).scalar_one_or_none() # .scalar_one_or_none() is great for single-value returns
            
            alert_id = alert_result

            # Update the dashboard payload with the new alert info
            dashboard_payload["is_alert"] = True
            dashboard_payload["alert_info"] = {
                "id": alert_id, "status": "New", "rule_name": verdict,
                "timestamp": original_timestamp, "log_id": new_log_id,
                "content": line, "risk_score": risk_score,
                "rule_description": attack_info.get("description") if attack_info else None,
                "mitre_tactic": attack_info.get("tactic") if attack_info else None,
                "mitre_technique": attack_info.get("technique") if attack_info else None
            }

            if risk_score >= 0.79:
                advice = f"({verdict}) | Risk: {risk_score:.2f}"
                # This part for sending notifications remains the same
                requests.post(f"{settings.DASHBOARD_URL}/api/new_alert", json={"log": line, "advice": advice, "status": "New", "id": alert_id}, timeout=1)
                dashboard_payload["play_sound"] = True

        except Exception as e:
            logger.warning(f"Failed to create alert or send to dashboard: {e}")

    logger.info(f" [LOG-WORKER] Verdict: [{verdict}] | RiskScore: {risk_score} | Loss: {reconstruction_loss:.4f} | Log: {line}")
    # send_to_dashboard(line, label_str, verdict, risk_score)
    send_to_dashboard(dashboard_payload)

# --- Main Worker Loop ---
def main():
    get_redis_client()
    while True:
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=settings.RABBITMQ_HOST))
            channel = connection.channel()
            channel.queue_declare(queue=LOG_QUEUE_NAME, durable=True)

            def callback(ch, method, properties, body):
                try:
                    message = json.loads(body)
                    process_log(message.get('source'), message.get('content'))
                except Exception as e:
                    logger.warning(f"Error processing message: {e}")
                finally:
                    ch.basic_ack(delivery_tag=method.delivery_tag)

            channel.basic_qos(prefetch_count=1)
            # channel.basic_consume(queue=LOG_QUEUE_NAME, on_message_callback=callback)
            logger.info('Worker connected to RabbitMQ.')
            logger.info(' [*] Worker is waiting for logs. To exit press CTRL+C')
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
                logger.error(f"❗ Connection to RabbitMQ lost: {e}. Retrying in 5 seconds...")
                time.sleep(5)

        except KeyboardInterrupt:
            print('Interrupted')
            break # Exit the outer loop on Ctrl+C

        except Exception as e:
            # Catch any other unexpected errors
            logger.error(f"❗ An unexpected error occurred: {e}. Retrying in 10 seconds...")
            time.sleep(10)

if __name__ == '__main__':
    setup_logging()
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
    tf.get_logger().setLevel('ERROR')
    try:
        main()
    except KeyboardInterrupt:
        logger.info('Interrupted')
        sys.exit(0)


