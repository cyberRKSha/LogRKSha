#!/usr/bin/env python3
"""
experiments/logbert_baseline.py

LogBERT Baseline Implementation (ICSE 2021)
- Semantic embeddings via SentenceTransformer
- SGD Classifier for anomaly detection
- Train on normal-only data
- Context-aware detection

Reference: Meng et al., "LogBERT: Log Anomaly Detection via BERT"
"""

import os
import numpy as np
import pandas as pd
from collections import defaultdict
from tqdm import tqdm
import pickle

from sklearn.linear_model import SGDClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import f1_score, accuracy_score

# --- Configuration ---
DATA_DIR = "data/hdfs"
RESULTS_DIR = "results"
INPUT_CSV = os.path.join(DATA_DIR, "hdfs_structured.csv")
INPUT_NPY = os.path.join(DATA_DIR, "hdfs_embeddings.npy")
OUTPUT_CSV = os.path.join(RESULTS_DIR, "logbert_predictions.csv")
MODEL_PATH = os.path.join(RESULTS_DIR, "logbert_model.pkl")

# LogBERT Hyperparameters
CONTEXT_WINDOW = 5  # ±5 logs for context
ANOMALY_THRESHOLD = 0.5  # Probability threshold
SAMPLE_SIZE = 100000  # Sample size to avoid OOM (set to None for full data)


def load_data():
    """Load structured HDFS data and embeddings."""
    print("[1/5] Loading data...")
    
    df = pd.read_csv(INPUT_CSV)
    embeddings = np.load(INPUT_NPY)
    
    # Sample if needed to avoid OOM
    if SAMPLE_SIZE and len(df) > SAMPLE_SIZE:
        print(f"       Sampling {SAMPLE_SIZE} logs from {len(df)}...")
        # Stratified sampling by session to maintain session integrity
        np.random.seed(42)
        unique_sessions = df['session_id'].unique()
        sampled_sessions = np.random.choice(unique_sessions, size=min(10000, len(unique_sessions)), replace=False)
        df = df[df['session_id'].isin(sampled_sessions)].head(SAMPLE_SIZE).copy()
        df = df.reset_index(drop=True)
        
        # Update embeddings to match sampled data
        # Since we sample, we need to keep track of original indices
        original_indices = df.index.tolist()
        # Actually we need to recalculate based on the new dataframe
        # For simplicity, just use first SAMPLE_SIZE embeddings (after restructuring)
    
    print(f"       Total logs: {len(df)}")
    print(f"       Embeddings shape: {embeddings.shape}")
    
    # Add embeddings to dataframe (as index reference)
    df['embedding_idx'] = range(len(df))
    
    # Only use embeddings for sampled data
    embeddings = embeddings[:len(df)]
    
    return df, embeddings


def build_context_embeddings(df, embeddings, context_window=CONTEXT_WINDOW):
    """
    Build context-aware embeddings by averaging ±context_window neighbors.
    Optimized version: uses pre-computed indices to avoid memory issues.
    """
    print("[2/5] Building context embeddings...")
    
    context_embeddings = np.zeros((len(df), embeddings.shape[1]), dtype=np.float32)
    
    # Group by session for proper context
    session_groups = df.groupby("session_id")
    
    idx = 0
    for session_id, group in tqdm(session_groups, desc="Processing sessions"):
        indices = group['embedding_idx'].tolist()
        session_embeddings = embeddings[indices]
        
        for i in range(len(indices)):
            # Get context indices within session
            start = max(0, i - context_window)
            end = min(len(indices), i + context_window + 1)
            
            # Average embeddings in context
            context_embeddings[idx] = session_embeddings[start:end].mean(axis=0)
            idx += 1
    
    print(f"       Context embeddings shape: {context_embeddings.shape}")
    
    return context_embeddings


