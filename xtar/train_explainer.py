import os
import sqlite3
import pandas as pd
import joblib
from lime.lime_text import LimeTextExplainer
from sklearn.pipeline import make_pipeline
import dill

# --- Configuration ---
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATABASE_FILE = os.path.join(BASE_DIR, "log_database.db")
EMBEDDER_PATH = os.path.join(BASE_DIR, "model/sentence_embedder.pkl")
SUPERVISED_MODEL_PATH = os.path.join(BASE_DIR, "model/sgd_embedder.pkl")
EXPLAINER_PATH = os.path.join(BASE_DIR, "model/lime_explainer.pkl")

# --- Logging Helpers ---
def log_info(msg): print(f"\033[94mℹ️ {msg}\033[0m")
def log_success(msg): print(f"\032[92m✅ {msg}\033[0m")

def train_explainer():
    """
    Creates and saves a LIME explainer for our model using the 'dill' library.
    """
    log_info("--- Training LIME Explainer ---")
    
    log_info("Loading models...")
    embedder = joblib.load(EMBEDDER_PATH)
    model = joblib.load(SUPERVISED_MODEL_PATH)
    
    pipeline = make_pipeline(embedder, model)

    log_info("Creating the LIME explainer object...")
    class_names = ['normal', 'anomaly']
    explainer = LimeTextExplainer(class_names=class_names)

    # --- THE FIX: Use dill.dump() instead of joblib.dump() ---
    log_info("Saving explainer with dill...")
    with open(EXPLAINER_PATH, 'wb') as f:
        dill.dump(explainer, f)
    # --- END FIX ---
    
    log_success(f"✅ LIME explainer saved to: {EXPLAINER_PATH}")
    log_info("You can now run the monitor script.")

if __name__ == "__main__":
    train_explainer()
