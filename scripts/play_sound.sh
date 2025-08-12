#!/bin/bash

# This script's only job is to play the alert sound.
# It will be called by the main Python script.

# Set the full path to your alert sound file
ALERT_FILE="/home/rksha/Documents/Projects/log-anamoly-detector/Linux/logs/alert.wav"

# Use paplay to play the sound
paplay "$ALERT_FILE"
