import os, re, sys, dill, pika, json, time, redis, pickle, joblib, hashlib, requests
import numpy as np
import tensorflow as tf
import logging, keras
from typing import Dict, Any
from app.log_config import setup_logging
from scripts.playbooks import block_ip_ufw, send_slack_alert
from keras.preprocessing.sequence import pad_sequences
from datetime import datetime, timezone, timedelta
from sklearn.pipeline import make_pipeline
from sentence_transformers import SentenceTransformer
from sqlalchemy import create_engine, text
from scripts.sigma_engine import SigmaEngine
from scripts.zeek_ml_engine import ZeekMLEngine
from app.services.es_client import es_client, init_indexes

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

ACTION_MAP = {
    "block_ip_ufw": block_ip_ufw,
    "send_slack_alert": send_slack_alert
}

logger.info("Initializing Sigma Engine (this may take a moment)...")
sigma_engine = SigmaEngine(rules_path=str(settings.PROJECT_ROOT / "sigma-rules"))
logger.info("Sigma Engine is ready.")

attack_mappings = []

# logger.info("Worker starting up. Loading models...")

embedder = None
supervised_model = None
unsupervised_model = None
lstm_model = None
unsupervised_threshold = None
explainer = None
zeek_engine = None

# def load_models():
#     """Loads all ML models on first use and caches them in global variables."""
#     global embedder, supervised_model, unsupervised_model, lstm_model, unsupervised_threshold, explainer
    
#     if embedder is None:
#         logger.info("Loading ML models for the worker...")
#         registry_path = os.path.join(settings.PROJECT_ROOT, "model_registry.json")
#         with open(registry_path, 'r') as f:
#             active_models = json.load(f)

#         embedder = SentenceTransformer(str(settings.EMBEDDER_PATH))
#         supervised_model = joblib.load(active_models["supervised_model"])
#         unsupervised_model = keras.models.load_model(active_models["autoencoder_model"])
#         lstm_model = keras.models.load_model(active_models["lstm_model"])
        
#         with open(settings.THRESHOLD_PATH, 'r') as f:
#             unsupervised_threshold = json.load(f)['threshold']

#         with open(settings.EXPLAINER_PATH, 'rb') as f:
#             explainer = dill.load(f)

#         logger.info("All worker models loaded successfully.")

def load_models():
    """Loads all ML models on first use and caches them in global variables."""
    global embedder, supervised_model, unsupervised_model, lstm_model
    global unsupervised_threshold, explainer

    if embedder is not None:
        return  # already loaded

    logger.info("Loading ML models for the worker...")

    registry_path = os.path.join(settings.PROJECT_ROOT, "model_registry.json")
    if not os.path.exists(registry_path):
        logger.error(f"model_registry.json not found at {registry_path}")
        return

    with open(registry_path, 'r') as f:
        active_models = json.load(f)

    try:
        embedder = SentenceTransformer(str(settings.EMBEDDER_PATH))

        supervised_model = joblib.load(
            os.path.join(settings.PROJECT_ROOT, active_models["supervised_model"])
        )

        unsupervised_model = keras.models.load_model(
            os.path.join(settings.PROJECT_ROOT, active_models["autoencoder_model"])
        )

        lstm_model = keras.models.load_model(
            os.path.join(settings.PROJECT_ROOT, active_models["lstm_model"])
        )

        with open(settings.THRESHOLD_PATH, 'r') as f:
            unsupervised_threshold = float(json.load(f)["threshold"])

        with open(settings.EXPLAINER_PATH, 'rb') as f:
            explainer = dill.load(f)

        logger.info("✅ All worker models loaded successfully.")

    except Exception as e:
        logger.error(f"❌ Failed to load models: {e}", exc_info=True)

        # hard fail – do NOT process logs in partial state
        embedder = None
        supervised_model = None
        unsupervised_model = None
        lstm_model = None
        unsupervised_threshold = None
        explainer = None


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
                log_id, log_ts = result[0], result[1]
                
                # --- Elasticsearch Dual-Write ---
                if settings.ES_ENABLED:
                    try:
                        doc = {
                            "timestamp": log_ts, # Use DB timestamp for consistency
                            "source": source,
                            "content": content,
                            "predicted_label": int(p_label),
                            "final_label": int(p_label),
                            "risk_score": float(risk),
                            "verdict": verdict_str,
                            "explanation": explanation,
                            "threat_intel": threat_intel
                        }
                        es_client.index(index=settings.ES_INDEX_LOGS, id=log_id, body=doc)
                        # logger.info(f"indexed log {log_id} to ES")
                    except Exception as e:
                        logger.error(f"❌ Failed to index log {log_id} to Elasticsearch: {e}")

                return log_id, log_ts
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

