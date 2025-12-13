# scripts/debug_worker.py
import sys
import os
import time

print("--- WORKER DIAGNOSTIC SCRIPT ---")
print(f"Python Executable Path: {sys.executable}")
print("\n--- Python Search Paths (sys.path) ---")
for path in sys.path:
    print(path)
print("\n--- VENV_PYTHON Environment Variable ---")
print(f"Value from os.environ: {os.environ.get('VENV_PYTHON', 'NOT SET')}")
print("\n--- DIAGNOSTIC COMPLETE ---")

# Keep the script running briefly so honcho doesn't restart it instantly
time.sleep(15)
