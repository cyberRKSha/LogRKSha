import sys
import os
from app.config import settings
import re
import psycopg2, psycopg2.extras
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
from sqlalchemy import create_engine, text


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
    print("🚀 Starting stateless review session preparation...")

    try:
        embedder = SentenceTransformer(str(settings.EMBEDDER_PATH))
        with open(settings.DRAIN_MODEL_PATH, "rb") as f:
            miner = dill.load(f)
        print("✅ Official models loaded successfully.")
    except Exception as e:
        print(f"❗ Model loading failed: {e}. Please ensure models exist.")
        return f"Model loading failed: {e}"

    engine = create_engine(settings.DATABASE_URL)

    try:
        with engine.connect() as connection:
            # Use a transaction for all database modifications
            with connection.begin() as transaction:
                print("Clearing all old cluster data...")
                connection.execute(text("TRUNCATE TABLE logCluster, cluster RESTART IDENTITY"))

            # Read unreviewed logs using Pandas with the engine
            query = "SELECT id, content, timestamp, predicted_label FROM logs WHERE is_reviewed = 0"
            df = pd.read_sql_query(query, connection)
    
        if df.empty:
            print("✅ No new unreviewed logs to process.")
            # engine.close()
            return "No new logs to process."

        print(f"Generating embeddings for {len(df)} logs...")
        embeddings = embedder.encode(df['content'].tolist(), show_progress_bar=True)
        df['embedding'] = list(embeddings)

        print(f"Clustering all {len(df)} logs...")
        dbscan = DBSCAN(eps=0.25, min_samples=5, metric='cosine')
        df['cluster_id_num'] = dbscan.fit_predict(df['embedding'].tolist()) 

        newly_formed_clusters = df[df['cluster_id_num'] != -1]
        noise_logs = df[df['cluster_id_num'] == -1]

        print(f"Found {newly_formed_clusters['cluster_id_num'].nunique()} new clusters and {len(noise_logs)} noise logs.")

        with engine.connect() as connection:
                with connection.begin() as transaction:
                    # Process and insert the main clusters
                    for cluster_id, group in newly_formed_clusters.groupby('cluster_id_num'):
                        cluster_id_str = f"cluster_{int(datetime.now().timestamp())}_{cluster_id}"
                        centroid = np.mean(np.array(group['embedding'].tolist()), axis=0)
                        cluster_name = generate_cluster_name(group, miner)
                        avg_prediction = group['predicted_label'].mean()
                        confidence = abs(avg_prediction - 0.5) * 2

                        connection.execute(
                            text("""INSERT INTO cluster (cluster_id, name, status, log_count, representative_log, first_seen, last_seen, centroid, is_noise, confidence) 
                                    VALUES (:cid, :name, :status, :count, :rep_log, :first, :last, :cent, 0, :conf)"""),
                            {
                                "cid": cluster_id_str, "name": cluster_name, "status": 'pending', 
                                "count": len(group), "rep_log": group.iloc[0]['content'], 
                                "first": group['timestamp'].min(), "last": group['timestamp'].max(), 
                                "cent": centroid.tobytes(), "conf": confidence
                            }
                        )

                        mappings = [{"log_id": row['id'], "cluster_id": cluster_id_str} for index, row in group.iterrows()]
                        connection.execute(
                            text("INSERT INTO logCluster (log_id, cluster_id) VALUES (:log_id, :cluster_id) ON CONFLICT (log_id) DO NOTHING"),
                            mappings
                        )

                    # Process and insert the noise logs
                    for index, row in noise_logs.iterrows():
                        noise_id_str = f"noise_{row['id']}"
                        connection.execute(
                            text("""INSERT INTO cluster (cluster_id, name, status, log_count, representative_log, first_seen, last_seen, is_noise, centroid, predicted_label) 
                                    VALUES (:cid, :name, :status, 1, :rep_log, :ts, :ts, 1, :cent, :pl)"""),
                            {
                                "cid": noise_id_str, "name": "Unclustered Log", "status": 'pending', 
                                "rep_log": row['content'], "ts": row['timestamp'], 
                                "cent": row['embedding'].tobytes(), "pl": row['predicted_label']
                            }
                        )
                        connection.execute(
                            text("INSERT INTO logCluster (log_id, cluster_id) VALUES (:log_id, :cluster_id) ON CONFLICT (log_id) DO NOTHING"),
                            {"log_id": row['id'], "cluster_id": noise_id_str}
                        )

        msg = f"Processed {len(df)} logs."
        print(f"✅ {msg}")
        return msg
    
    except Exception as e:
        print(f"❗ An error occurred during review session preparation: {e}")
        return f"An error occurred: {e}"
