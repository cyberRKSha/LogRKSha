# scripts/monitor.py (HTTP LOG SHIPPER + ZEEK VERSION)
import os
import sys
import json
import time
import queue
import threading
import logging
import requests
from collections import defaultdict
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from systemd import journal

# --- Path Fix ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.config import settings
from app.log_config import setup_logging

# --- Setup ---
setup_logging()
logger = logging.getLogger(__name__)
log_processing_queue = queue.Queue()

# --- HTTP Shipper ---
def http_shipper(q: queue.Queue):
    """Takes messages from a local queue and ships them to the API via HTTP."""
    batch = []
    batch_size = 50
    last_ship_time = time.time()
    api_url = f"{settings.DASHBOARD_URL}/api/ingest/logs"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": settings.LOG_SHIPPER_API_KEY or ""
    }

    logger.info(f"HTTP Shipper started. Target: {api_url}")

    while True:
        try:
            # Get log with a short timeout to allow periodic flushing
            try:
                log_entry = q.get(timeout=1.0)
                if log_entry is None: # Sentinel check
                    return
                batch.append(log_entry)
                q.task_done()
            except queue.Empty:
                pass

            # Ship if batch is full OR time threshold reached
            current_time = time.time()
            if len(batch) >= batch_size or (batch and current_time - last_ship_time > 1.0):
                payload = {"logs": batch}
                try:
                    response = requests.post(api_url, json=payload, headers=headers, timeout=5)
                    if response.status_code == 200:
                        logger.info(f"Successfully shipped {len(batch)} logs.")
                        batch = [] # Clear batch
                        last_ship_time = current_time
                    else:
                        logger.error(f"Failed to ship logs. Status: {response.status_code}, Response: {response.text}")
                        time.sleep(2) # Backoff
                except requests.exceptions.RequestException as e:
                    logger.error(f"Network error shipping logs: {e}. Retrying...")
                    time.sleep(2) # Backoff

        except Exception as e:
            logger.error(f"Unexpected error in HTTP shipper: {e}")
            time.sleep(1)

# --- Zeek Integration Logic ---
def is_zeek_log_line(line):
    """Check if a line is a valid Zeek log entry (not header/comment)."""
    line = line.strip()
    return line and not line.startswith('#') and not line.startswith('//')

def process_existing_zeek_logs(file_path, log_queue):
    """Process existing content in Zeek log files on startup."""
    if '/zeek/' not in file_path:
        return 0  # Not a Zeek file
        
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        # Process last 5 valid Zeek log lines to capture recent activity
        valid_lines = [line for line in lines if is_zeek_log_line(line)]
        processed_count = 0
        
        for line in valid_lines[-5:]:  # Last 5 valid entries
            log_queue.put({
                'source': os.path.basename(file_path),
                'content': line.strip()
            })
            processed_count += 1
            logger.debug(f"Queued existing Zeek log: {line.strip()[:100]}...")
        
        logger.info(f"📊 Processed {processed_count} existing entries from {os.path.basename(file_path)}")
        return processed_count
        
    except Exception as e:
        logger.error(f"Error processing existing Zeek logs from {file_path}: {e}")
        return 0

def poll_zeek_files():
    """Continuously poll Zeek files for changes (backup to watchdog)"""
    zeek_files = [f for f in settings.LOG_FILES if '/zeek/' in f and os.path.exists(f)]
    file_sizes = {f: os.path.getsize(f) for f in zeek_files}
    
    logger.info(f"🔄 Starting Zeek file polling for {len(zeek_files)} files")
    
    while True:
        try:
            for file_path in zeek_files:
                if os.path.exists(file_path):
                    current_size = os.path.getsize(file_path)
                    last_size = file_sizes.get(file_path, 0)
                    
                    if current_size > last_size:
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                f.seek(last_size)
                                new_lines = f.readlines()
                                
                            for line in new_lines:
                                line_content = line.strip()
                                if line_content and is_zeek_log_line(line_content):
                                    log_processing_queue.put({
                                        'source': os.path.basename(file_path),
                                        'content': line_content
                                    })
                                    logger.info(f"🔍 [POLL] New Zeek log in {os.path.basename(file_path)}: {line_content[:100]}...")
                                    
                            file_sizes[file_path] = current_size
                            
                        except Exception as e:
                            logger.error(f"Error reading new content from {file_path}: {e}")
                            
            time.sleep(3)  # Poll every 3 seconds
            
        except Exception as e:
            logger.error(f"Error in Zeek file polling: {e}")
            time.sleep(5)

