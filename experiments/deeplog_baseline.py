#!/usr/bin/env python3
"""
experiments/deeplog_baseline.py

DeepLog Baseline Implementation (CCS 2017)
- Sequential LSTM model
- Train on normal-only data
- Sliding window sequence prediction
- Top-k anomaly detection

Reference: Du et al., "DeepLog: Anomaly Detection and Diagnosis from System Logs"
"""

import os
import pickle
import numpy as np
import pandas as pd
from collections import defaultdict
from tqdm import tqdm

import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Embedding
from tensorflow.keras.utils import to_categorical
from tensorflow.keras.callbacks import EarlyStopping

# --- Configuration ---
DATA_DIR = "data/hdfs"
RESULTS_DIR = "results"
INPUT_CSV = os.path.join(DATA_DIR, "hdfs_structured.csv")
OUTPUT_CSV = os.path.join(RESULTS_DIR, "deeplog_predictions.csv")
MODEL_PATH = os.path.join(RESULTS_DIR, "deeplog_model.keras")

# DeepLog Hyperparameters (as per paper)
WINDOW_SIZE = 10
TOP_K = 5  # Middle ground: not too aggressive, not too conservative
HIDDEN_SIZE = 64
EPOCHS = 10
BATCH_SIZE = 256
ANOMALY_THRESHOLD = 0.0  # If ANY event is anomalous -> session is anomalous (paper-aligned)


def load_data():
    """Load structured HDFS data."""
    print("[1/5] Loading data...")
    df = pd.read_csv(INPUT_CSV)
    print(f"       Total logs: {len(df)}")
    print(f"       Unique sessions: {df['session_id'].nunique()}")
    print(f"       Unique templates: {df['template_id'].nunique()}")
    return df


def build_sequences(df, window_size=WINDOW_SIZE, train_only_normal=True):
    """
    Build sliding window sequences for DeepLog.
    Returns X (input sequences), y (next event), and session metadata.
    """
    print("[2/5] Building sequences...")
    
    # Get unique template IDs and create mapping
    unique_templates = sorted(df['template_id'].unique())
    template2idx = {t: i+1 for i, t in enumerate(unique_templates)}  # 0 reserved for padding
    vocab_size = len(unique_templates) + 1
    
    print(f"       Vocabulary size: {vocab_size}")
    
    X_train, y_train = [], []
    X_test, y_test = [], []
    test_session_info = []  # (session_id, true_label, event_index)
    
    for session_id, group in tqdm(df.groupby("session_id"), desc="Processing sessions"):
        seq = [template2idx[t] for t in group["template_id"].tolist()]
        label = group["label"].iloc[0]  # Session-level label
        
        if len(seq) <= window_size:
            continue
        
        for i in range(len(seq) - window_size):
            input_seq = seq[i:i+window_size]
            target = seq[i+window_size]
            
            if label == 0:  # Normal session -> training data
                X_train.append(input_seq)
                y_train.append(target)
            
            # All sessions go to test for evaluation
            X_test.append(input_seq)
            y_test.append(target)
            test_session_info.append((session_id, label, i))
    
    X_train = np.array(X_train)
    y_train = to_categorical(y_train, num_classes=vocab_size)
    X_test = np.array(X_test)
    y_test = np.array(y_test)
    
    print(f"       Training samples (normal only): {len(X_train)}")
    print(f"       Test samples (all): {len(X_test)}")
    
    return X_train, y_train, X_test, y_test, test_session_info, vocab_size


def build_model(vocab_size, window_size=WINDOW_SIZE, hidden_size=HIDDEN_SIZE):
    """Build DeepLog LSTM model."""
    print("[3/5] Building LSTM model...")
    
    model = Sequential([
        Embedding(input_dim=vocab_size, output_dim=hidden_size, input_length=window_size),
        LSTM(hidden_size, return_sequences=False),
        Dense(vocab_size, activation='softmax')
    ])
    
    model.compile(
        loss='categorical_crossentropy',
        optimizer='adam',
        metrics=['accuracy']
    )
    
    model.summary()
    return model


def train_model(model, X_train, y_train):
    """Train the DeepLog model."""
    print("[4/5] Training model...")
    
    early_stop = EarlyStopping(monitor='val_loss', patience=2, restore_best_weights=True)
    
    history = model.fit(
        X_train, y_train,
        epochs=EPOCHS,
        batch_size=BATCH_SIZE,
        validation_split=0.1,
        callbacks=[early_stop],
        verbose=1
    )
    
    model.save(MODEL_PATH)
    print(f"       Model saved to {MODEL_PATH}")
    
    return model


def detect_anomalies(model, X_test, y_test, test_session_info, top_k=TOP_K):
    """
    Detect anomalies using top-k prediction logic.
    If true next event is NOT in top-k predictions -> anomaly event.
    """
    print("[5/5] Detecting anomalies...")
    
    predictions = model.predict(X_test, verbose=0)
    
    # Get top-k predictions for each sample
    top_k_preds = np.argsort(predictions, axis=1)[:, -top_k:]
    
    # Check if true label is in top-k
    event_anomalies = []
    for i, true_next in enumerate(y_test):
        is_anomaly = true_next not in top_k_preds[i]
        event_anomalies.append(is_anomaly)
    
    # Aggregate to session level
    session_results = defaultdict(lambda: {"anomaly_events": 0, "total_events": 0, "true_label": 0})
    
    for i, (session_id, true_label, event_idx) in enumerate(test_session_info):
        session_results[session_id]["total_events"] += 1
        session_results[session_id]["true_label"] = true_label
        if event_anomalies[i]:
            session_results[session_id]["anomaly_events"] += 1
    
    # Determine session-level prediction
    # Paper: if ANY event is anomalous -> session is anomalous
    results = []
    for session_id, data in session_results.items():
        # Changed: any anomalous event triggers session anomaly
        predicted_label = 1 if data["anomaly_events"] > 0 else 0
        anomaly_ratio = data["anomaly_events"] / data["total_events"]
        results.append({
            "session_id": session_id,
            "true_label": data["true_label"],
            "predicted_label": predicted_label,
            "anomaly_ratio": anomaly_ratio
        })
    
    return pd.DataFrame(results)


def main():
    print("=" * 60)
    print("DeepLog Baseline - HDFS Anomaly Detection")
    print("=" * 60)
    
    # Step 1: Load Data
    df = load_data()
    
    # Step 2: Build Sequences
    X_train, y_train, X_test, y_test, test_session_info, vocab_size = build_sequences(df)
    
    # Step 3: Build Model
    model = build_model(vocab_size)
    
    # Step 4: Train Model
    model = train_model(model, X_train, y_train)
    
    # Step 5: Detect Anomalies
    results_df = detect_anomalies(model, X_test, y_test, test_session_info)
    
    # Save Results
    os.makedirs(RESULTS_DIR, exist_ok=True)
    results_df.to_csv(OUTPUT_CSV, index=False)
    print(f"\n✅ Predictions saved to {OUTPUT_CSV}")
    
    # Quick metrics preview
    from sklearn.metrics import f1_score, accuracy_score
    f1 = f1_score(results_df["true_label"], results_df["predicted_label"])
    acc = accuracy_score(results_df["true_label"], results_df["predicted_label"])
    print(f"   Quick Check: Accuracy={acc:.4f}, F1={f1:.4f}")
    
    print("=" * 60)
    print("DeepLog Baseline Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
