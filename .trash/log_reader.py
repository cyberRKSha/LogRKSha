# #!/usr/bin/env python3
# import os
# import time
# from systemd import journal

# # Step 1: Paths to extra log files
# HYPRLAND_LOG = os.path.expanduser("~/.cache/hypr/hyprland.log")
# PACMAN_LOG = "/var/log/pacman.log"

# # Step 2: Function to read latest N lines from Hyprland log
# def read_hyprland_log(n=50):
#     if os.path.exists(HYPRLAND_LOG):
#         with open(HYPRLAND_LOG, 'r', encoding='utf-8', errors='ignore') as f:
#             lines = f.readlines()
#             return lines[-n:]
#     else:
#         print("Hyprland log not found.")
#         return []

# # Step 3: Read from pacman.log
# def read_pacman_log(n=50):
#     if os.path.exists(PACMAN_LOG):
#         with open(PACMAN_LOG, 'r', encoding='utf-8', errors='ignore') as f:
#             lines = f.readlines()
#             return lines[-n:]
#     else:
#         print("pacman.log not found.")
#         return []

# # Step 4: Read last N system journal entries
# def read_journal_logs(n=50):
#     j = journal.Reader()
#     j.this_boot()                # limit to current boot
#     j.log_level(journal.LOG_INFO) # could use LOG_WARNING to filter more
#     j.seek_tail()
#     j.get_previous(n)            # go back N entries

#     entries = []
#     for entry in j:
#         message = entry.get('MESSAGE')
#         if message:
#             entries.append(message)
#     return entries

# # Step 5: Aggregate
# def get_all_logs(n=50):
#     logs = []
#     logs += read_journal_logs(n)
#     logs += read_hyprland_log(n)
#     logs += read_pacman_log(n)
#     return logs

# if __name__ == "__main__":
#     logs = get_all_logs(20)
#     print("\n=== Combined latest logs ===")
#     for log in logs:
#         print(log)



import time
import os
import subprocess
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import threading
import csv

log_storage_file = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux/logs/real_log.csv"

# Create logs folder and CSV if not exists
os.makedirs("logs", exist_ok=True)
if not os.path.exists(log_storage_file):
    with open(log_storage_file, "w", newline='', encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "source", "content"])

# Log files to watch
log_files = [
    "/var/log/pacman.log",
    os.path.expanduser("~/.cache/hypr/hyprland.log")
]

def process_line(line, source):
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{ts}] [{source}] {line.strip()}")

class LogFileHandler(FileSystemEventHandler):
    def __init__(self, path):
        self.path = path
        self._last_size = os.path.getsize(path) if os.path.exists(path) else 0

    def on_modified(self, event):
        if event.src_path != self.path:
            return
        try:
            current_size = os.path.getsize(self.path)
            with open(self.path, "r", encoding="utf-8", errors="ignore") as f:
                f.seek(self._last_size)
                new_lines = f.read().splitlines()
            self._last_size = current_size

            for line in new_lines:
                process_line(line, os.path.basename(self.path))
        except Exception as e:
            print(f"❌ Error reading {self.path}: {e}")

def monitor_file(path):
    observer = Observer()
    handler = LogFileHandler(path)
    observer.schedule(handler, path=os.path.dirname(path), recursive=False)
    observer.start()
    return observer

def monitor_journalctl():
    cmd = ["journalctl", "-f", "-n", "0", "-o", "short"]
    print("🔧 Starting journalctl live monitor...")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)
    for line in proc.stdout:
        process_line(line, "journalctl")
    proc.wait()

def process_line(line, source):
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{ts}] [{source}] {line.strip()}")
    # Append to CSV
    with open(log_storage_file, "a", newline='', encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([ts, source, line.strip()])

if __name__ == "__main__":
    print("🔍 Starting log file watchers...")
    observers = [monitor_file(f) for f in log_files if os.path.exists(f)]
    threading.Thread(target=monitor_journalctl, daemon=True).start()
    print("✅ Monitoring started. Ctrl+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("⏹ Stopping observers...")
        for obs in observers:
            obs.stop()
        for obs in observers:
            obs.join()
        print("🛑 Exited cleanly.")
