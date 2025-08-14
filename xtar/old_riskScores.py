import os
import sqlite3
import pandas as pd
import joblib
import numpy as np
import tensorflow as tf
import json
from tqdm import tqdm # A library for progress bars

# --- Configuration ---
# This creates a path relative to the script's location
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATABASE_FILE = os.path.join(BASE_DIR, "log_database.db")
EMBEDDER_PATH = os.path.join(BASE_DIR, "model/sentence_embedder.pkl")
AUTOENCODER_PATH = os.path.join(BASE_DIR, "model/autoencoder_model.keras")
THRESHOLD_PATH = os.path.join(BASE_DIR, "model/autoencoder_threshold.json")

# --- Logging Helpers ---
def log_info(msg): print(f"\033[94mℹ️ {msg}\033[0m")
def log_success(msg): print(f"\032[92m✅ {msg}\033[0m")
def log_error(msg): print(f"\033[91m❗ {msg}\033[0m")

def sanitize_string(text):
    """Safely decodes and re-encodes a string to remove invalid characters."""
    if isinstance(text, str):
        return text.encode('utf-8', 'replace').decode('utf-8')
    return text

def fix_and_backfill_scores():
    """
    Cleans corrupted risk_score data and then calculates and updates
    scores for historical logs.
    """
    log_info("--- Starting Database Repair and Risk Score Backfill ---")

    # --- 1. Load Models ---
    log_info("Loading models and threshold...")
    try:
        embedder = joblib.load(EMBEDDER_PATH)
        unsupervised_model = tf.keras.models.load_model(AUTOENCODER_PATH)
        with open(THRESHOLD_PATH, 'r') as f:
            unsupervised_threshold = json.load(f)['threshold']
        log_success("Models loaded successfully.")
    except Exception as e:
        log_error(f"Failed to load models. Please ensure they exist. Error: {e}")
        return

    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    # --- 2. Clean Corrupted Data ---
    log_info("Cleaning any corrupted data from the risk_score column...")
    # This resets any non-numeric/BLOB data to 0.0 for all anomalies.
    cursor.execute("UPDATE logs SET risk_score = 0.0 WHERE final_label = 1;")
    conn.commit()
    log_success("Corrupted data has been cleaned.")

    # --- 3. Fetch Unscored Anomaly Logs ---
    log_info("Fetching historical anomaly logs to score...")
    query = "SELECT id, content FROM logs WHERE final_label = 1 AND risk_score = 0.0"
    df_unscored = pd.read_sql_query(query, conn)
    
    if df_unscored.empty:
        log_success("No unscored historical logs found. Database is up-to-date.")
        conn.close()
        return
    
    log_info(f"Found {len(df_unscored)} anomaly logs to score.")

    # --- 4. Process in Batches, Sanitize, and Calculate Scores ---
    batch_size = 256
    updates = []

    for i in tqdm(range(0, len(df_unscored), batch_size), desc="Calculating Scores"):
        batch_df = df_unscored.iloc[i:i+batch_size]
        
        # Sanitize the content before sending to the model
        clean_content = [sanitize_string(log) for log in batch_df['content']]
        
        embeddings = embedder.encode(clean_content)
        reconstructions = unsupervised_model.predict(embeddings, verbose=0)
        losses = tf.keras.losses.mae(reconstructions, embeddings).numpy()
        
        risk_scores = np.minimum(1.0, losses / unsupervised_threshold)
        
        # Ensure data is in the correct format (float, int) for the database
        batch_updates = [(float(score), int(log_id)) for score, log_id in zip(risk_scores, batch_df['id'])]
        updates.extend(batch_updates)

    # --- 5. Update Database Safely ---
    if not updates:
        log_info("No scores were calculated. Exiting.")
        conn.close()
        return

    log_info(f"Updating {len(updates)} records in the database...")
    
    # Use executemany for a fast, safe, bulk update
    cursor.executemany("UPDATE logs SET risk_score = ? WHERE id = ?", updates)
    conn.commit()
    conn.close()

    log_success("✅ Successfully repaired and backfilled risk scores for all historical logs!")

if __name__ == "__main__":
    fix_and_backfill_scores()