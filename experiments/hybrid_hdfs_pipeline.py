#!/usr/bin/env python3
"""
experiments/hybrid_hdfs_pipeline.py

SIEM Hybrid Model Evaluation on HDFS Dataset.

This script runs your production SIEM models on the HDFS benchmark:
- Model A: Supervised Semantic Classifier (SGD)
- Model B: Unsupervised Autoencoder (Novelty Detection)
- Model C: Sequence Risk (LSTM)
- Hybrid: Combined Decision Logic

Outputs:
    - results/hdfs_supervised.csv
    - results/hdfs_autoencoder.csv
    - results/hdfs_sequence.csv
    - results/hdfs_hybrid.csv
"""

import os
import pickle
import numpy as np
import pandas as pd
from collections import defaultdict
from tqdm import tqdm

from sklearn.linear_model import SGDClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import f1_score, accuracy_score

import tensorflow as tf
from tensorflow.keras.models import Sequential, load_model
from tensorflow.keras.layers import LSTM, Dense, Embedding, Input
from tensorflow.keras.callbacks import EarlyStopping

# --- Configuration ---
DATA_DIR = "data/hdfs"
RESULTS_DIR = "results"
INPUT_CSV = os.path.join(DATA_DIR, "hdfs_structured.csv")
INPUT_NPY = os.path.join(DATA_DIR, "hdfs_embeddings.npy")

# Output files
OUTPUT_SUPERVISED = os.path.join(RESULTS_DIR, "hdfs_supervised.csv")
OUTPUT_AUTOENCODER = os.path.join(RESULTS_DIR, "hdfs_autoencoder.csv")
OUTPUT_SEQUENCE = os.path.join(RESULTS_DIR, "hdfs_sequence.csv")
OUTPUT_HYBRID = os.path.join(RESULTS_DIR, "hdfs_hybrid.csv")

# Hyperparameters
SAMPLE_SIZE = 100000  # Sample size to avoid OOM
AUTOENCODER_THRESHOLD_PERCENTILE = 95
SEQUENCE_RISK_THRESHOLD = 0.5
MAX_SEQ_LEN = 20


def load_data():
    """Load HDFS data and embeddings."""
    print("[1/6] Loading HDFS data...")
    
    df = pd.read_csv(INPUT_CSV)
    embeddings = np.load(INPUT_NPY)
    
    # Sample if needed
    if SAMPLE_SIZE and len(df) > SAMPLE_SIZE:
        print(f"       Sampling {SAMPLE_SIZE} logs...")
        np.random.seed(42)
        unique_sessions = df['session_id'].unique()
        sampled_sessions = np.random.choice(unique_sessions, size=min(10000, len(unique_sessions)), replace=False)
        df = df[df['session_id'].isin(sampled_sessions)].head(SAMPLE_SIZE).copy()
        df = df.reset_index(drop=True)
        embeddings = embeddings[:len(df)]
    
    print(f"       Loaded {len(df)} logs, {df['session_id'].nunique()} sessions")
    return df, embeddings


# ============================================================================
# MODEL A: SUPERVISED SEMANTIC CLASSIFIER
# ============================================================================

def train_supervised(embeddings, labels):
    """Train SGD classifier on normal data with synthetic anomalies."""
    print("[2/6] Training Supervised Classifier...")
    
    # Scale embeddings
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(embeddings)
    
    # Train on normal only with synthetic anomalies
    normal_mask = labels == 0
    X_normal = X_scaled[normal_mask]
    
    # Create synthetic anomalies
    np.random.seed(42)
    n_synthetic = int(len(X_normal) * 0.1)
    synthetic = X_normal[:n_synthetic] + np.random.randn(n_synthetic, X_normal.shape[1]) * 2
    
    X_train = np.vstack([X_normal, synthetic])
    y_train = np.concatenate([np.zeros(len(X_normal)), np.ones(n_synthetic)])
    
    # Shuffle
    idx = np.random.permutation(len(X_train))
    X_train, y_train = X_train[idx], y_train[idx]
    
    # Train
    clf = SGDClassifier(loss='log_loss', max_iter=1000, random_state=42, class_weight='balanced')
    clf.fit(X_train, y_train)
    
    print(f"       Trained on {len(X_normal)} normal + {n_synthetic} synthetic samples")
    return clf, scaler


def predict_supervised(clf, scaler, embeddings):
    """Predict using supervised classifier."""
    X_scaled = scaler.transform(embeddings)
    probs = clf.predict_proba(X_scaled)[:, 1]
    preds = (probs > 0.5).astype(int)
    return preds, probs


# ============================================================================
# MODEL B: AUTOENCODER (NOVELTY DETECTION)
# ============================================================================

