# #!/usr/bin/env python3
# import os
# import pandas as pd
# import joblib
# import numpy as np
# from sklearn.metrics import confusion_matrix, accuracy_score, classification_report
# from sentence_transformers import SentenceTransformer

# # --- Configuration: File Paths ---
# BASE_DIR = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux"
# REAL_LOG_CSV = os.path.join(BASE_DIR, "logs/real_log.csv")
# MODEL_PATH = os.path.join(BASE_DIR, "model/sgd_embedder.pkl")
# EMBEDDER_PATH = os.path.join(BASE_DIR, "model/sentence_embedder.pkl")
# CHECKPOINT_FILE = os.path.join(BASE_DIR, "model/last_update_checkpoint.txt")

# # --- Logging Helpers ---
# def log_info(msg): print(f"\033[94mℹ️ {msg}\033[0m")
# def log_success(msg): print(f"\033[92m✅ {msg}\033[0m")
# def log_warn(msg): print(f"\033[93m⚠️ {msg}\033[0m")
# def log_error(msg): print(f"\033[91m❗ {msg}\033[0m")
# def log_report(report): print(f"\033[96m{report}\033[0m")

# def run_update():
#     """
#     Main function to evaluate and incrementally update the model.
#     """
#     # --- 1. Pre-flight Checks ---
#     log_info("Starting model update process...")
#     for path in [REAL_LOG_CSV, MODEL_PATH, EMBEDDER_PATH]:
#         if not os.path.exists(path):
#             log_error(f"Required file not found: {path}. Please run train.py first. Exiting.")
#             return

#     # --- 2. Load Model and Data ---
#     log_info("Loading existing model, embedder, and log data...")
#     try:
#         model = joblib.load(MODEL_PATH)
#         embedder = joblib.load(EMBEDDER_PATH)
#         df_real = pd.read_csv(REAL_LOG_CSV)
#     except Exception as e:
#         log_error(f"Failed to load a required file: {e}. Exiting.")
#         return

#     if df_real.empty or 'label' not in df_real.columns:
#         log_warn("real_log.csv is empty or missing 'label' column. Nothing to update.")
#         return

#     # --- 3. Find New Data Using Checkpoint ---
#     last_processed_row = 0
#     if os.path.exists(CHECKPOINT_FILE):
#         with open(CHECKPOINT_FILE, "r") as f:
#             try:
#                 last_processed_row = int(f.read().strip())
#             except ValueError:
#                 log_warn("Checkpoint file is invalid. Assuming no rows have been processed.")

#     new_logs_df = df_real.iloc[last_processed_row:].copy()

#     if new_logs_df.empty:
#         log_success("Model is already up-to-date. No new logs to train on.")
#         return

#     # --- 4. Clean Data and Report Breakdown ---
#     new_logs_df['label'] = pd.to_numeric(new_logs_df['label'], errors='coerce').fillna(0)
    
#     normal_count = (new_logs_df['label'] == 0).sum()
#     anomaly_count = (new_logs_df['label'] == 1).sum()

#     log_info(f"Found {len(new_logs_df)} new logs to process (Normal: {normal_count}, Anomaly: {anomaly_count}).")

#     X_new_text = new_logs_df['content'].astype(str).tolist()
#     y_new = new_logs_df['label'].astype(int).values

#     # --- 5. Evaluate Current Model on New Data ---
#     log_info("Generating embeddings for the new batch to evaluate current model performance...")
#     X_eval = embedder.encode(X_new_text, show_progress_bar=True)
#     y_pred = model.predict(X_eval)

#     defined_labels = [0, 1] 
    
#     # Diagnostic prints to help debug in the future
#     # log_info(f"Debug Info - y_new (true labels) - Type: {type(y_new)}, Shape: {y_new.shape}, Unique values: {np.unique(y_new)}")
#     # log_info(f"Debug Info - y_pred (predicted) - Type: {type(y_pred)}, Shape: {y_pred.shape}, Unique values: {np.unique(y_pred)}")

#     cm = confusion_matrix(y_new, y_pred, labels=defined_labels)
#     # --- END: THE FIX ---
    
#     accuracy = accuracy_score(y_new, y_pred)
#     report = classification_report(y_new, y_pred, target_names=['Normal (0)', 'Anomaly (1)'], labels=defined_labels, zero_division=0)
    
#     print("\n" + "="*50)
#     log_info("Performance of CURRENT model on the NEW data batch:")
#     log_report(f"Accuracy on new batch: {accuracy:.2%}")
#     log_report(f"Confusion Matrix (Labels: {defined_labels}):\n{cm}")
#     log_report("Classification Report:")
#     log_report(report)
#     print("="*50 + "\n")

#     # --- 6. Update (Incrementally Train) the Model ---
#     log_info("Proceeding with model update using the new data...")
    
#     idx = np.random.permutation(len(y_new))
#     X_to_fit = X_eval[idx]
#     y_to_fit = y_new[idx]
    
#     model.partial_fit(X_to_fit, y_to_fit, classes=np.array([0, 1]))
#     joblib.dump(model, MODEL_PATH)
#     log_success(f"Model successfully updated and saved to: {MODEL_PATH}")