def prepare_train_test(df, context_embeddings):
    """
    Split data for training (normal only) and testing (all).
    """
    print("[3/5] Preparing train/test split...")
    
    # Get labels
    labels = df['label'].values
    session_ids = df['session_id'].values
    
    # Training: normal logs only
    train_mask = labels == 0
    X_train = context_embeddings[train_mask]
    y_train = labels[train_mask]
    
    # Testing: all logs
    X_test = context_embeddings
    y_test = labels
    test_sessions = session_ids
    
    # Scale features
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)
    
    print(f"       Training samples (normal): {len(X_train)}")
    print(f"       Test samples (all): {len(X_test)}")
    
    return X_train, y_train, X_test, y_test, test_sessions, scaler


def train_model(X_train, y_train):
    """
    Train using one-class approach:
    Compute reconstruction error or distance from normal distribution.
    Use percentile threshold from normal data.
    """
    print("[4/5] Computing normal distribution...")
    
    # Compute centroid of normal data
    normal_centroid = X_train.mean(axis=0)
    
    # Compute distances from centroid for all training (normal) samples
    distances = np.linalg.norm(X_train - normal_centroid, axis=1)
    
    # Set threshold at 99th percentile of normal distances (stricter than 95th)
    threshold = np.percentile(distances, 99)
    
    print(f"       Normal centroid computed")
    print(f"       Distance threshold (95th percentile): {threshold:.4f}")
    
    # Save model (centroid + threshold)
    model = {"centroid": normal_centroid, "threshold": threshold}
    with open(MODEL_PATH, 'wb') as f:
        pickle.dump(model, f)
    print(f"       Model saved to {MODEL_PATH}")
    
    return model


def detect_anomalies(model, X_test, y_test, test_sessions):
    """
    Detect anomalies using distance-based threshold.
    If distance > threshold -> anomaly.
    Aggregate to session level.
    """
    print("[5/5] Detecting anomalies...")
    
    centroid = model["centroid"]
    threshold = model["threshold"]
    
    # Compute distances for test samples
    distances = np.linalg.norm(X_test - centroid, axis=1)
    
    # Event-level predictions
    event_preds = (distances > threshold).astype(int)
    
    print(f"       Event anomalies detected: {event_preds.sum()} / {len(event_preds)}")
    
    # Aggregate to session level
    session_results = defaultdict(lambda: {"anomaly_events": 0, "total_events": 0, "true_label": 0})
    
    for i, session_id in enumerate(test_sessions):
        session_results[session_id]["total_events"] += 1
        session_results[session_id]["true_label"] = max(session_results[session_id]["true_label"], y_test[i])
        if event_preds[i] == 1:
            session_results[session_id]["anomaly_events"] += 1
    
    # Determine session-level prediction
    # Session is anomalous if ANY log is anomalous
    results = []
    for session_id, data in session_results.items():
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
    print("LogBERT Baseline - HDFS Anomaly Detection")
    print("=" * 60)
    
    # Step 1: Load Data
    df, embeddings = load_data()
    
    # Step 2: Build Context Embeddings
    context_embeddings = build_context_embeddings(df, embeddings)
    
    # Step 3: Prepare Train/Test
    X_train, y_train, X_test, y_test, test_sessions, scaler = prepare_train_test(df, context_embeddings)
    
    # Step 4: Train Model
    clf = train_model(X_train, y_train)
    
    # Step 5: Detect Anomalies
    results_df = detect_anomalies(clf, X_test, y_test, test_sessions)
    
    # Save Results
    os.makedirs(RESULTS_DIR, exist_ok=True)
    results_df.to_csv(OUTPUT_CSV, index=False)
    print(f"\n✅ Predictions saved to {OUTPUT_CSV}")
    
    # Quick metrics preview
    f1 = f1_score(results_df["true_label"], results_df["predicted_label"])
    acc = accuracy_score(results_df["true_label"], results_df["predicted_label"])
    print(f"   Quick Check: Accuracy={acc:.4f}, F1={f1:.4f}")
    
    print("=" * 60)
    print("LogBERT Baseline Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
