# # update.py
# import os
# import pandas as pd
# import joblib
# import numpy as np
# from sklearn.metrics import confusion_matrix, accuracy_score, classification_report
# from sentence_transformers import SentenceTransformer
# import sqlite3

# # --- Configuration: File Paths ---
# BASE_DIR = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux" # Example path
# DATABASE_FILE = os.path.join(BASE_DIR, "log_database.db")
# MODEL_PATH = os.path.join(BASE_DIR, "model/sgd_embedder.pkl")
# EMBEDDER_PATH = os.path.join(BASE_DIR, "model/sentence_embedder.pkl")
# CHECKPOINT_FILE = os.path.join(BASE_DIR, "model/last_processed_log_id.txt") # Checkpoint by ID now

# # --- (Keep your logging helpers) ---
# def log_info(msg): print(f"\033[94mℹ️ {msg}\033[0m")
# def log_success(msg): print(f"\032[92m✅ {msg}\033[0m")
# def log_warn(msg): print(f"\033[93m⚠️ {msg}\033[0m")
# def log_report(report): print(f"\033[96m{report}\033[0m")
# def log_error(msg): print(f"\033[91m❗ {msg}\033[0m")

# def run_update():
#     """
#     Main function to evaluate and incrementally update the model.
#     """
#     log_info("Starting model update process...")
#     # --- (Keep your pre-flight checks for model files) ---

#     log_info("Starting model update process...")
#     for path in [DATABASE_FILE, MODEL_PATH, EMBEDDER_PATH]:
#         if not os.path.exists(path):
#             log_error(f"Required file not found: {path}. Please run train.py first. Exiting.")
#             return

#     log_info("Loading existing model and embedder...")
#     model = joblib.load(MODEL_PATH)
#     embedder = joblib.load(EMBEDDER_PATH)

#     # --- Find New Data Using Checkpoint ---
#     last_processed_id = 0
#     if os.path.exists(CHECKPOINT_FILE):
#         with open(CHECKPOINT_FILE, "r") as f:
#             try: last_processed_id = int(f.read().strip())
#             except (ValueError, IOError): last_processed_id = 0

#     # --- NEW: Fetch new, reviewed data from the database ---
#     conn = sqlite3.connect(DATABASE_FILE)
#     query = f"SELECT id, content, final_label FROM logs WHERE is_reviewed = 1 AND id > {last_processed_id}"
#     new_logs_df = pd.read_sql_query(query, conn)
#     conn.close()

#     if new_logs_df.empty:
#         log_success("Model is already up-to-date. No new reviewed logs to train on.")
#         return

#     # Get the ID of the last log we are about to process
#     latest_id_in_batch = new_logs_df['id'].max()

#     log_info(f"Found {len(new_logs_df)} new reviewed logs to process.")

#     log_info("Cleaning and mapping labels...")
#     # Define a mapping for all possible correct values (string and int)
#     label_map = {'normal': 0, 'anomaly': 1, 0: 0, 1: 1, '0': 0, '1': 1}

#     # Use the .map() function to apply this mapping.
#     # This safely converts 'normal' to 0, 'anomaly' to 1, and keeps existing integers as they are.
#     new_logs_df['final_label'] = new_logs_df['final_label'].map(label_map)

#     # Drop any rows where the label could not be mapped (e.g., it was NaN or some other string)
#     new_logs_df.dropna(subset=['final_label'], inplace=True)

#     # Now, the 'final_label' column is clean and ready for type conversion.
#     X_new_text = new_logs_df['content'].astype(str).tolist()
#     y_new = new_logs_df['final_label'].astype(int).values

#     defined_labels = [0, 1]

#     # --- (Keep your model evaluation logic as is) ---
#     log_info("Evaluating current model performance on the new batch...")
#     X_eval = embedder.encode(X_new_text, show_progress_bar=True)
#     y_pred = model.predict(X_eval)
#     report = classification_report(y_new, y_pred, target_names=['Normal (0)', 'Anomaly (1)'], zero_division=0)
#     accuracy = accuracy_score(y_new, y_pred)
#     cm = confusion_matrix(y_new, y_pred, labels=defined_labels)

#     print("\n" + "="*50)
#     log_info("Performance of CURRENT model on the NEW data batch:")    
#     log_report(f"Accuracy on new batch: {accuracy:.2%}")
#     log_report(f"Confusion Matrix (Labels: {defined_labels}):\n{cm}")
#     log_report("Classification Report on new data:\n" + report)
    
#     # --- Update (Incrementally Train) the Model ---
#     log_info("Proceeding with model update...")
#     idx = np.random.permutation(len(y_new))
#     X_to_fit = X_eval[idx]
#     y_to_fit = y_new[idx]

#     model.partial_fit(X_to_fit, y_to_fit, classes=np.array([0, 1]))
#     joblib.dump(model, MODEL_PATH)
#     log_success(f"Model successfully updated and saved to: {MODEL_PATH}")

#     # --- Update Checkpoint ---
#     with open(CHECKPOINT_FILE, "w") as f:
#         f.write(str(latest_id_in_batch))
#     log_success(f"Checkpoint updated. Last processed log ID: {latest_id_in_batch}")

# if __name__ == "__main__":
#     run_update()


























































































# update.py (ULTIMATE HYBRID VERSION)
import os
import pandas as pd
import joblib
import numpy as np
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix
from sentence_transformers import SentenceTransformer
import sqlite3
import tensorflow as tf
import json