def train_autoencoder(embeddings, labels):
    """Train autoencoder on normal data only."""
    print("[3/6] Training Autoencoder...")
    
    # Train only on normal
    normal_mask = labels == 0
    X_normal = embeddings[normal_mask]
    
    # Scale
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_normal)
    
    # Build autoencoder
    input_dim = X_scaled.shape[1]
    
    model = Sequential([
        Dense(128, activation='relu', input_shape=(input_dim,)),
        Dense(64, activation='relu'),
        Dense(32, activation='relu'),
        Dense(64, activation='relu'),
        Dense(128, activation='relu'),
        Dense(input_dim, activation='linear')
    ])
    
    model.compile(optimizer='adam', loss='mse')
    
    # Train
    model.fit(X_scaled, X_scaled, epochs=10, batch_size=256, 
              validation_split=0.1, verbose=0,
              callbacks=[EarlyStopping(patience=2, restore_best_weights=True)])
    
    # Compute threshold from normal reconstruction
    reconstructed = model.predict(X_scaled, verbose=0)
    losses = np.mean((X_scaled - reconstructed) ** 2, axis=1)
    threshold = np.percentile(losses, AUTOENCODER_THRESHOLD_PERCENTILE)
    
    print(f"       Threshold (percentile {AUTOENCODER_THRESHOLD_PERCENTILE}): {threshold:.4f}")
    return model, scaler, threshold


def predict_autoencoder(model, scaler, embeddings, threshold):
    """Predict using autoencoder reconstruction loss."""
    X_scaled = scaler.transform(embeddings)
    reconstructed = model.predict(X_scaled, verbose=0)
    losses = np.mean((X_scaled - reconstructed) ** 2, axis=1)
    preds = (losses > threshold).astype(int)
    return preds, losses


# ============================================================================
# MODEL C: SEQUENCE RISK (LSTM)
# ============================================================================

def build_session_sequences(df, embeddings, max_len=MAX_SEQ_LEN):
    """Build session sequences for LSTM."""
    sequences = {}
    session_labels = {}
    
    df['embedding_idx'] = range(len(df))
    
    for sid, group in df.groupby('session_id'):
        indices = group['embedding_idx'].tolist()
        if len(indices) >= 2:
            # Get embeddings for this session
            seq_emb = embeddings[indices[-max_len:]]
            sequences[sid] = seq_emb
            session_labels[sid] = group['label'].max()
    
    return sequences, session_labels


def train_sequence_model(sequences, session_labels):
    """Train LSTM for sequence risk prediction."""
    print("[4/6] Training Sequence (LSTM) Model...")
    
    # Prepare data
    X_list = []
    y_list = []
    
    for sid, seq in sequences.items():
        X_list.append(seq)
        y_list.append(session_labels[sid])
    
    # Pad sequences
    max_len = max(len(s) for s in X_list)
    emb_dim = X_list[0].shape[1]
    
    X = np.zeros((len(X_list), max_len, emb_dim))
    for i, seq in enumerate(X_list):
        X[i, -len(seq):] = seq  # Right-pad
    
    y = np.array(y_list)
    
    # Train only on normal
    normal_mask = y == 0
    X_normal = X[normal_mask]
    
    # Build LSTM
    model = Sequential([
        LSTM(64, input_shape=(max_len, emb_dim)),
        Dense(32, activation='relu'),
        Dense(1, activation='sigmoid')
    ])
    
    model.compile(optimizer='adam', loss='binary_crossentropy')
    
    # Train to predict 0 for normal (sequence should predict "normalcy")
    model.fit(X_normal, np.zeros(len(X_normal)), epochs=5, batch_size=64, 
              validation_split=0.1, verbose=0)
    
    print(f"       Trained on {len(X_normal)} normal sequences")
    return model, max_len, emb_dim


def predict_sequence(model, sequences, max_len, emb_dim):
    """Predict sequence risk."""
    X_list = list(sequences.values())
    sids = list(sequences.keys())
    
    X = np.zeros((len(X_list), max_len, emb_dim))
    for i, seq in enumerate(X_list):
        X[i, -len(seq):] = seq
    
    risks = model.predict(X, verbose=0).flatten()
    
    # Higher deviation from 0 = more anomalous
    preds = (risks > SEQUENCE_RISK_THRESHOLD).astype(int)
    
    return dict(zip(sids, preds)), dict(zip(sids, risks))


# ============================================================================
# HYBRID DECISION LOGIC
# ============================================================================

def hybrid_decision(supervised_preds, autoencoder_preds, sequence_preds, 
                    supervised_scores, autoencoder_scores, sequence_scores):
    """
    Hybrid decision logic (frozen - matches SIEM worker).
    
    Logic:
    - If supervised == 1 -> anomaly
    - Elif sequence_risk > 0.5 -> anomaly  
    - Elif reconstruction_loss > threshold -> anomaly
    - Else -> normal
    """
    hybrid_preds = {}
    hybrid_scores = {}
    
    all_sids = set(supervised_preds.keys()) | set(autoencoder_preds.keys()) | set(sequence_preds.keys())
    
    for sid in all_sids:
        sup = supervised_preds.get(sid, 0)
        ae = autoencoder_preds.get(sid, 0)
        seq = sequence_preds.get(sid, 0)
        
        # Scores for ranking
        sup_score = supervised_scores.get(sid, 0)
        ae_score = autoencoder_scores.get(sid, 0)
        seq_score = sequence_scores.get(sid, 0)
        
        # Hybrid logic
        if sup == 1:
            hybrid_preds[sid] = 1
            hybrid_scores[sid] = max(sup_score, ae_score, seq_score)
        elif seq == 1:
            hybrid_preds[sid] = 1
            hybrid_scores[sid] = seq_score
        elif ae == 1:
            hybrid_preds[sid] = 1
            hybrid_scores[sid] = ae_score
        else:
            hybrid_preds[sid] = 0
            hybrid_scores[sid] = max(sup_score, ae_score, seq_score)
    
    return hybrid_preds, hybrid_scores