def zeek_status_check():
    """Check if Zeek is running and log status."""
    try:
        # Check if any Zeek logs have recent activity (last 5 minutes)
        zeek_files = [f for f in settings.LOG_FILES if '/zeek/' in f and os.path.exists(f)]
        
        if not zeek_files:
            return False
            
        recent_activity = False
        current_time = time.time()
        
        for zeek_file in zeek_files:
            try:
                file_mtime = os.path.getmtime(zeek_file)
                age_minutes = (current_time - file_mtime) / 60
                
                if age_minutes < 5:  # Modified in last 5 minutes
                    recent_activity = True
                    logger.info(f"✅ Active Zeek log: {os.path.basename(zeek_file)} (modified {age_minutes:.1f}m ago)")
                    
            except Exception as e:
                logger.warning(f"Error checking {zeek_file}: {e}")
        
        return recent_activity
        
    except Exception as e:
        logger.error(f"Error in Zeek status check: {e}")
        return False

def periodic_zeek_check():
    """Periodically check Zeek status and log information."""
    while True:
        try:
            time.sleep(300)  # Check every 5 minutes
            zeek_status_check()
        except Exception as e:
            logger.error(f"Error in periodic Zeek check: {e}")

# --- File Watching Logic ---
class MultiFileEventHandler(FileSystemEventHandler):
    """Handles events for a specific set of files within a directory."""
    def __init__(self, files_to_watch):
        super().__init__()
        self.files_to_watch = files_to_watch
        self.file_sizes = {}
        
        # Initialize file sizes and process existing Zeek content
        for f in files_to_watch:
            self.file_sizes[f] = os.path.getsize(f) if os.path.exists(f) else 0
            
            # Process existing Zeek logs on startup
            if os.path.exists(f):
                process_existing_zeek_logs(f, log_processing_queue)

    def on_modified(self, event):
        if event.src_path in self.files_to_watch:
            try:
                new_size = os.path.getsize(event.src_path)
                last_size = self.file_sizes.get(event.src_path, 0)
                if new_size < last_size: last_size = 0
                if new_size > last_size:
                    with open(event.src_path, 'r', encoding='utf-8', errors='ignore') as f:
                        f.seek(last_size)
                        for line in f:
                            line_content = line.strip()
                            if line_content:
                                # Skip Zeek headers but process all other lines
                                if '/zeek/' in event.src_path and not is_zeek_log_line(line_content):
                                    continue
                                    
                                log_processing_queue.put({
                                    'source': os.path.basename(event.src_path),
                                    'content': line_content
                                })
                                
                    self.file_sizes[event.src_path] = new_size
            except Exception as e:
                logger.error(f"Error processing modified file {event.src_path}: {e}")

def watch_journald(log_queue):
    """Reads ALL new logs directly from the systemd journal."""
    try:
        j = journal.Reader()
        j.seek_tail()
        j.get_previous()
        logger.info("Starting to monitor ALL systemd journal entries.")
        while True:
            if j.wait(): 
                for entry in j:
                    log_message = entry.get('MESSAGE', '')
                    log_source = entry.get('SYSLOG_IDENTIFIER', 'journald')
                    if log_message:
                        log_queue.put({
                            'source': f"journald:{log_source}",
                            'content': str(log_message)
                        })
    except Exception as e:
        logger.error(f"Error in journald monitoring thread: {e}", exc_info=True)

if __name__ == "__main__":
    if os.geteuid() != 0:
        logger.critical("Monitor must be run as root (using sudo) to access system logs.")
        sys.exit(1)

    # Start the HTTP Shipper thread instead of RabbitMQ
    shipper_thread = threading.Thread(target=http_shipper, args=(log_processing_queue,), daemon=True)
    shipper_thread.start()

    # Start journald monitor
    journal_thread = threading.Thread(target=watch_journald, args=(log_processing_queue,), daemon=True)
    journal_thread.start()

    # Start Zeek file polling
    zeek_poll_thread = threading.Thread(target=poll_zeek_files, daemon=True)
    zeek_poll_thread.start()

    # Start periodic Zeek status checker
    zeek_checker_thread = threading.Thread(target=periodic_zeek_check, daemon=True)
    zeek_checker_thread.start()

    files_by_dir = defaultdict(set)
    for file_path in settings.LOG_FILES:
        dir_path = os.path.dirname(file_path)
        files_by_dir[dir_path].add(file_path)

    observer = Observer()
    for dir_path, files in files_by_dir.items():
        event_handler = MultiFileEventHandler(files)
        observer.schedule(event_handler, dir_path, recursive=False)
        logger.info(f"Watching directory '{dir_path}' for {len(files)} file(s).")

    observer.start()
    logger.info("HTTP Log Shipper started with Zeek integration. Press CTRL+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down monitor.")
        log_processing_queue.put(None)

    observer.join()
