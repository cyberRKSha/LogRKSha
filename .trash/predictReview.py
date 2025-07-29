# # scripts/predict_and_review.py
# import pandas as pd
# import joblib
# import os

# PENDING_CSV = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux/logs/review.csv"

# def log_info(msg): print(f"\033[94mℹ️ {msg}\033[0m")
# def log_success(msg): print(f"\033[92m✅ {msg}\033[0m")
# def log_error(msg): print(f"\033[91m❗ {msg}\033[0m")

# def main():
#     # Ask user to input file path (can drag drop)
#     input_csv = input("📂 Enter or drag & drop the extracted CSV file path: ").strip().strip('"').strip("'")

#     if not os.path.exists(input_csv):
#         log_error("File not found.")
#         return

#     # Load data
#     df = pd.read_csv(input_csv)
#     if 'content' not in df.columns:
#         log_error("CSV must have 'content' column (use extract_logs.py first).")
#         return

#     # Load model
#     vectorizer = joblib.load("/home/rksha/Documents/Projects/log-anamoly-detector/Linux/model/hashing_vectorizer.pkl")
#     model = joblib.load("/home/rksha/Documents/Projects/log-anamoly-detector/Linux/model/sgd_incremental.pkl")

#     # Predict
#     log_info("🧠 Predicting...")
#     X = vectorizer.transform(df['content'])
#     preds = model.predict(X)
#     df['predicted_label'] = preds

#     # Save prediction file
#     base, ext = os.path.splitext(input_csv)
#     output_csv = f"{base}_predicted{ext}"
#     df.to_csv(output_csv, index=False)
#     log_success(f"✅ Predictions saved to: {output_csv}")

#     # Append to review.csv
#     log_info("✏ Adding to review.csv...")
#     if not os.path.exists(PENDING_CSV):
#         df_pending = pd.DataFrame(columns=['timestamp', 'source', 'content', 'label'])
#     else:
#         df_pending = pd.read_csv(PENDING_CSV)

#     new_rows = []
#     for idx, row in df.iterrows():
#         timestamp = row.get('timestamp', pd.Timestamp.now())
#         content = row['content']
#         label = row['predicted_label']
#         new_rows.append({'timestamp': timestamp, 'source': 'file', 'content': content, 'label': label})

#     df_new = pd.DataFrame(new_rows)
#     df_pending = pd.concat([df_pending, df_new], ignore_index=True)
#     df_pending.to_csv(PENDING_CSV, index=False)
#     log_success(f"✅ Added {len(new_rows)} entries to review.csv.")

#     # Show summary
#     log_info(f"Normal: {(preds==0).sum()}, Anomaly: {(preds==1).sum()}")

# if __name__ == "__main__":
#     main()





# scripts/predict_and_review.py
import pandas as pd
import joblib
import os

PENDING_CSV = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux/logs/review.csv"

def log_info(msg): print(f"\033[94mℹ️ {msg}\033[0m")
def log_success(msg): print(f"\033[92m✅ {msg}\033[0m")
def log_error(msg): print(f"\033[91m❗ {msg}\033[0m")

def main():
    input_csv = input("📂 Enter or drag & drop the extracted CSV file path: ").strip().strip('"').strip("'")

    if not os.path.exists(input_csv):
        log_error("File not found.")
        return

    df = pd.read_csv(input_csv)
    if 'content' not in df.columns:
        log_error("CSV must have 'content' column (use extract_logs.py first).")
        return

    # Load model
    vectorizer = joblib.load("/home/rksha/Documents/Projects/log-anamoly-detector/Linux/model/hashing_vectorizer.pkl")
    model = joblib.load("/home/rksha/Documents/Projects/log-anamoly-detector/Linux/model/sgd_incremental.pkl")

    log_info("🧠 Predicting...")
    X = vectorizer.transform(df['content'])
    preds = model.predict(X)

    df['label'] = preds  # add label column

    df = df[['timestamp', 'source', 'content', 'label']]  # keep consistent order

    base, ext = os.path.splitext(input_csv)
    output_csv = f"{base}_predicted{ext}"
    df.to_csv(output_csv, index=False)
    log_success(f"✅ Predictions saved to: {output_csv}")

    log_info("✏ Adding to review.csv...")
    if not os.path.exists(PENDING_CSV):
        df_pending = pd.DataFrame(columns=['timestamp', 'source', 'content', 'label'])
    else:
        df_pending = pd.read_csv(PENDING_CSV)

    df_pending = pd.concat([df_pending, df], ignore_index=True)
    df_pending.to_csv(PENDING_CSV, index=False)
    log_success(f"✅ Added {len(df)} entries to review.csv.")

    log_info(f"Normal: {(preds==0).sum()}, Anomaly: {(preds==1).sum()}")

if __name__ == "__main__":
    main()