#     # --- 7. Update Checkpoint ---
#     new_checkpoint_row = last_processed_row + len(new_logs_df)
#     with open(CHECKPOINT_FILE, "w") as f:
#         f.write(str(new_checkpoint_row))
#     log_success(f"Checkpoint updated. Total rows processed: {new_checkpoint_row}")

# if __name__ == "__main__":
#     run_update()

































# update.py
import os
import pandas as pd
import joblib
import numpy as np
from sklearn.metrics import confusion_matrix, accuracy_score, classification_report
from sentence_transformers import SentenceTransformer
import sqlite3

# --- Configuration: File Paths ---
BASE_DIR = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux" # Example path
DATABASE_FILE = os.path.join(BASE_DIR, "log_database.db")
MODEL_PATH = os.path.join(BASE_DIR, "model/sgd_embedder.pkl")
EMBEDDER_PATH = os.path.join(BASE_DIR, "model/sentence_embedder.pkl")
CHECKPOINT_FILE = os.path.join(BASE_DIR, "model/last_processed_log_id.txt") # Checkpoint by ID now

# --- (Keep your logging helpers) ---
def log_info(msg): print(f"\033[94mℹ️ {msg}\033[0m")
def log_success(msg): print(f"\032[92m✅ {msg}\033[0m")
def log_warn(msg): print(f"\033[93m⚠️ {msg}\033[0m")
def log_report(report): print(f"\033[96m{report}\033[0m")
def log_error(msg): print(f"\033[91m❗ {msg}\033[0m")

def run_update():
    """
    Main function to evaluate and incrementally update the model.
    """
    log_info("Starting model update process...")
    # --- (Keep your pre-flight checks for model files) ---

    log_info("Starting model update process...")
    for path in [DATABASE_FILE, MODEL_PATH, EMBEDDER_PATH]:
        if not os.path.exists(path):
            log_error(f"Required file not found: {path}. Please run train.py first. Exiting.")
            return

    log_info("Loading existing model and embedder...")
    model = joblib.load(MODEL_PATH)
    embedder = joblib.load(EMBEDDER_PATH)

    # --- Find New Data Using Checkpoint ---
    last_processed_id = 0
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, "r") as f:
            try: last_processed_id = int(f.read().strip())
            except (ValueError, IOError): last_processed_id = 0

    # --- NEW: Fetch new, reviewed data from the database ---
    conn = sqlite3.connect(DATABASE_FILE)
    query = f"SELECT id, content, final_label FROM logs WHERE is_reviewed = 1 AND id > {last_processed_id}"
    new_logs_df = pd.read_sql_query(query, conn)
    conn.close()

    if new_logs_df.empty:
        log_success("Model is already up-to-date. No new reviewed logs to train on.")
        return

    # Get the ID of the last log we are about to process
    latest_id_in_batch = new_logs_df['id'].max()

    log_info(f"Found {len(new_logs_df)} new reviewed logs to process.")

    log_info("Cleaning and mapping labels...")
    # Define a mapping for all possible correct values (string and int)
    label_map = {'normal': 0, 'anomaly': 1, 0: 0, 1: 1, '0': 0, '1': 1}

    # Use the .map() function to apply this mapping.
    # This safely converts 'normal' to 0, 'anomaly' to 1, and keeps existing integers as they are.
    new_logs_df['final_label'] = new_logs_df['final_label'].map(label_map)

    # Drop any rows where the label could not be mapped (e.g., it was NaN or some other string)
    new_logs_df.dropna(subset=['final_label'], inplace=True)

    # Now, the 'final_label' column is clean and ready for type conversion.
    X_new_text = new_logs_df['content'].astype(str).tolist()
    y_new = new_logs_df['final_label'].astype(int).values

    defined_labels = [0, 1]

    # --- (Keep your model evaluation logic as is) ---
    log_info("Evaluating current model performance on the new batch...")
    X_eval = embedder.encode(X_new_text, show_progress_bar=True)
    y_pred = model.predict(X_eval)
    report = classification_report(y_new, y_pred, target_names=['Normal (0)', 'Anomaly (1)'], zero_division=0)
    accuracy = accuracy_score(y_new, y_pred)
    cm = confusion_matrix(y_new, y_pred, labels=defined_labels)

    print("\n" + "="*50)
    log_info("Performance of CURRENT model on the NEW data batch:")    
    log_report(f"Accuracy on new batch: {accuracy:.2%}")
    log_report(f"Confusion Matrix (Labels: {defined_labels}):\n{cm}")
    log_report("Classification Report on new data:\n" + report)
    
    # --- Update (Incrementally Train) the Model ---
    log_info("Proceeding with model update...")
    idx = np.random.permutation(len(y_new))
    X_to_fit = X_eval[idx]
    y_to_fit = y_new[idx]

    model.partial_fit(X_to_fit, y_to_fit, classes=np.array([0, 1]))
    joblib.dump(model, MODEL_PATH)
    log_success(f"Model successfully updated and saved to: {MODEL_PATH}")

    # --- Update Checkpoint ---
    with open(CHECKPOINT_FILE, "w") as f:
        f.write(str(latest_id_in_batch))
    log_success(f"Checkpoint updated. Last processed log ID: {latest_id_in_batch}")

if __name__ == "__main__":
    run_update()