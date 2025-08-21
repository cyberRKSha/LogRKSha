# scripts/tune_clusters.py
import sqlite3
import joblib
import pandas as pd
import numpy as np
from sklearn.cluster import DBSCAN
from sentence_transformers import SentenceTransformer
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATABASE_FILE = os.path.join(PROJECT_ROOT, "log_database.db")
EMBEDDER_PATH = os.path.join(PROJECT_ROOT, "model/sentence_embedder.pkl")

# Fetch unreviewed logs
con = sqlite3.connect(DATABASE_FILE)
query = "SELECT content FROM logs WHERE is_reviewed = 0"
df = pd.read_sql_query(query, con)
con.close()

if not df.empty:
    # Generate embeddings
    print("Generating embeddings...")
    embedder = SentenceTransformer(str(EMBEDDER_PATH))
    embeddings = embedder.encode(df['content'].tolist(), show_progress_bar=True)

    # --- Test different eps values ---
    print("\n--- Tuning DBSCAN eps parameter ---")
    for eps_value in [0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5]:
        dbscan = DBSCAN(eps=eps_value, min_samples=5, metric='cosine')
        clusters = dbscan.fit_predict(embeddings)
        
        # Calculate the number of actual clusters found (ignoring noise cluster '-1')
        num_clusters = len(set(clusters)) - (1 if -1 in clusters else 0)
        
        print(f"eps = {eps_value:.2f} -> Found {num_clusters} clusters")
