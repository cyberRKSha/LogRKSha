# train_drain_parser.py
import os
import sqlite3
import pandas as pd
import joblib
from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig

# --- Configuration ---
BASE_DIR = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux"
DATABASE_FILE = os.path.join(BASE_DIR, "log_database.db")
DRAIN_PATH = os.path.join(BASE_DIR, "model/template_miner.pkl")

def log_info(msg): print(f"\033[94mℹ️ {msg}\033[0m")
def log_success(msg): print(f"\032[92m✅ {msg}\033[0m")

def train_parser():
    log_info(f"Connecting to database: {DATABASE_FILE}")
    conn = sqlite3.connect(DATABASE_FILE)
    query = "SELECT content FROM logs"
    df = pd.read_sql_query(query, conn)
    conn.close()
    log_info(f"Fetched {len(df)} logs to learn templates.")

    log_info("Training Drain3 to learn log templates...")
    
    # === START: THE FIX ===
    # Create a configuration object
    config = TemplateMinerConfig()
    # Set the parameters directly as attributes
    config.drain_sim_th = 0.5  # Similarity threshold
    config.drain_depth = 4     # Parsing depth
    
    # Pass the config object to the TemplateMiner constructor
    template_miner = TemplateMiner(config=config)
    # === END: THE FIX ===

    for log_line in df['content']:
        # Ensure log_line is a string, as data from DB can sometimes be other types
        template_miner.add_log_message(str(log_line))

    log_success(f"Drain3 training complete. Found {len(template_miner.drain.clusters)} unique templates.")

    joblib.dump(template_miner, DRAIN_PATH)
    log_success(f"Template miner model saved to {DRAIN_PATH}")

if __name__ == "__main__":
    train_parser()