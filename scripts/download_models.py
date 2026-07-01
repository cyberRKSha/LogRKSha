# scripts/download_models.py
"""Download required pre-trained models for LogRKSha."""
from sentence_transformers import SentenceTransformer
from pathlib import Path

MODEL_DIR = Path(__file__).parent.parent / "model" / "sentence_transformer_model"

def main():
    print("Downloading sentence transformer model...")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    model.save(str(MODEL_DIR))
    print(f"Model saved to {MODEL_DIR}")
    print("\nProject-specific models (autoencoder, LSTM, etc.) must be trained")
    print("using scripts/auto_trainer.py after ingesting sufficient log data.")

if __name__ == "__main__":
    main()
