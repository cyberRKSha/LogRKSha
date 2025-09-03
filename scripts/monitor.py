# from app.config import settings
# import sys
# import os

# import pika
# import json
# import time
# import queue
# import threading
# import subprocess
# import logging
# from app.log_config import setup_logging
# from watchdog.observers import Observer
# from watchdog.events import FileSystemEventHandler
# from fastapi import FastAPI
# import threading # Use threading for journalctl

# setup_logging()
# app = FastAPI(title="Log Anomaly Detector API")
# logger = logging.getLogger(__name__)

# LOG_QUEUE_NAME = 'log_queue'

# def is_monitoring_active():
#     """Checks the status file. Defaults to True if file not found."""
#     if not os.path.exists(settings.STATUS_FILE):
#         return True
#     try:
#         with open(settings.STATUS_FILE, 'r') as f:
#             return json.load(f).get("is_active", True)
#     except (json.JSONDecodeError, IOError):
#         return True # Default to active on error
    
# def rabbitmq_publisher(log_queue: queue.Queue):

#     connection = pika.BlockingConnection(pika.ConnectionParameters(host=settings.RABBITMQ_HOST))
#     channel = connection.channel()
#     channel.queue_declare(queue=LOG_QUEUE_NAME, durable=True)
#     logger.info(" Publisher thread connected to RabbitMQ.")

#     while True:
#         try:
#             # Get a log from the thread-safe in-memory queue
#             log_message = log_queue.get()
#             if log_message is None: # Sentinel to stop the thread
#                 break
            
#             # Safely publish the message
#             channel.basic_publish(
#                 exchange='',
#                 routing_key=LOG_QUEUE_NAME,
#                 body=json.dumps(log_message),
#                 properties=pika.BasicProperties(delivery_mode=2)
#             )
#             log_queue.task_done()
#         except pika.exceptions.StreamLostError:
#             logger.error("RabbitMQ connection lost. Reconnecting...")
#             time.sleep(5)
#             # Re-establish connection
#             connection = pika.BlockingConnection(pika.ConnectionParameters(host=settings.RABBITMQ_HOST))
#             channel = connection.channel()
#             channel.queue_declare(queue=LOG_QUEUE_NAME, durable=True)
#         except pika.exceptions.AMQPConnectionError:
#             logger.error("Could not connect to RabbitMQ. Retrying in 5 seconds...")
#             time.sleep(5)
#             connection = pika.BlockingConnection(pika.ConnectionParameters(host=settings.RABBITMQ_HOST))
#             channel = connection.channel()
#             channel.queue_declare(queue=LOG_QUEUE_NAME, durable=True)
#         except Exception as e:
#             logger.error(f"Error in publisher thread: {e}")

#     connection.close()
#     logger.info("Publisher thread shut down.")

# class LogHandler(FileSystemEventHandler):
#     def __init__(self, file_path, log_queue):
#         super().__init__()
#         self.file_path = file_path
#         self.log_queue = log_queue
#         self._last_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

#     def on_modified(self, event):
#         if event.src_path == self.file_path and is_monitoring_active():
#             try:
#                 new_size = os.path.getsize(self.file_path)
#                 if new_size > self._last_size:
#                     with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
#                         f.seek(self._last_size)
#                         for line in f:
#                             # THIS IS THE CRITICAL CHECK
#                             if line.strip() and not line.strip().startswith("[LOG-WORKER]"):
#                                 self.log_queue.put({'source': os.path.basename(self.file_path), 'content': line.strip()})
#                     self._last_size = new_size
#             except FileNotFoundError:
#                 logger.warning(f"File vanished- LogHandler: {self.file_path}")
#                 self._last_size = 0
#             except Exception as e:
#                 logger.error(f"Error processing modified file {self.file_path}: {e}")

# def watch_journalctl(log_queue):
#     logger.info("🚀 Started journalctl monitoring...")
#     process = subprocess.Popen(['journalctl', '-f', '-o', 'cat','-u', 'sshd', '-u', 'sudo'],
#                                stdout=subprocess.PIPE, text=True, encoding='utf-8', errors='ignore')
#     for line in process.stdout:
#         # THIS IS THE CRITICAL CHECK
#         if line.strip() and not line.strip().startswith("[LOG-WORKER]") and is_monitoring_active():
#             log_queue.put({'source': 'journalctl', 'content': line.strip()})
#     return



# if __name__ == "__main__":

#     log_queue = queue.Queue()

#     # Start the single, dedicated publisher thread
#     publisher_thread = threading.Thread(target=rabbitmq_publisher, args=(log_queue,), daemon=True)
#     publisher_thread.start()

#     observer = Observer()
#     for file_path in settings.LOG_FILES:
#         if os.path.exists(file_path):
#             observer.schedule(LogHandler(file_path, log_queue), os.path.dirname(file_path), recursive=False)
#             logger.info(f"Watching {file_path}")
#         else:
#             logger.warning(f"File not found (skipped): {file_path}")

