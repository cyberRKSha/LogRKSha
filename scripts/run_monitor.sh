#!/bin/bash
# This script runs the monitor.py with the correct Python interpreter
# from your virtual environment, using sudo for necessary permissions.

echo "--- Log Anomaly Detector Monitor ---"

# Find the absolute path to the project's root directory (one level up from 'scripts')
PROJECT_DIR=$(dirname "$(dirname "$(readlink -f "$0")")")

# Define the full path to your virtual environment's Python executable
VENV_PYTHON="$PROJECT_DIR/venv-s/bin/python"

# The full path to the script we want to run
MONITOR_SCRIPT="$PROJECT_DIR/scripts/monitor.py"

# Check if the venv Python exists
if [ ! -f "$VENV_PYTHON" ]; then
    echo "ERROR: Could not find Python interpreter at $VENV_PYTHON"
    echo "Please ensure the 'venv-stable' virtual environment exists."
    exit 1
fi

echo "Starting monitor with root privileges to read system logs..."
echo "Your password may be required."
echo "Press Ctrl+C to stop the monitor."

# Execute the monitor script using the venv's Python with sudo
sudo "$VENV_PYTHON" "$MONITOR_SCRIPT"
