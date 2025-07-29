# scripts/full_pipeline.py
import os
import re
import pandas as pd
import joblib
from datetime import datetime
import matplotlib.pyplot as plt
from sentence_transformers import SentenceTransformer

PENDING_CSV = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux/logs/review.csv"

def log_info(msg): print(f"\033[94mℹ️ {msg}\033[0m")
def log_success(msg): print(f"\033[92m✅ {msg}\033[0m")
def log_warn(msg): print(f"\033[93m⚠️ {msg}\033[0m")
def log_error(msg): print(f"\033[91m❗ {msg}\033[0m")

def extract_logs(input_file):
    base, ext = os.path.splitext(input_file)
    output_file = f"{base}_extracted.csv"

    try:
        if ext.lower() == '.csv':
            df = pd.read_csv(input_file)
            possible_timestamp = [col for col in df.columns if 'time' in col.lower() or 'date' in col.lower()]
            possible_content = [col for col in df.columns if 'content' in col.lower() or 'message' in col.lower() or 'log' in col.lower()]

            timestamp_col = possible_timestamp[0] if possible_timestamp else None
            content_col = possible_content[0] if possible_content else None

            if timestamp_col and content_col:
                clean_df = df[[timestamp_col, content_col]].rename(columns={timestamp_col: 'timestamp', content_col: 'content'})
            else:
                clean_df = pd.DataFrame({'timestamp': datetime.now(), 'content': df.iloc[:, 0].astype(str)})
        else:
            # txt: each line becomes one log entry
            lines = []
            with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        match = re.match(r'^(\d{4}-\d{2}-\d{2}.*?)\s+(.*)$', line)
                        if match:
                            timestamp, content = match.groups()
                        else:
                            timestamp, content = datetime.now(), line
                        lines.append({'timestamp': timestamp, 'content': content})
            clean_df = pd.DataFrame(lines)

        clean_df['source'] = os.path.basename(input_file)
        clean_df = clean_df[['timestamp', 'source', 'content']]  # keep only 3 columns
        clean_df.dropna(subset=['content'], inplace=True)
        clean_df.to_csv(output_file, index=False)
        log_success(f"Extracted logs saved to: {output_file}")
        return output_file
    except Exception as e:
        log_error(f"Failed to extract: {e}")
        return None

def predict_logs(extracted_file):
    # Load embedding model and classifier
    log_info("🔄 Loading embedding model & classifier...")
    embedder = joblib.load("/home/rksha/Documents/Projects/log-anamoly-detector/Linux/model/sentence_embedder.pkl")
    model = joblib.load("/home/rksha/Documents/Projects/log-anamoly-detector/Linux/model/sgd_embedder.pkl")

    df = pd.read_csv(extracted_file)
    if 'content' not in df.columns:
        log_error("CSV must have 'content' column.")
        return None, None

    log_info("🧠 Generating embeddings & predicting...")

    # Generate embeddings
    embeddings = embedder.encode(df['content'].tolist(), batch_size=32, show_progress_bar=True)
    preds = model.predict(embeddings)
    df['label'] = preds

    output_file = extracted_file.replace("_extracted.csv", "_predicted.csv")
    df.to_csv(output_file, index=False)
    log_success(f"Predictions saved to: {output_file}")

    # Create and save summary plot
    try:
        counts = df['label'].value_counts().sort_index()
        labels = ['normal (0)', 'anomaly (1)']
        values = [counts.get(0, 0), counts.get(1, 0)]

        plt.figure(figsize=(5, 4))
        plt.bar(labels, values, color=['green', 'red'])
        plt.title("Prediction Summary")
        plt.ylabel("Number of logs")
        plt.tight_layout()

        plot_file = os.path.splitext(output_file)[0] + "_summary.png"
        plt.savefig(plot_file)
        plt.close()
        log_success(f"📊 Summary plot saved to: {plot_file}")
    except Exception as e:
        log_warn(f"Could not create summary plot: {e}")

    return df, output_file

def update_review(df):
    log_info("✏ Updating review.csv...")

    header = ['timestamp', 'source', 'content', 'label']

    if not os.path.exists(PENDING_CSV) or os.stat(PENDING_CSV).st_size == 0:
        df_pending = pd.DataFrame(columns=header)
        df_pending.to_csv(PENDING_CSV, index=False)
    else:
        df_pending = pd.read_csv(PENDING_CSV)

    df_pending = pd.concat([df_pending, df], ignore_index=True)
    df_pending.to_csv(PENDING_CSV, index=False)
    log_success(f"Added {len(df)} entries to review.csv.")

def show_summary(df):
    normal_count = (df['label'] == 0).sum()
    anomaly_count = (df['label'] == 1).sum()
    print(f"\n📊 Summary:")
    print(f"\033[92m✔ Normal: {normal_count}\033[0m")
    print(f"\033[91m⚠️ Anomaly: {anomaly_count}\033[0m")

def main():
    input_file = input("📂 Enter or drag & drop log file path (csv/txt): ").strip().strip('"').strip("'")
    if not os.path.exists(input_file):
        log_error("File not found.")
        return

    extracted = extract_logs(input_file)
    if extracted:
        df_pred, _ = predict_logs(extracted)
        if df_pred is not None:
            update_review(df_pred)
            show_summary(df_pred)

if __name__ == "__main__":
    main()