#     journal_thread = threading.Thread(target=watch_journalctl, args=(log_queue,), daemon=True)
#     journal_thread.start()
    
#     observer.start()
#     logger.info("Monitoring logs and publishing to queue. Press CTRL+C to stop.")

#     try:
#         while True:
#             time.sleep(1)
#     except KeyboardInterrupt:
#         print("\n🛑 Stopping monitor.")
#         observer.stop()
#         log_queue.put(None)
    
#     observer.join()
#     # connection.close()
#     publisher_thread.join()
















# scripts/monitor.py (UPGRADED VERSION)
import os
import sys
import json
import pika
import time
import queue
import threading
import logging
from collections import defaultdict

# --- Path Fix ---
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app.config import settings
from app.log_config import setup_logging

# --- Third-party library imports ---
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from systemd import journal

# --- Setup ---
setup_logging()
logger = logging.getLogger(__name__)
LOG_QUEUE_NAME = 'log_queue'
log_processing_queue = queue.Queue()

def rabbitmq_publisher(q: queue.Queue):
    """Takes messages from a local queue and publishes them to RabbitMQ."""
    while True:
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=settings.RABBITMQ_HOST))
            channel = connection.channel()
            channel.queue_declare(queue=LOG_QUEUE_NAME, durable=True)
            logger.info("RabbitMQ publisher thread connected and ready.")

            while True:
                message = q.get()
                if message is None: # Sentinel to stop the thread
                    connection.close()
                    logger.info("Publisher thread shut down.")
                    return
                
                channel.basic_publish(
                    exchange='',
                    routing_key=LOG_QUEUE_NAME,
                    body=json.dumps(message),
                    properties=pika.BasicProperties(delivery_mode=2)
                )
                q.task_done()
        except (pika.exceptions.AMQPConnectionError, pika.exceptions.StreamLostError) as e:
            logger.error(f"RabbitMQ connection error: {e}. Retrying in 5 seconds...")
            time.sleep(5)
        except Exception as e:
            logger.error(f"An unexpected error occurred in publisher thread: {e}")
            time.sleep(5)

class MultiFileEventHandler(FileSystemEventHandler):
    """Handles events for a specific set of files within a directory."""
    def __init__(self, files_to_watch):
        super().__init__()
        self.files_to_watch = files_to_watch
        self.file_sizes = {f: os.path.getsize(f) if os.path.exists(f) else 0 for f in files_to_watch}

    def on_modified(self, event):
        if event.src_path in self.files_to_watch:
            try:
                # Check for truncation (log rotation)
                new_size = os.path.getsize(event.src_path)
                last_size = self.file_sizes.get(event.src_path, 0)
                
                if new_size < last_size:
                    last_size = 0 # File was truncated, read from the start
                
                if new_size > last_size:
                    with open(event.src_path, 'r', encoding='utf-8', errors='ignore') as f:
                        f.seek(last_size)
                        for line in f:
                            if line.strip():
                                log_processing_queue.put({
                                    'source': os.path.basename(event.src_path),
                                    'content': line.strip()
                                })
                    self.file_sizes[event.src_path] = new_size
            except Exception as e:
                logger.error(f"Error processing modified file {event.src_path}: {e}")

def watch_journald(log_queue):
    """Reads new logs directly from the systemd journal using a native library."""
    try:
        j = journal.Reader()
        j.add_match(_SYSTEMD_UNIT="sshd.service")
        j.add_match(_SYSTEMD_UNIT="sudo.service")
        
        j.seek_tail()
        j.get_previous()
        
        logger.info("Starting to monitor systemd journal with native library.")
        while True:
            if j.wait():
                for entry in j:
                    log_queue.put({
                        'source': f"journald:{entry.get('SYSLOG_IDENTIFIER', 'unknown')}",
                        'content': entry.get('MESSAGE', '')
                    })
    except Exception as e:
        logger.error(f"Error in journald monitoring thread: {e}")


if __name__ == "__main__":
    setup_logging()
    publisher_thread = threading.Thread(target=rabbitmq_publisher, args=(log_processing_queue,), daemon=True)
    publisher_thread.start()

    journal_thread = threading.Thread(target=watch_journald, args=(log_processing_queue,), daemon=True)
    journal_thread.start()

    # Group files by their parent directory for efficient watching
    files_by_dir = defaultdict(set)
    for file_path in settings.LOG_FILES:
        # settings.LOG_FILES now returns a list of absolute paths that are confirmed to exist
        dir_path = os.path.dirname(file_path)
        files_by_dir[dir_path].add(file_path)

    observer = Observer()
    for dir_path, files in files_by_dir.items():
        event_handler = MultiFileEventHandler(files)
        observer.schedule(event_handler, dir_path, recursive=False)
        logger.info(f"Watching directory '{dir_path}' for {len(files)} file(s).")
    
    observer.start()
    logger.info("File and journal monitoring has started. Press CTRL+C to stop.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down monitor.")
        observer.stop()
        log_processing_queue.put(None) # Signal publisher to stop
    
    observer.join()
    publisher_thread.join()