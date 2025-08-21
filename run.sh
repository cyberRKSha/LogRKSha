#!/bin/bash
# This master script starts all application services using honcho.

echo "--- Starting Log Anomaly Detector Services ---"

# Define the full path to the honcho executable inside the venv
VENV_HONCHO="$(pwd)/venv-s/bin/honcho"

# Check if honcho exists
if [ ! -f "$VENV_HONCHO" ]; then
    echo "ERROR: Could not find honcho executable at $VENV_HONCHO"
    exit 1
fi

echo "Starting honcho process manager..."
echo "Your password may be required. Press Ctrl+C to stop all services."

# We run honcho with sudo so it can manage the sudo-required 'monitor' process
sudo "$VENV_HONCHO" start