def load_zeek_engine():
    """Load specialized Zeek ML engine"""
    global zeek_engine
    if zeek_engine is None:
        try:
            zeek_engine = ZeekMLEngine(settings.MODEL_DIR)
            logger.info("Zeek ML engine loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load Zeek ML engine: {e}", exc_info=True)
            zeek_engine = None

def is_zeek_source(source: str) -> bool:
    if not source:
        return False
    name = os.path.basename(source).lower()
    if name.endswith(".gz"):
        name = name[:-3]
    zeek_names = (
        "conn.log", "dns.log", "http.log", "ssl.log", "x509.log",
        "weird.log", "notice.log", "files.log"
    )
    return name in zeek_names

def get_session_key(log_line: str) -> str | None:
    """
    Extracts a session key from a log line in a prioritized order.
    1. IP Address
    2. Username
    3. Process ID (PID)
    4. Generic User
    """
    # 1. Try to find an IP address
    ip_match = re.search(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", log_line)
    if ip_match:
        return f"ip_{ip_match.group(0)}"

    # 2. If no IP, try to find a common username pattern
    user_patterns = [
        r'User session for (\w+)',          # NEW: "User session for testuser123"  
        r'(?:user|for user) (\w+)',         # EXISTING: "user root" or "for user admin"
        r'for user (\w+)',                  # "Failed password for user admin"
        r'user (\w+) by',
    ]
    
    for pattern in user_patterns:
        user_match = re.search(pattern, log_line)
        if user_match:
            return f"user_{user_match.group(1)}"
        
    # 3. If no user, try to find a Process ID (PID)
    pid_match = re.search(r"\[(\d+)\]:", log_line) # e.g., "sshd[12345]:"
    if pid_match:
        return f"pid_{pid_match.group(1)}"
    
    # 4. Fallback: try to find generic user pattern (lowest priority)
    generic_user_match = re.search(r'\buser\s+(\w+)', log_line)
    if generic_user_match:
        return f"user_{generic_user_match.group(1)}"
        
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

def extract_ip_from_log(log_content: str) -> str | None:
    """Extracts the first valid IPv4 address from a log line."""
    if not isinstance(log_content, str):
        return None
    match = re.search(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", log_content)
    return match.group(0) if match else None

def run_playbooks(alert_info: dict):
    """
    Checks an alert against all active playbooks and executes actions if triggers are met.
    """
    print(f"PLAYBOOK RUNNER: Checking playbooks for alert on log ID {alert_info['log_id']}")
    engine = create_engine(settings.DATABASE_URL)
    
    try:
        with engine.connect() as connection:
            playbooks = connection.execute(text("SELECT * FROM playbooks WHERE is_active = TRUE")).fetchall()

        for playbook in playbooks:
            playbook_dict = dict(playbook._mapping)
            conditions = playbook_dict['trigger_conditions']
            actions = playbook_dict['actions']
            
            # Simple condition checker (can be made more robust)
            match = True
            # Loop through all conditions in the playbook's trigger
            for key, condition in conditions.items():
                alert_value = alert_info.get(key)
                
                # If the required key (e.g., 'risk_score') isn't in the alert, it's not a match.
                if alert_value is None:
                    match = False
                    break
                
                # Check conditions based on operator
                if condition.get('operator') == '>=' and not (alert_value >= condition.get('value')):
                    match = False
                    break
                if condition.get('operator') == 'contains' and not (isinstance(alert_value, str) and condition.get('value', '').lower() in alert_value.lower()):
                    match = False
                    break
            
            if match:
                print(f"PLAYBOOK MATCH: Alert matched playbook '{playbook_dict['name']}'. Executing actions...")
                for action_item in actions:
                    action_func_name = action_item.get("action")
                    if action_func_name in ACTION_MAP:
                        action_func = ACTION_MAP[action_func_name]
                        
                        # Dynamic parameter handling
                        if 'param_source' in action_item and action_item['param_source'] == 'log_content.ip':
                            ip = extract_ip_from_log(alert_info['content'])
                            action_func(ip)
                        elif 'message' in action_item:
                            message = action_item['message'].format(log_content=alert_info['content'])
                            action_func(message)
                        else:
                             action_func() # For actions with no params
                    else:
                        print(f"PLAYBOOK WARNING: Action '{action_func_name}' not found in ACTION_MAP.")

    except Exception as e:
        print(f"PLAYBOOK RUNNER ERROR: Could not run playbooks. Error: {e}")

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

def process_log(source, line, honeytoken=None):
    load_models()
    if not embedder:
        return
    if any(x is None for x in [embedder, supervised_model, unsupervised_model, lstm_model, unsupervised_threshold]):
        logger.error("Models are not ready; dropping message (check model_registry.json and artifacts).")
        return
    if line.startswith("[LOG-WORKER]"):
        return
    
    line = line.replace('%', '%%')

    if any(p in line for p in IGNORED_PATTERNS):
        return
    
    # Priority Check: Honeytoken
    if honeytoken:
        logger.warning(f"🚨 [HONEYTOKEN] Detected: {honeytoken} in {source}")
        # Force anomaly parameters
        is_anomaly = True
        verdict = f"Honeytoken Triggered: {honeytoken}"
        risk_score = 1.0
        sequence_risk = 0.0
        reconstruction_loss = 0.0
    
    elif zeek_engine and is_zeek_source(source):  # Use engine's method
        load_zeek_engine()
        is_anomaly, risk_score, verdict, details = zeek_engine.predict_zeek_log(line, source)
        normalized_line = zeek_engine.normalize_zeek_for_analysis(line, source)
        logger.info(f"🔄 [ZEEK] {source}: {normalized_line[:100]}...")
        
        # Skip duplicate check for Zeek (handled by engine)
        h = hashlib.sha256(line.encode('utf-8')).hexdigest()
        if h in known_hashes:
            logger.info(f"Skipping duplicate log: {line[:50]}")
            return
        known_hashes.add(h)
        with open(settings.KNOWN_HASHES_FILE, 'a') as f:
            f.write(f"{h}\n")
        
        # Skip further ML processing - use engine's results
        sequence_risk = 0.0  # Zeek engine handles this
        return
        
    else:
        # Standard processing for non-Zeek logs (existing logic unchanged)
        h = hashlib.sha256(line.encode('utf-8')).hexdigest()
        if h in known_hashes:
            logger.info(f"Skipping duplicate log: {line[:50]}")
            return
        
        if not is_monitoring_active():
            return
        
        known_hashes.add(h)
        with open(settings.KNOWN_HASHES_FILE, 'a') as f:
            f.write(f"{h}\n")
        
        # Check Sigma rules first
        sigma_match = sigma_engine.check_log(line)
        
        # ML Processing
        embedding = embedder.encode([line], show_progress_bar=False)
        supervised_pred = supervised_model.predict(embedding)[0]
        ae_recon = unsupervised_model.predict(embedding, verbose=0)
        reconstruction_loss = np.mean(np.abs(embedding - ae_recon))
        
        risk_score = float(min(1.0, reconstruction_loss / unsupervised_threshold))
        unsupervised_pred = 1 if reconstruction_loss > unsupervised_threshold else 0
        
        # Sequence analysis
        sequence_risk = update_and_predict_sequence(line, embedding)
        
        # Determine verdict
        verdict = "Normal"
        is_anomaly = False
        
        if sigma_match:
            is_anomaly = True
            verdict = f"Sigma Rule: {sigma_match['title']}"
            risk_score = 0.90
            
            logger.info(f"🚨 [SIGMA] MATCH FOUND: {sigma_match['title']}")
            try:
                requests.post(f"{settings.DASHBOARD_URL}/api/new-sigma-match", json=sigma_match, timeout=1)
            except Exception as e:
                logger.warning(f"Failed to send Sigma match to dashboard: {e}")
                
        elif supervised_pred == 1:
            is_anomaly = True
            verdict = "Supervised"
            
        elif sequence_risk > 0.9:
            is_anomaly = True
            verdict = f"Malicious Sequence Detected (Score: {sequence_risk:.2f})"
            risk_score = max(risk_score, sequence_risk)
            
        elif unsupervised_pred == 1:
            is_anomaly = True
            verdict = "Novelty Detected"
    
    if not is_anomaly:
        risk_score = 0.0
    
    # Enhanced logging
    status_emoji = "🚨" if is_anomaly else "✅"
    is_zeek_flow = bool(zeek_engine and is_zeek_source(source))

    if is_zeek_flow:
        logger.info(f"{status_emoji} [ZEEK-ENHANCED] Verdict: [{verdict}] | RiskScore: {risk_score:.3f} | Source: {source}")
    else:
        # Only log reconstruction_loss for standard ML path where it's defined
        try:
            loss_val = float(reconstruction_loss)
            logger.info(f"{status_emoji} [SYS] Verdict: [{verdict}] | RiskScore: {risk_score:.3f} | Loss: {loss_val:.4f} | Source: {source}")
        except (NameError, UnboundLocalError):
            logger.info(f"{status_emoji} [SYS] Verdict: [{verdict}] | RiskScore: {risk_score:.3f} | Source: {source}")


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
    new_log_id, new_log_timestamp = insert_log_to_db(source, line, int(is_anomaly), risk_score, sequence_risk, verdict, 0, "", threat_intel=threat_intel_data)
    dashboard_payload = {
        "id": new_log_id,
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
                        "desc": attack_info.get("description") if attack_info else None,
                    }).scalar_one_or_none() # .scalar_one_or_none() is great for single-value returns
            
            alert_id = alert_result

            # Update the dashboard payload with the new alert info
            dashboard_payload["is_alert"] = True
            alert_info = {
                "id": alert_id, "status": "New", "rule_name": verdict,
                "timestamp": original_timestamp, "log_id": new_log_id,
                "content": line, "risk_score": risk_score,
                "rule_description": attack_info.get("description") if attack_info else None,
                "mitre_tactic": attack_info.get("tactic") if attack_info else None,
                "mitre_technique": attack_info.get("technique") if attack_info else None
            }
            dashboard_payload["alert_info"] = alert_info
            run_playbooks(alert_info)

            if risk_score >= 0.79:
                advice = f"({verdict}) | Risk: {risk_score:.2f}"
                # This part for sending notifications remains the same
                requests.post(f"{settings.DASHBOARD_URL}/api/new_alert", json={"log": line, "advice": advice, "status": "New", "id": alert_id}, timeout=1)
                dashboard_payload["play_sound"] = True

        except Exception as e:
            logger.error(f"Failed to create alert or send to dashboard. Error: {e}", exc_info=True)

    logger.info(f" [LOG-WORKER] Verdict: [{verdict}] | RiskScore: {risk_score} | Loss: {reconstruction_loss:.4f} | Log: {line}")
    # send_to_dashboard(line, label_str, verdict, risk_score)
    send_to_dashboard(dashboard_payload)

# --- Main Worker Loop ---
def main():
    get_redis_client()
    init_indexes() # Ensure ES indexes exist
    while True:
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=settings.RABBITMQ_HOST))
            channel = connection.channel()
            channel.queue_declare(queue=LOG_QUEUE_NAME, durable=True)

            def callback(ch, method, properties, body):
                try:
                    message = json.loads(body)
                    process_log(message.get('source'), message.get('content'), message.get('honeytoken'))
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

