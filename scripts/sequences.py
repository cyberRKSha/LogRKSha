# scripts/sequences.py

import os
import re
import sqlite3
import dill
import joblib
import pandas as pd
import numpy as np
from datetime import timedelta
from sentence_transformers import SentenceTransformer
from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig

# --- Configuration ---
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATABASE_FILE = os.path.join(PROJECT_ROOT, "log_database.db")
MODEL_DIR = os.path.join(PROJECT_ROOT, "model")
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
EMBEDDER_PATH = os.path.join(PROJECT_ROOT, "model/sentence_embedder.pkl")
DRAIN_MODEL_PATH = os.path.join(PROJECT_ROOT, "model/drain_miner.pkl")

os.makedirs(DATA_DIR, exist_ok=True)

# The file where we will save our final prepared data
OUTPUT_FILE = os.path.join(DATA_DIR, "training_sequences.pkl")
LOG_ID_START = 50000  # The ID to start fetching logs from

def fetch_logs_from_db(start_id: int) -> pd.DataFrame:
    print(f"Connecting to database at {DATABASE_FILE}...")
    try:
        con = sqlite3.connect(DATABASE_FILE)
        query = f"SELECT timestamp, content, final_label FROM logs WHERE id > {start_id} ORDER BY timestamp ASC"
        df = pd.read_sql_query(query, con)
        con.close()
        df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
        df.dropna(subset=['timestamp', 'content'], inplace=True)
        print(f"✅ Fetched {len(df)} logs from the database.")
        return df
    except Exception as e:
        print(f"❗ Error fetching logs: {e}")
        return pd.DataFrame()

def extract_ip(log_line: str) -> str:
    """Extracts the first IP address found in a log line."""
    match = re.search(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", log_line)
    return match.group(0) if match else "NO_IP"

def group_into_sequences(df: pd.DataFrame, max_session_time_minutes=5) -> list:
    """
    Groups a DataFrame of logs into sequences based on IP address and a time window.
    """
    print("Grouping logs into session sequences...")
    df['ip'] = df['content'].apply(extract_ip)
    
    sequences = []
    # Group the DataFrame by the extracted IP address
    for ip, group in df.groupby('ip'):
        if ip == "NO_IP":
            continue # Skip logs where no IP could be found

        group = group.sort_values(by='timestamp')
        session_start_time = None
        current_sequence = []
        current_labels = []

        for index, row in group.iterrows():
            if not session_start_time or (row['timestamp'] - session_start_time) > timedelta(minutes=max_session_time_minutes):
                # If a session exists and is long enough, save it
                if len(current_sequence) > 1:
                    # A sequence is an anomaly if any log in it is an anomaly
                    label = 1 if any(lbl == 1 for lbl in current_labels) else 0
                    sequences.append({
                        "sequence_embeddings": np.array(current_sequence),
                        "label": label
                    })
                # Start a new session
                current_sequence = [row['embedding']]
                current_labels = [row['final_label']]
                session_start_time = row['timestamp']
            else:
                # Append to the current session
                current_sequence.append(row['embedding'])
                current_labels.append(row['final_label'])
        
        # Add the last remaining session
        if len(current_sequence) > 1:
            label = 1 if any(lbl == 1 for lbl in current_labels) else 0
            sequences.append({
                "sequence_embeddings": np.array(current_sequence),
                "label": label
            })
            
    print(f"✅ Created {len(sequences)} sequences.")
    return sequences

if __name__ == "__main__":
    df_logs = fetch_logs_from_db(LOG_ID_START)

    if not df_logs.empty:

        # 1. Create and save the official Sentence Transformer model
        print("Initializing Sentence Transformer model...")
        embedder = SentenceTransformer('all-MiniLM-L6-v2') # This model produces 384 dimensions
        # joblib.dump(embedder, EMBEDDER_PATH)
        embedder.save(EMBEDDER_PATH)
        print(f"✅ Sentence embedder saved to {EMBEDDER_PATH}")

        # 2. Generate embeddings using this official model
        print("Generating embeddings for all log messages...")
        embeddings = embedder.encode(df_logs['content'].tolist(), show_progress_bar=True)
        df_logs['embedding'] = list(embeddings)

        # 1. Create and train a Drain miner on the same logs
        print("Training Drain miner for cluster naming...")
        config = TemplateMinerConfig()
        config.load(os.path.join(PROJECT_ROOT, "drain3.ini"))
        miner = TemplateMiner(config=config)
        
        for log_content in df_logs['content']:
            miner.add_log_message(log_content)
            
        # 2. Save the trained miner so the review manager can use it
        with open(DRAIN_MODEL_PATH, "wb") as f:
            dill.dump(miner, f)
        print(f"✅ Drain miner trained and saved to {DRAIN_MODEL_PATH}")

        # 2. Group into sequences
        training_data = group_into_sequences(df_logs)
        
        # 3. Save the final prepared data
        with open(OUTPUT_FILE, "wb") as f:
            dill.dump(training_data, f)
        
        print(f"\n🎉 Success! Training data has been prepared and saved to {OUTPUT_FILE}")
        normal_count = sum(1 for s in training_data if s['label'] == 0)
        anomaly_count = sum(1 for s in training_data if s['label'] == 1)
        print(f"  - Total sequences: {len(training_data)}")
        print(f"  - Normal sequences: {normal_count}")
        print(f"  - Anomaly sequences: {anomaly_count}")
