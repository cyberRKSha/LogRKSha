#!/usr/bin/env python3
"""
scripts/hdfs_preprocess.py

Standalone HDFS Preprocessing Script for Research Comparison.
This script is INDEPENDENT of the SIEM codebase.

Outputs:
    - data/hdfs/hdfs_structured.csv
    - data/hdfs/hdfs_sequences.pkl
    - data/hdfs/hdfs_embeddings.npy
"""

import os
import re
import pickle
import numpy as np
import pandas as pd
from collections import defaultdict
from tqdm import tqdm
from drain3 import TemplateMiner
from drain3.template_miner_config import TemplateMinerConfig
from sentence_transformers import SentenceTransformer

# --- Configuration ---
DATA_DIR = "data/hdfs"
LOG_FILE = os.path.join(DATA_DIR, "HDFS.log")
LABEL_FILE = os.path.join(DATA_DIR, "preprocessed", "anomaly_label.csv")

OUTPUT_CSV = os.path.join(DATA_DIR, "hdfs_structured.csv")
OUTPUT_PKL = os.path.join(DATA_DIR, "hdfs_sequences.pkl")
OUTPUT_NPY = os.path.join(DATA_DIR, "hdfs_embeddings.npy")

# Limit for faster testing (set to None for full dataset)
LOG_LIMIT = 1000000  # Processing 1M logs to avoid OOM


def load_labels(label_file: str) -> dict:
    """Loads ground truth labels from CSV. Returns dict: {BlockId: 0 or 1}"""
    print(f"[1/4] Loading labels from {label_file}...")
    df = pd.read_csv(label_file)
    label_map = {}
    for _, row in df.iterrows():
        label_map[row['BlockId']] = 1 if row['Label'] == 'Anomaly' else 0
    print(f"       Loaded {len(label_map)} block labels. Anomalies: {sum(label_map.values())}")
    return label_map


def parse_logs_with_drain(log_file: str, limit: int = None) -> pd.DataFrame:
    """
    Parses raw HDFS logs using Drain3.
    Extracts: content, template, template_id, session_id (BlockId).
    """
    print(f"[2/4] Parsing logs with Drain3 from {log_file}...")
    
    # Initialize Drain
    config = TemplateMinerConfig()
    # Use default config, no need to load external ini for this standalone script
    miner = TemplateMiner(config=config)

    # Regex for Block ID
    blk_pattern = re.compile(r"(blk_-?\d+)")
    
    rows = []
    line_count = 0
    
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in tqdm(f, desc="Parsing", unit=" lines"):
            line = line.strip()
            if not line:
                continue
            
            # Extract Block ID
            match = blk_pattern.search(line)
            block_id = match.group(1) if match else "NO_BLOCK"
            
            # Drain parsing
            result = miner.add_log_message(line)
            
            rows.append({
                "content": line,
                "template": result["template_mined"],
                "template_id": result["cluster_id"],
                "session_id": block_id
            })
            
            line_count += 1
            if limit and line_count >= limit:
                break
    
    print(f"       Parsed {line_count} log lines. Found {len(miner.drain.clusters)} unique templates.")
    return pd.DataFrame(rows)


def map_labels(df: pd.DataFrame, label_map: dict) -> pd.DataFrame:
    """Maps session-level labels to each log entry."""
    print("[3/4] Mapping labels to log entries...")
    df['label'] = df['session_id'].map(label_map).fillna(0).astype(int)  # Default to Normal
    anomaly_count = df['label'].sum()
    print(f"       Total logs: {len(df)}, Anomalous: {anomaly_count}")
    return df


def create_sequences(df: pd.DataFrame) -> list:
    """
    Groups logs by session_id (Block ID) and creates sequences of template_ids.
    Returns: List of dicts with 'sequence' (list of template_ids) and 'label' (0 or 1).
    """
    print("       Creating session sequences for DeepLog/LSTM...")
    sessions = defaultdict(list)
    session_labels = {}
    
    for _, row in df.iterrows():
        sessions[row['session_id']].append(row['template_id'])
        # If any log in session is anomaly, session is anomaly
        if row['label'] == 1:
            session_labels[row['session_id']] = 1
        elif row['session_id'] not in session_labels:
            session_labels[row['session_id']] = 0
    
    sequences = []
    for sid, seq in sessions.items():
        sequences.append({
            "session_id": sid,
            "sequence": seq,
            "label": session_labels.get(sid, 0)
        })
    
    print(f"       Created {len(sequences)} session sequences.")
    return sequences


def create_embeddings(df: pd.DataFrame) -> np.ndarray:
    """
    Generates SentenceTransformer embeddings for each log template.
    Returns: Numpy array of shape (n_logs, embedding_dim).
    """
    print("       Creating semantic embeddings for LogBERT/SBERT...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    # Embed templates (not raw content, for efficiency and consistency)
    unique_templates = df['template'].unique().tolist()
    template_to_embedding = {}
    
    print(f"       Embedding {len(unique_templates)} unique templates...")
    embeddings = model.encode(unique_templates, show_progress_bar=True)
    
    for i, tmpl in enumerate(unique_templates):
        template_to_embedding[tmpl] = embeddings[i]
    
    # Map embeddings back to dataframe order
    all_embeddings = np.array([template_to_embedding[t] for t in df['template']])
    print(f"       Generated embeddings with shape: {all_embeddings.shape}")
    return all_embeddings


def save_outputs(df: pd.DataFrame, sequences: list, embeddings: np.ndarray):
    """Saves all three output formats."""
    print("[4/4] Saving outputs...")
    
    # 1. CSV for analysis
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"       Saved: {OUTPUT_CSV}")
    
    # 2. PKL for sequences (DeepLog)
    with open(OUTPUT_PKL, 'wb') as f:
        pickle.dump(sequences, f)
    print(f"       Saved: {OUTPUT_PKL}")
    
    # 3. NPY for embeddings (LogBERT/SBERT)
    np.save(OUTPUT_NPY, embeddings)
    print(f"       Saved: {OUTPUT_NPY}")


def main():
    print("=" * 60)
    print("HDFS Dataset Preprocessing for Research Comparison")
    print("=" * 60)
    
    # Step 1: Load Labels
    label_map = load_labels(LABEL_FILE)
    
    # Step 2: Parse Logs
    df = parse_logs_with_drain(LOG_FILE, limit=LOG_LIMIT)
    
    # Step 3: Map Labels
    df = map_labels(df, label_map)
    
    # Step 4: Create Outputs
    sequences = create_sequences(df)
    embeddings = create_embeddings(df)
    
    # Step 5: Save
    save_outputs(df, sequences, embeddings)
    
    print("=" * 60)
    print("✅ Preprocessing Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