# ============================================================================
# AGGREGATION & SAVING
# ============================================================================

def aggregate_to_session(df, preds, scores):
    """Aggregate event-level predictions to session level."""
    session_preds = {}
    session_scores = {}
    session_labels = {}
    
    for i, (_, row) in enumerate(df.iterrows()):
        sid = row['session_id']
        if sid not in session_preds:
            session_preds[sid] = 0
            session_scores[sid] = 0
            session_labels[sid] = row['label']
        
        # Any anomalous event -> session is anomalous
        if preds[i] == 1:
            session_preds[sid] = 1
        session_scores[sid] = max(session_scores[sid], scores[i])
        session_labels[sid] = max(session_labels[sid], row['label'])
    
    return session_preds, session_scores, session_labels


def save_results(session_preds, session_scores, session_labels, output_file):
    """Save predictions to CSV."""
    results = []
    for sid in session_preds.keys():
        results.append({
            "session_id": sid,
            "true_label": session_labels[sid],
            "predicted_label": session_preds[sid],
            "score": session_scores[sid]
        })
    
    df = pd.DataFrame(results)
    df.to_csv(output_file, index=False)
    
    # Quick metrics
    f1 = f1_score(df["true_label"], df["predicted_label"])
    acc = accuracy_score(df["true_label"], df["predicted_label"])
    print(f"       Saved: {output_file} (Acc={acc:.4f}, F1={f1:.4f})")
    
    return df


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("=" * 60)
    print("SIEM Hybrid Model Evaluation on HDFS")
    print("=" * 60)
    
    os.makedirs(RESULTS_DIR, exist_ok=True)
    
    # Load data
    df, embeddings = load_data()
    labels = df['label'].values
    
    # --- Model A: Supervised ---
    clf, sup_scaler = train_supervised(embeddings, labels)
    sup_preds, sup_probs = predict_supervised(clf, sup_scaler, embeddings)
    sup_session_preds, sup_session_scores, session_labels = aggregate_to_session(df, sup_preds, sup_probs)
    save_results(sup_session_preds, sup_session_scores, session_labels, OUTPUT_SUPERVISED)
    
    # --- Model B: Autoencoder ---
    ae_model, ae_scaler, ae_threshold = train_autoencoder(embeddings, labels)
    ae_preds, ae_losses = predict_autoencoder(ae_model, ae_scaler, embeddings, ae_threshold)
    ae_session_preds, ae_session_scores, _ = aggregate_to_session(df, ae_preds, ae_losses)
    save_results(ae_session_preds, ae_session_scores, session_labels, OUTPUT_AUTOENCODER)
    
    # --- Model C: Sequence ---
    print("[4/6] Building session sequences...")
    sequences, seq_session_labels = build_session_sequences(df, embeddings)
    seq_model, max_len, emb_dim = train_sequence_model(sequences, seq_session_labels)
    seq_session_preds, seq_session_scores = predict_sequence(seq_model, sequences, max_len, emb_dim)
    
    # Save sequence results
    seq_results = []
    for sid in seq_session_preds.keys():
        seq_results.append({
            "session_id": sid,
            "true_label": seq_session_labels.get(sid, 0),
            "predicted_label": seq_session_preds[sid],
            "score": seq_session_scores[sid]
        })
    seq_df = pd.DataFrame(seq_results)
    seq_df.to_csv(OUTPUT_SEQUENCE, index=False)
    f1 = f1_score(seq_df["true_label"], seq_df["predicted_label"])
    print(f"       Saved: {OUTPUT_SEQUENCE} (F1={f1:.4f})")
    
    # --- Hybrid ---
    print("[5/6] Running Hybrid Decision Logic...")
    hybrid_preds, hybrid_scores = hybrid_decision(
        sup_session_preds, ae_session_preds, seq_session_preds,
        sup_session_scores, ae_session_scores, seq_session_scores
    )
    
    # Save hybrid results
    hybrid_results = []
    for sid in hybrid_preds.keys():
        hybrid_results.append({
            "session_id": sid,
            "true_label": session_labels.get(sid, seq_session_labels.get(sid, 0)),
            "predicted_label": hybrid_preds[sid],
            "score": hybrid_scores[sid]
        })
    hybrid_df = pd.DataFrame(hybrid_results)
    hybrid_df.to_csv(OUTPUT_HYBRID, index=False)
    f1 = f1_score(hybrid_df["true_label"], hybrid_df["predicted_label"])
    print(f"       Saved: {OUTPUT_HYBRID} (F1={f1:.4f})")
    
    print("\n[6/6] Running Full Evaluation...")
    print("=" * 60)
    print("✅ SIEM Hybrid Pipeline Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
