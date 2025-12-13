#!/bin/bash
# This master script starts all application services using honcho.

echo "--- Starting Log Anomaly Detector Services ---"

# # Define the full path to the honcho executable inside the venv
# VENV_HONCHO="$(pwd)/venv-s/bin/honcho"

# # Check if honcho exists
# if [ ! -f "$VENV_HONCHO" ]; then
#     echo "ERROR: Could not find honcho executable at $VENV_HONCHO"
#     exit 1
# fi

# echo "Starting honcho process manager..."
# echo "Your password may be required. Press Ctrl+C to stop all services."

# # We run honcho with sudo so it can manage the sudo-required 'monitor' process
# sudo "$VENV_HONCHO" start

# 1. Check if the virtual environment exists
VENV_PATH="venv-s/bin/activate"
if [ ! -f "$VENV_PATH" ]; then
    echo "ERROR: Virtual environment not found at $VENV_PATH"
    echo "Please run the setup steps in the README."
    exit 1
fi

# 2. Activate the virtual environment
echo "Activating Python virtual environment..."
source "$VENV_PATH"

# Find the full path to the Python executable in our virtual environment
VENV_PYTHON=$(which python)
# Export the path as an environment variable so honcho can access it
export VENV_PYTHON

echo "Starting honcho process manager..."
echo "Your password may be required for the log monitor. Press Ctrl+C to stop all services."

# 3. Run honcho with sudo, preserving the activated environment
# The "-E" flag tells sudo to preserve the user's environment variables (like PATH),
# which is how it finds the correct python from our venv.
honcho start