# --- Configuration ---
BASE_DIR = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux"
DATABASE_FILE = os.path.join(BASE_DIR, "log_database.db")
# Models
EMBEDDER_PATH = os.path.join(BASE_DIR, "model/sentence_embedder.pkl")
SUPERVISED_MODEL_PATH = os.path.join(BASE_DIR, "model/sgd_embedder.pkl")
AUTOENCODER_PATH = os.path.join(BASE_DIR, "model/autoencoder_model.keras")
THRESHOLD_PATH = os.path.join(BASE_DIR, "model/autoencoder_threshold.json")
# Checkpoint
CHECKPOINT_FILE = os.path.join(BASE_DIR, "model/last_processed_log_id.txt")

# --- Logging Helpers ---
def log_info(msg): print(f"\033[94mℹ️ {msg}\033[0m")
def log_success(msg): print(f"\033[92m✅ {msg}\033[0m")
def log_warn(msg): print(f"\033[93m⚠️ {msg}\033[0m")
def log_report(report): print(f"\033[96m{report}\033[0m")
def log_error(msg): print(f"\033[91m❗ {msg}\033[0m")

def run_hybrid_update():
    """
    Main function to incrementally update both the supervised and unsupervised models.
    """
    log_info("Starting HYBRID model update process...")
    
    # --- 1. Load all models and data ---
    log_info("Loading existing models and embedder...")
    supervised_model = joblib.load(SUPERVISED_MODEL_PATH)
    unsupervised_model = tf.keras.models.load_model(AUTOENCODER_PATH)
    embedder = joblib.load(EMBEDDER_PATH)

    # --- 2. Find new, reviewed data using the checkpoint ---
    last_processed_id = 0
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, "r") as f:
            try: last_processed_id = int(f.read().strip())
            except (ValueError, IOError): last_processed_id = 0

    conn = sqlite3.connect(DATABASE_FILE)
    query = f"SELECT id, content, final_label FROM logs WHERE is_reviewed = 1 AND id > {last_processed_id}"
    new_logs_df = pd.read_sql_query(query, conn)
    conn.close()

    if new_logs_df.empty:
        log_success("All models are already up-to-date. No new reviewed logs to train on.")
        return

    latest_id_in_batch = new_logs_df['id'].max()
    log_info(f"Found {len(new_logs_df)} new reviewed logs to process.")

    # --- 3. Generate Embeddings for the new data ---
    log_info("Generating embeddings for the new batch...")
    X_new_text = new_logs_df['content'].astype(str).tolist()
    X_eval = embedder.encode(X_new_text, show_progress_bar=True)
    y_new = new_logs_df['final_label'].astype(int).values

    # --- 4. Update the SUPERVISED Model ---
    log_info("--- Updating Supervised Model (sgd_embedder.pkl) ---")
    # Evaluate performance before updating
    y_pred = supervised_model.predict(X_eval)
    accuracy = accuracy_score(y_new, y_pred)
    log_report(f"Accuracy of OLD supervised model on new data: {accuracy:.2%}")

    # Incrementally train the supervised model with all new logs
    supervised_model.partial_fit(X_eval, y_new, classes=np.array([0, 1]))
    joblib.dump(supervised_model, SUPERVISED_MODEL_PATH)
    log_success("Supervised model successfully updated and saved.")

    # --- 5. Update the UNSUPERVISED Model ---
    log_info("--- Updating Unsupervised Model (autoencoder_model.keras) ---")
    # We only retrain the autoencoder on the NORMAL logs from the new batch
    normal_logs_mask = (y_new == 0)
    X_normal_eval = X_eval[normal_logs_mask]

    if len(X_normal_eval) > 0:
        log_info(f"Found {len(X_normal_eval)} new normal logs to refine the Autoencoder.")
        # Continue training the autoencoder for a few epochs on the new normal data
        unsupervised_model.fit(X_normal_eval, X_normal_eval,
                               epochs=10,
                               batch_size=32,
                               shuffle=True,
                               verbose=0) # verbose=0 for cleaner output
        unsupervised_model.save(AUTOENCODER_PATH)

        # OPTIONAL BUT RECOMMENDED: Recalculate the threshold
        log_info("Recalculating anomaly threshold...")
        all_normal_query = "SELECT content FROM logs WHERE final_label = 0 ORDER BY RANDOM() LIMIT 20000"
        conn = sqlite3.connect(DATABASE_FILE)
        df_all_normal = pd.read_sql_query(all_normal_query, conn)
        conn.close()
        all_normal_embeddings = embedder.encode(df_all_normal['content'].astype(str).tolist(), show_progress_bar=False)
        reconstructions = unsupervised_model.predict(all_normal_embeddings, verbose=0)
        train_loss = tf.keras.losses.mae(reconstructions, all_normal_embeddings)
        new_threshold = np.mean(train_loss) + 3 * np.std(train_loss)
        
        with open(THRESHOLD_PATH, 'w') as f:
            json.dump({'threshold': new_threshold}, f)

        log_success(f"Unsupervised model refined and new threshold ({new_threshold:.6f}) saved.")
    else:
        log_warn("No new normal logs found in this batch. Skipping Autoencoder update.")

    # --- 6. Update Checkpoint ---
    with open(CHECKPOINT_FILE, "w") as f:
        f.write(str(latest_id_in_batch))
    log_success(f"Checkpoint updated. Last processed log ID: {latest_id_in_batch}")

if __name__ == "__main__":
    run_hybrid_update()
