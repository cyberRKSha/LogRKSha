# # train.py
# import os
# import pandas as pd
# import joblib
# import numpy as np
# from sentence_transformers import SentenceTransformer
# import sqlite3

# # --- (Keep your configuration and logging helpers) ---
# BASE_DIR = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux" # Example path
# DATABASE_FILE = os.path.join(BASE_DIR, "log_database.db")
# MODEL_PATH = os.path.join(BASE_DIR, "model/sgd_embedder.pkl")
# EMBEDDER_PATH = os.path.join(BASE_DIR, "model/sentence_embedder.pkl")
# CHECKPOINT_FILE = os.path.join(BASE_DIR, "model/last_processed_log_id.txt") # Checkpoint by ID now


# def log_info(msg): print(f"\033[94mℹ️ {msg}\033[0m")
# def log_success(msg): print(f"\032[92m✅ {msg}\033[0m")
# def log_error(msg): print(f"\033[91m❗ {msg}\033[0m")

# # --- NEW: Fetch all reviewed data from the database for training ---
# log_info(f"Connecting to database: {DATABASE_FILE}")
# conn = sqlite3.connect(DATABASE_FILE)
# query = "SELECT content, final_label FROM logs WHERE is_reviewed = 1"
# df = pd.read_sql_query(query, conn)
# conn.close()

# if df.empty or 'final_label' not in df.columns:
#     log_error("No reviewed data found in the database. Please review some logs first. Exiting.")
#     exit(1)

# # Rename column for consistency
# df.rename(columns={'final_label': 'label'}, inplace=True)

# log_info("🔄 Loading sentence embedder...")
# embedder = joblib.load(EMBEDDER_PATH)

# log_info(f"📦 Training on {len(df)} reviewed logs "
#          f"(Normal: {(df['label']==0).sum()}, Anomaly: {(df['label']==1).sum()})")

# log_info("🔢 Generating embeddings for all training data...")
# X = embedder.encode(df['content'].astype(str).tolist(), show_progress_bar=True)
# y = df['label'].astype(int).values

# # Shuffle the data
# idx = np.random.permutation(len(y))
# X = X[idx]
# y = y[idx]

# # Create a fresh model
# from sklearn.linear_model import SGDClassifier
# model = SGDClassifier(loss='log_loss', max_iter=1000, tol=1e-3, random_state=42)

# log_info("🧠 Training fresh model from scratch...")
# model.fit(X, y) # Use fit for training from scratch

# joblib.dump(model, MODEL_PATH)
# log_success(f"✅ New model saved to: {MODEL_PATH}")

# # Reset checkpoint since we trained on everything
# if os.path.exists(CHECKPOINT_FILE):
#     os.remove(CHECKPOINT_FILE)
# log_info("📌 Checkpoint reset.")





































# train.py (Updated for Database and Hybrid System)
import os
import pandas as pd
import joblib
import numpy as np
from sklearn.linear_model import SGDClassifier
from sentence_transformers import SentenceTransformer
import sqlite3

# --- Configuration ---
BASE_DIR = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux"
DATABASE_FILE = os.path.join(BASE_DIR, "log_database.db")
MODEL_PATH = os.path.join(BASE_DIR, "model/sgd_embedder.pkl")
EMBEDDER_PATH = os.path.join(BASE_DIR, "model/sentence_embedder.pkl")
CHECKPOINT_FILE = os.path.join(BASE_DIR, "model/last_processed_log_id.txt")

# --- Logging Helpers ---
def log_info(msg): print(f"\033[94mℹ️ {msg}\033[0m")
def log_success(msg): print(f"\033[92m✅ {msg}\033[0m")
def log_error(msg): print(f"\033[91m❗ {msg}\033[0m")

def train_from_scratch():
    """
    Trains the supervised SGDClassifier model from scratch using all
    human-reviewed data in the database.
    """
    log_info(f"Connecting to database: {DATABASE_FILE}")
    conn = sqlite3.connect(DATABASE_FILE)
    # Fetch ALL human-reviewed logs to train a fresh model
    query = "SELECT content, final_label FROM logs WHERE is_reviewed = 1"
    df = pd.read_sql_query(query, conn)
    conn.close()

    if df.empty:
        log_error("No reviewed data found in the database. Please review logs before training. Exiting.")
        return

    # Rename column for consistency with the model's expected input
    df.rename(columns={'final_label': 'label'}, inplace=True)
    log_info(f"Fetched {len(df)} reviewed logs for training.")

    log_info("Loading sentence embedder...")
    embedder = joblib.load(EMBEDDER_PATH)

    log_info(f"Generating embeddings for all {len(df)} logs...")
    # This model is trained only on the semantic embeddings
    X = embedder.encode(df['content'].astype(str).tolist(), show_progress_bar=True)
    y = df['label'].astype(int).values

    # Shuffle the data for robust training
    idx = np.random.permutation(len(y))
    X_train = X[idx]
    y_train = y[idx]

    # Create a fresh model instance
    model = SGDClassifier(loss='log_loss', max_iter=1000, tol=1e-3, random_state=42)

    log_info("🧠 Training fresh supervised model from scratch...")
    model.fit(X_train, y_train)

    joblib.dump(model, MODEL_PATH)
    log_success(f"✅ New supervised model saved to: {MODEL_PATH}")

    # After a full retrain, the update checkpoint should be reset to the latest ID
    # to prevent the update.py script from reprocessing old data.
    conn = sqlite3.connect(DATABASE_FILE)
    # Safely get the max ID, handling the case where the table might be empty
    latest_id_df = pd.read_sql_query("SELECT MAX(id) FROM logs WHERE is_reviewed = 1", conn)
    conn.close()
    
    latest_id = latest_id_df.iloc[0,0] if not latest_id_df.empty else 0
    
    with open(CHECKPOINT_FILE, "w") as f:
        f.write(str(latest_id))
    log_info(f"📌 Checkpoint has been updated to the latest reviewed log ID: {latest_id}")

if __name__ == "__main__":
    train_from_scratch()
