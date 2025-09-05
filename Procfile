worker: bash -c "touch /tmp/worker.lock; trap 'rm -f /tmp/worker.lock' EXIT; /home/rksha/Documents/Projects/log-anamoly-detector/Linux/venv-s/bin/python -m scripts.worker"
monitor: bash -c "touch /tmp/monitor.lock; trap 'rm -f /tmp/monitor.lock' EXIT; sudo /home/rksha/Documents/Projects/log-anamoly-detector/Linux/venv-s/bin/python -m scripts.monitor"
