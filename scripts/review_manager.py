import os
import re
import sqlite3
import joblib
import dill
from drain3 import TemplateMiner
from datetime import datetime
from collections import Counter
import pandas as pd
import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer

# --- Configuration ---
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATABASE_FILE = os.path.join(PROJECT_ROOT, "log_database.db")
EMBEDDER_PATH = os.path.join(PROJECT_ROOT, "model/sentence_embedder.pkl")
DRAIN_MODEL_PATH = os.path.join(PROJECT_ROOT, "model/drain_miner.pkl")
SIMILARITY_THRESHOLD = 0.95  # How similar a log must be to an existing cluster to be added

def generate_cluster_name(group_df, miner):
    stop_words = {'a', 'an', 'the', 'is', 'in', 'on', 'for', 'of', 'to', 'with', 'and', 'from'}

    templates = []
    for index, row in group_df.iterrows():
        result = miner.match(row['content'])
        if result:
            templates.append(result.get_template())

    words = []
    for template in templates:
        if template:
            words.extend([word.lower() for word in re.split(r'[^a-zA-Z0-9]+', template) if word.lower() not in stop_words and len(word) > 2])
            
    if not words:
        return "Generic Cluster"

    most_common = [word for word, count in Counter(words).most_common(3)]
    return "-".join(most_common)

def prepare_review_session():

    print("🚀 Starting stateful review session preparation...")

    try:
        # embedder = joblib.load(EMBEDDER_PATH)
        embedder = SentenceTransformer(str(EMBEDDER_PATH))
        with open(DRAIN_MODEL_PATH, "rb") as f:
            miner = dill.load(f)
        print("✅ Official models loaded successfully.")
    except FileNotFoundError as e:
        print(f"❗ Model not found: {e}. Please run 'scripts/sequence.py' first.")
        return f"Model not found: {e}"

    con = sqlite3.connect(DATABASE_FILE)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    # cleanup_reviewed_clusters(con)

    print("Clearing all old cluster data...")
    cur.execute("DELETE FROM logCluster")
    cur.execute("DELETE FROM cluster")
    con.commit()

    query = "SELECT id, content, timestamp, predicted_label FROM logs WHERE is_reviewed = 0"
    df = pd.read_sql_query(query, con)
    
    if df.empty:
        print("✅ No new unreviewed logs to process.")
        con.close()
        return "No new logs to process."

    print(f"Generating embeddings for {len(df)} logs...")
    # embedder = joblib.load(EMBEDDER_PATH)
    embeddings = embedder.encode(df['content'].tolist(), show_progress_bar=True)
    df['embedding'] = list(embeddings)

    print(f"Clustering all {len(df)} logs...")
    dbscan = DBSCAN(eps=0.25, min_samples=5, metric='cosine')
    df['cluster_id_num'] = dbscan.fit_predict(df['embedding'].tolist()) 

    newly_formed_clusters = df[df['cluster_id_num'] != -1]
    noise_logs = df[df['cluster_id_num'] == -1]

    print(f"Found {newly_formed_clusters['cluster_id_num'].nunique()} new clusters.")
    print(f"Identified {len(noise_logs)} unclustered (noise) logs.")

    for cluster_id, group in newly_formed_clusters.groupby('cluster_id_num'):
        cluster_id_str = f"cluster_{int(datetime.now().timestamp())}_{cluster_id}"
        centroid = np.mean(np.array(group['embedding'].tolist()), axis=0)
        cluster_name = generate_cluster_name(group, miner)
        predicted_labels = cur.execute(
            f"SELECT predicted_label FROM logs WHERE id IN ({','.join('?' for _ in group['id'])})",
            tuple(group['id'])
        ).fetchall()

        if predicted_labels:
            avg_prediction = np.mean([p[0] for p in predicted_labels])
            confidence = abs(avg_prediction - 0.5) * 2
        else:
            confidence = 0.53 
        cur.execute(
            "INSERT INTO cluster (cluster_id, name, status, log_count, representative_log, first_seen, last_seen, centroid, is_noise, confidence) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)",
            (cluster_id_str, cluster_name, 'pending', len(group), group.iloc[0]['content'], group['timestamp'].min(), group['timestamp'].max(), centroid.tobytes(), confidence)
        )
        log_ids_in_group = group['id'].tolist()
        mappings = [(log_id, cluster_id_str) for log_id in log_ids_in_group]
        cur.executemany("INSERT OR IGNORE INTO logCluster (log_id, cluster_id) VALUES (?, ?)", mappings)
    
    for index, row in noise_logs.iterrows():
        # Each noise log gets its own "cluster" entry, flagged as noise
        noise_id_str = f"noise_{row['id']}"
        centroid = row['embedding']
        log_id = row['id']
        predicted_label = row['predicted_label']
        cur.execute(
            "INSERT INTO cluster (cluster_id, name, status, log_count, representative_log, first_seen, last_seen, is_noise, centroid, predicted_label) VALUES (?, ?, ?, 1, ?, ?, ?, 1, ?, ?)",
            (noise_id_str, "Unclustered Log", 'pending', row['content'], row['timestamp'], row['timestamp'], centroid.tobytes(), predicted_label)
        )
        # Also map it in the logCluster table
        cur.execute("INSERT OR IGNORE INTO logCluster (log_id, cluster_id) VALUES (?, ?)", (row['id'], noise_id_str))
    con.commit()
    con.close()
    
    msg = f"Processed {len(df)} logs."
    print(f"✅ {msg}")
    return msg


