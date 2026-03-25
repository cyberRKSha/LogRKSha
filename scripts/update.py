# update.py (ULTIMATE HYBRID VERSION)
import os, sys, joblib, json, pandas as pd, numpy as np, psycopg2, tensorflow as tf
from datetime import datetime
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix, precision_recall_fscore_support
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import SGDClassifier
from tensorflow.keras.models import Model
from tensorflow.keras.layers import Input, Dense
from sqlalchemy import create_engine

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.config import settings
# # --- Configuration ---
# BASE_DIR = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux"
# DATABASE_FILE = os.path.join(BASE_DIR, "log_database.db")
# # Models
# EMBEDDER_PATH = os.path.join(BASE_DIR, "model/sentence_embedder.pkl")
# SUPERVISED_MODEL_PATH = os.path.join(BASE_DIR, "model/sgd_embedder.pkl")
# AUTOENCODER_PATH = os.path.join(BASE_DIR, "model/autoencoder_model.keras")
# THRESHOLD_PATH = os.path.join(BASE_DIR, "model/autoencoder_threshold.json")
# # Checkpoint
# CHECKPOINT_FILE = os.path.join(BASE_DIR, "model/last_processed_log_id.txt")

# --- Logging Helpers ---
def log_info(msg): print(f"\033[94mℹ️ {msg}\033[0m")
def log_success(msg): print(f"\033[92m✅ {msg}\033[0m")
def log_warn(msg): print(f"\033[93m⚠️ {msg}\033[0m")
def log_report(report): print(f"\033[96m{report}\033[0m")
def log_error(msg): print(f"\033[91m❗ {msg}\033[0m")

def get_last_processed_id():
    last_id = 0
    checkpoint_path = settings.CHECKPOINT_FILE
    if os.path.exists(checkpoint_path):
        with open(checkpoint_path, "r") as f:
            content = f.read().strip()
            try: last_id = int(content)
            except (ValueError, IOError): last_id = 0
    return last_id

def create_new_autoencoder(input_dim):
    """Defines and compiles a new autoencoder model architecture."""
    input_layer = Input(shape=(input_dim,))
    encoded = Dense(128, activation='relu')(input_layer)
    encoded = Dense(64, activation='relu')(encoded)
    decoded = Dense(128, activation='relu')(encoded)
    decoded = Dense(input_dim, activation='sigmoid')(decoded)
    autoencoder = Model(input_layer, decoded)
    autoencoder.compile(optimizer='adam', loss='mae')
    log_info("Created a new autoencoder model architecture.")
    return autoencoder

def cleanup_old_models(model_prefix: str, max_versions: int = 10):
    try:
        model_files = [f for f in os.listdir(settings.MODEL_DIR) if f.startswith(model_prefix) and "_" in f]
        
        if len(model_files) > max_versions:
            model_files.sort()
            files_to_delete = model_files[:-max_versions]
            log_info(f"Found {len(model_files)} versions for '{model_prefix}'. Deleting {len(files_to_delete)} oldest versions.")
            
            for file_name in files_to_delete:
                try:
                    os.remove(os.path.join(settings.MODEL_DIR, file_name))
                    log_warn(f"Deleted old model version: {file_name}")
                except OSError as e:
                    log_error(f"Error deleting old model {file_name}: {e}")
    except Exception as e:
        log_error(f"An error occurred during model cleanup: {e}")

