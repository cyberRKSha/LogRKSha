# scripts/train_lstm.py
import os
import dill
import numpy as np
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Masking, Dropout
from tensorflow.keras.preprocessing.sequence import pad_sequences
from sklearn.model_selection import train_test_split

# --- Configuration ---
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATA_FILE = os.path.join(PROJECT_ROOT, "data/training_sequences.pkl")
MODEL_OUTPUT_PATH = os.path.join(PROJECT_ROOT, "model/lstm_classifier_model.keras")

# --- Model Parameters ---
SEQUENCE_LEN = 20  # The fixed length of all sequences
EMBEDDING_DIM = 384 # The dimension of your sentence embeddings (all-MiniLM-L6-v2)

def load_and_prepare_data(max_len):
    """
    Loads the prepared sequence data, pads/truncates sequences to a fixed length,
    and splits it into training and testing sets.
    """
    print(f"Loading prepared sequence data from {DATA_FILE}...")
    with open(DATA_FILE, "rb") as f:
        data = dill.load(f)

    sequences = [item['sequence_embeddings'] for item in data]
    labels = [item['label'] for item in data]

    print(f"Padding/truncating sequences to a fixed length of {max_len}...")
    # This ensures every sequence has the same length.
    # Shorter sequences are padded with zeros, longer ones are cut from the beginning.
    padded_sequences = pad_sequences(sequences, maxlen=max_len, dtype='float32', padding='pre', truncating='pre')

    # Convert to numpy arrays for TensorFlow
    X = np.array(padded_sequences)
    y = np.array(labels)

    print("Splitting data into training and validation sets...")
    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    
    print(f"Training data shape: {X_train.shape}")
    print(f"Validation data shape: {X_val.shape}")
    
    return X_train, X_val, y_train, y_val

def build_lstm_model(input_shape):
    """
    Defines and compiles the LSTM classifier model.
    """
    print("Building LSTM model...")
    model = Sequential([
        # The input layer expects data of shape (SEQUENCE_LEN, EMBEDDING_DIM)
        # The Masking layer is crucial: it tells the LSTM to ignore the padded zero values.
        Masking(mask_value=0., input_shape=input_shape),
        
        # The LSTM layer learns the sequential patterns.
        LSTM(64, return_sequences=False), # return_sequences=False because it's the last LSTM layer
        
        # A standard hidden layer
        Dense(32, activation='relu'),
        
        # Dropout helps prevent the model from overfitting to the training data.
        Dropout(0.5),
        
        # The final output layer: a single neuron with a sigmoid activation
        # for binary classification (0=Normal, 1=Anomaly).
        Dense(1, activation='sigmoid')
    ])

    print("Compiling model...")
    model.compile(
        optimizer='adam',
        loss='binary_crossentropy',
        metrics=['accuracy']
    )
    
    model.summary()
    return model

if __name__ == "__main__":
    # 1. Load and prepare the data
    X_train, X_val, y_train, y_val = load_and_prepare_data(max_len=SEQUENCE_LEN)

    # 2. Build the model
    # The input shape is (sequence_length, number_of_features_per_step)
    input_shape = (SEQUENCE_LEN, EMBEDDING_DIM)
    model = build_lstm_model(input_shape)

    # 3. Train the model
    print("\n--- Starting Model Training ---")
    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=10, # You can adjust the number of epochs
        batch_size=32,
        callbacks=[tf.keras.callbacks.EarlyStopping(monitor='val_loss', patience=3, restore_best_weights=True)]
    )
    print("--- Model Training Complete ---")

    # 4. Save the trained model
    print(f"Saving trained model to {MODEL_OUTPUT_PATH}...")
    model.save(MODEL_OUTPUT_PATH)
    print("✅ Model saved successfully.")
