#!/usr/bin/env python3
import os
import pandas as pd
import joblib
import numpy as np
from sklearn.metrics import confusion_matrix, accuracy_score
from sklearn.metrics import classification_report

def log_info(msg): print(f"\033[94mℹ️ {msg}\033[0m")
def log_success(msg): print(f"\033[92m✅ {msg}\033[0m")
def log_warn(msg): print(f"\033[93m⚠️ {msg}\033[0m")
def log_error(msg): print(f"\033[91m❗ {msg}\033[0m")

REAL_LOG = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux/logs/real_log.csv"
MODEL_PATH = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux/model/sgd_embedder.pkl"
EMBEDDER_PATH = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux/model/sentence_embedder.pkl"
CHECKPOINT_FILE = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux/model/last_update_checkpoint.txt"

log_info("🔄 Loading model & embedder...")
model = joblib.load(MODEL_PATH)
embedder = joblib.load(EMBEDDER_PATH)

if not os.path.exists(REAL_LOG):
    log_error(f"{REAL_LOG} not found. Exiting.")
    exit(1)

df_real = pd.read_csv(REAL_LOG)
if df_real.empty or 'label' not in df_real.columns:
    log_warn("⚠️ real_log.csv is empty or missing 'label' column. Nothing to update.")
    exit(0)

# Find new rows
last_row = 0
if os.path.exists(CHECKPOINT_FILE):
    with open(CHECKPOINT_FILE, "r") as f:
        try: last_row = int(f.read().strip())
        except: last_row = 0

new_logs = df_real.iloc[last_row:]
if new_logs.empty:
    log_warn("✅ No new logs to train on. Model already up-to-date.")
    exit(0)

log_info(f"📦 Found {len(new_logs)} new logs "
        f"(normal: {(new_logs['label']==0).sum()}, anomaly: {(new_logs['label']==1).sum()})")

log_info("🔢 Evaluating current model on new batch…")
X_eval = embedder.encode(
    new_logs['content'].astype(str).tolist(),
    show_progress_bar=True
)
y_true = new_logs['label'].astype(int).tolist()
y_pred = model.predict(X_eval)

cm  = confusion_matrix(y_true, y_pred)
acc = accuracy_score(y_true, y_pred)

log_info(f"📊 Confusion Matrix:\n{cm.tolist()}")   
log_info(f"✔ Accuracy on new batch: {acc:.2%}")
print("Classification report:")
log_info(classification_report(y_true, y_pred, target_names=['Normal','Anomaly']))

log_info("🔢 Generating embeddings...")
X_new = embedder.encode(new_logs['content'].astype(str).tolist(), show_progress_bar=True)
y_new = new_logs['label'].astype(int).values

# Shuffle
idx = np.random.permutation(len(y_new))
X_new = X_new[idx]
y_new = y_new[idx]

log_info("🧠 Updating model...")
model.partial_fit(X_new, y_new, classes=[0, 1])

joblib.dump(model, MODEL_PATH)
log_success(f"✅ Model updated and saved to: {MODEL_PATH}")

# Update checkpoint
new_last_row = last_row + len(new_logs)
with open(CHECKPOINT_FILE, "w") as f:
    f.write(str(new_last_row))
log_info(f"📌 Checkpoint updated: last row processed = {new_last_row}")