def trigger_model_update():

    log_info("Starting HYBRID model update process...")

    last_processed_id = get_last_processed_id()

    engine = create_engine(settings.DATABASE_URL)
    query = f"SELECT id, content, final_label FROM logs WHERE is_reviewed = 1 AND id > {last_processed_id}"
    from sqlalchemy import text
    new_logs_df = pd.read_sql_query(query, engine)
    # engine.close()

    if new_logs_df.empty:
        log_success("All models are already up-to-date. No new reviewed logs to train on.")
        return

    latest_id_in_batch = new_logs_df['id'].max()
    log_info(f"Found {len(new_logs_df)} new reviewed logs to process.")

    registry_path = os.path.join(settings.PROJECT_ROOT, "model_registry.json")
    with open(registry_path, 'r') as f:
        active_models = json.load(f)

    # --- 2. Generate Embeddings for the new data ---
    log_info("Generating embeddings for the new batch...")
    embedder = SentenceTransformer(str(settings.EMBEDDER_PATH))
    X_new_text = new_logs_df['content'].astype(str).tolist()
    X_eval = embedder.encode(X_new_text, show_progress_bar=True)
    y_new = new_logs_df['final_label'].astype(int).values
    embedding_dim = X_eval.shape[1]

    # --- 3. Update the SUPERVISED Model ---
    log_info("--- Updating Supervised Model ---")
    active_supervised_path = active_models["supervised_model"]
    if os.path.exists(active_supervised_path):
        log_info("Loading existing supervised model...")
        supervised_model = joblib.load(active_supervised_path)
        is_new_model = False
    else:
        log_warn(f"No supervised model found at {active_supervised_path}. Creating a new one.")
        supervised_model = SGDClassifier(loss='log_loss', random_state=42)
        is_new_model = True
        
    # Evaluate performance before updating
    # Evaluate performance before updating - ONLY if model is already fitted
    if not is_new_model:
        y_pred = supervised_model.predict(X_eval)
        accuracy = accuracy_score(y_new, y_pred)
        precision, recall, f1, _ = precision_recall_fscore_support(y_new, y_pred, average='binary', zero_division=0)
        
        log_report(f"Metrics on new data (Drift Check) - Acc: {accuracy:.2%}, Prec: {precision:.2f}, Rec: {recall:.2f}, F1: {f1:.2f}")

        # Store metrics in DB
        try:
            with engine.connect() as connection:
                with connection.begin():
                    connection.execute(
                        text("INSERT INTO model_metrics (timestamp, model_type, version, accuracy, precision, recall, f1_score) VALUES (:ts, :type, :ver, :acc, :prec, :rec, :f1)"),
                        {
                            "ts": datetime.now(),
                            "type": "supervised_sgd",
                            "ver": os.path.basename(active_supervised_path),
                            "acc": float(accuracy),
                            "prec": float(precision),
                            "rec": float(recall),
                            "f1": float(f1)
                        }
                    )
        except Exception as e:
            log_error(f"Failed to save model metrics: {e}")
    else:
        log_info("Skipping evaluation (Model is new and not yet fitted).")

    # Incrementally train the supervised model with all new logs
    supervised_model.partial_fit(X_eval, y_new, classes=np.array([0, 1]))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_supervised_path_str = f"model/sgd_embedder_{timestamp}.pkl"
    joblib.dump(supervised_model, os.path.join(settings.PROJECT_ROOT, new_supervised_path_str))
    log_success("Supervised model successfully updated and saved.")

    # --- 4. Update the UNSUPERVISED Model ---
    log_info("--- Updating Unsupervised Model (autoencoder_model.keras) ---")
    # We only retrain the autoencoder on the NORMAL logs from the new batch
    normal_logs_mask = (y_new == 0)
    X_normal_eval = X_eval[normal_logs_mask]

    if len(X_normal_eval) < 10:
        log_warn(f"Not enough new normal logs ({len(X_normal_eval)}) to train/refine the Autoencoder. Skipping.")
        new_autoencoder_path_str = active_models["autoencoder_model"]
    else:
        active_autoencoder_path = active_models["autoencoder_model"]
        if os.path.exists(active_autoencoder_path):
            log_info("Loading active autoencoder model...")
            unsupervised_model = tf.keras.models.load_model(active_autoencoder_path)
        else:
            log_warn(f"No autoencoder model found at {active_autoencoder_path}.. Creating a new one.")
            unsupervised_model = create_new_autoencoder(input_dim=embedding_dim)

        log_info(f"Found {len(X_normal_eval)} new normal logs to refine the Autoencoder.")
        # Continue training the autoencoder for a few epochs on the new normal data
        # unsupervised_model = tf.keras.models.load_model(AUTOENCODER_PATH)
        unsupervised_model.fit(X_normal_eval, X_normal_eval,
                               epochs=10,
                               batch_size=32,
                               shuffle=True,
                               verbose=0) # verbose=0 for cleaner output
        try:
            new_autoencoder_path_str = f"model/autoencoder_model_{timestamp}.keras"
            unsupervised_model.save(os.path.join(settings.PROJECT_ROOT, new_autoencoder_path_str))
            log_success(f"New autoencoder model saved to: {new_autoencoder_path_str}")
        except Exception as e:
            log_error(f"CRITICAL: Failed to save the autoencoder model! Error: {e}")
            # Do not proceed if saving fails, as it could corrupt the file
            return

        # OPTIONAL BUT RECOMMENDED: Recalculate the threshold
        log_info("Recalculating anomaly threshold...")
        all_normal_query = "SELECT content FROM logs WHERE final_label = 0 ORDER BY RANDOM() LIMIT 20000"
        engine = create_engine(settings.DATABASE_URL)
        df_all_normal = pd.read_sql_query(all_normal_query, engine)
        # engine.close()
        all_normal_embeddings = embedder.encode(df_all_normal['content'].astype(str).tolist(), show_progress_bar=False)
        reconstructions = unsupervised_model.predict(all_normal_embeddings, verbose=0)
        train_loss = tf.keras.losses.mae(reconstructions, all_normal_embeddings)
        new_threshold = np.mean(train_loss) + 3 * np.std(train_loss)
        
        with open(settings.THRESHOLD_PATH, 'w') as f:
            json.dump({'threshold': float(new_threshold)}, f)
        log_success(f"Autoencoder model refined and new threshold ({new_threshold:.6f}) saved.")

    # --- 5. Update the Model Registry ---
    log_info("Updating model registry...")
    
    # Calculate metadata
    training_metadata = {
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "batch_sample_count": len(new_logs_df),
        "supervised_metrics": {
            "accuracy": float(accuracy) if 'accuracy' in locals() else None,
            "f1": float(f1) if 'f1' in locals() else None
        } if not is_new_model else "Initial Training"
    }

    with open(registry_path, 'r+') as f:
        registry = json.load(f)
        registry["supervised_model"] = new_supervised_path_str
        registry["autoencoder_model"] = new_autoencoder_path_str
        registry["metadata"] = training_metadata
        
        # Keep version history (last 5)
        if "history" not in registry:
            registry["history"] = []
        
        history_entry = {
            "timestamp": timestamp,
            "supervised": new_supervised_path_str,
            "autoencoder": new_autoencoder_path_str,
            "metrics": training_metadata["supervised_metrics"]
        }
        registry["history"].insert(0, history_entry)
        registry["history"] = registry["history"][:5]
        
        f.seek(0)
        json.dump(registry, f, indent=4)
        f.truncate()
    log_success("Model registry updated with metadata and version history.")

    # --- 6. Update Checkpoint ---
    with open(settings.CHECKPOINT_FILE, "w") as f:
        f.write(str(latest_id_in_batch))
    log_success(f"Checkpoint updated. Last processed log ID: {latest_id_in_batch}")

    # --- 7. Clean Up Old Model Versions ---
    log_info("Cleaning up old model versions...")
    cleanup_old_models("sgd_embedder_")
    cleanup_old_models("autoencoder_model_")

if __name__ == "__main__":
    trigger_model_update()
