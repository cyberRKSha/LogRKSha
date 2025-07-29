#!/usr/bin/env python3
import os
import pandas as pd
import joblib
import numpy as np

# Load embedder directly
from sentence_transformers import SentenceTransformer

def log_info(msg): print(f"\033[94mℹ️ {msg}\033[0m")
def log_success(msg): print(f"\033[92m✅ {msg}\033[0m")
def log_warn(msg): print(f"\033[93m⚠️ {msg}\033[0m")
def log_error(msg): print(f"\033[91m❗ {msg}\033[0m")

REAL_LOG = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux/logs/real_log.csv"
MODEL_PATH = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux/model/sgd_embedder.pkl"
EMBEDDER_PATH = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux/model/sentence_embedder.pkl"
CHECKPOINT_FILE = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux/model/last_update_checkpoint.txt"

log_info("🔄 Loading embedder...")
embedder = joblib.load(EMBEDDER_PATH)

if not os.path.exists(REAL_LOG):
    log_error(f"{REAL_LOG} not found. Exiting.")
    exit(1)

df = pd.read_csv(REAL_LOG)
if df.empty or 'label' not in df.columns:
    log_error("No data or missing 'label' column in real_log.csv. Exiting.")
    exit(1)

log_info(f"📦 Training on {len(df)} logs "
         f"(normal: {(df['label']==0).sum()}, anomaly: {(df['label']==1).sum()})")

log_info("🔢 Generating embeddings...")
X = embedder.encode(df['content'].astype(str).tolist(), show_progress_bar=True)
y = df['label'].astype(int).values

# Shuffle
idx = np.random.permutation(len(y))
X = X[idx]
y = y[idx]

# === Create new model ===
from sklearn.linear_model import SGDClassifier
model = SGDClassifier(loss='log_loss', max_iter=1000, tol=1e-3)

log_info("🧠 Training fresh model...")
model.partial_fit(X, y, classes=[0, 1])

joblib.dump(model, MODEL_PATH)
log_success(f"✅ Model saved to: {MODEL_PATH}")

# Reset checkpoint
with open(CHECKPOINT_FILE, "w") as f:
    f.write(str(len(df)))
log_info(f"📌 Checkpoint updated: last row processed = {len(df)}")
