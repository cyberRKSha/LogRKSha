# scripts/debug_config.py
import sys
import os

# Add the project root directory to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

print("Attempting to import settings from app.config...")

try:
    from app.config import settings
    print("✅ Import successful!")
except Exception as e:
    print(f"❌ FAILED to import settings. Error: {e}")
    sys.exit(1)


print("\n--- Accessing all model paths from the settings object ---")
try:
    # We will try to access every model path property you've defined
    print(f"  EMBEDDER_PATH: {settings.EMBEDDER_PATH}")
    print(f"  SUPERVISED_MODEL_PATH: {settings.SUPERVISED_MODEL_PATH}")
    print(f"  AUTOENCODER_PATH: {settings.AUTOENCODER_PATH}")
    print(f"  THRESHOLD_PATH: {settings.THRESHOLD_PATH}")
    print(f"  EXPLAINER_PATH: {settings.EXPLAINER_PATH}")
    print(f"  LSTM_MODEL_PATH: {settings.LSTM_MODEL_PATH}") # The specific property that is failing

    print("\n✅ SUCCESS: All paths accessed without error.")
except AttributeError as e:
    print(f"\n❌ FAILURE: Encountered an AttributeError.")
    print(f"   Error message: {e}")
