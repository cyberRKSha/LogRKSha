# train_autoencoder.py
import os
import sqlite3
import pandas as pd
import joblib
import json
import numpy as np
from sentence_transformers import SentenceTransformer
import tensorflow as tf
from tensorflow import keras

# --- Configuration ---
BASE_DIR = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux"
DATABASE_FILE = os.path.join(BASE_DIR, "log_database.db")
EMBEDDER_PATH = os.path.join(BASE_DIR, "model/sentence_embedder.pkl")
AUTOENCODER_PATH = os.path.join(BASE_DIR, "model/autoencoder_model.keras")
THRESHOLD_PATH = os.path.join(BASE_DIR, "model/autoencoder_threshold.json")

def log_info(msg): print(f"\033[94mℹ️ {msg}\033[0m")
def log_success(msg): print(f"\032[92m✅ {msg}\033[0m")
def log_error(msg): print(f"\033[91m❗ {msg}\033[0m")

def train_autoencoder():
    log_info(f"Connecting to database: {DATABASE_FILE}")
    conn = sqlite3.connect(DATABASE_FILE)
    query = "SELECT content FROM logs WHERE final_label = 0"
    df = pd.read_sql_query(query, conn)
    conn.close()
    log_info(f"Fetched {len(df)} normal logs for training.")

    if len(df) < 500: # Autoencoders benefit from more data
        log_error("Not enough normal logs to train. Please review more logs.")
        return

    log_info("Loading sentence embedder...")
    embedder = joblib.load(EMBEDDER_PATH)
    log_info("Generating embeddings for normal logs...")
    embeddings = np.array(embedder.encode(df['content'].astype(str).tolist(), show_progress_bar=True))

    # --- Define Autoencoder Architecture ---
    input_dim = embeddings.shape[1]
    model = keras.Sequential([
        keras.layers.Input(shape=(input_dim,)),
        keras.layers.Dense(128, activation='relu'),
        keras.layers.Dense(64, activation='relu'),
        keras.layers.Dense(32, activation='relu'), # Bottleneck layer
        keras.layers.Dense(64, activation='relu'),
        keras.layers.Dense(128, activation='relu'),
        keras.layers.Dense(input_dim, activation='sigmoid') # Output matches input
    ])
    model.compile(optimizer='adam', loss='mae') # Mean Absolute Error loss
    log_info("Autoencoder model architecture created.")
    model.summary()

    log_info("Training Autoencoder model... (This may take some time)")
    # Train the model to reconstruct its own input
    model.fit(embeddings, embeddings,
              epochs=50,
              batch_size=64,
              shuffle=True,
              validation_split=0.1,
              callbacks=[keras.callbacks.EarlyStopping(monitor='val_loss', patience=5, restore_best_weights=True)])

    # --- Determine Anomaly Threshold ---
    log_info("Calculating anomaly detection threshold...")
    reconstructions = model.predict(embeddings)
    # Calculate the reconstruction error for each normal log
    train_loss = tf.keras.losses.mae(reconstructions, embeddings)
    # Set the threshold to be 3 standard deviations above the mean error
    threshold = np.mean(train_loss) + 3 * np.std(train_loss)

    # --- Save Model and Threshold ---
    model.save(AUTOENCODER_PATH)
    with open(THRESHOLD_PATH, 'w') as f:
        json.dump({'threshold': threshold}, f)

    log_success(f"Autoencoder model saved to {AUTOENCODER_PATH}")
    log_success(f"Anomaly threshold ({threshold}) saved to {THRESHOLD_PATH}")

if __name__ == "__main__":
    train_autoencoder()
