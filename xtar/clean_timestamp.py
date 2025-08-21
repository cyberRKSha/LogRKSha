import sqlite3
from datetime import datetime
import os
from tqdm import tqdm

# --- Configuration ---
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATABASE_FILE = os.path.join(BASE_DIR, "log_database.db")

# --- Logging Helpers ---
def log_info(msg): print(f"\033[94mℹ️ {msg}\033[0m")
def log_success(msg): print(f"\032[92m✅ {msg}\033[0m")
def log_warn(msg): print(f"\033[93m⚠️ {msg}\033[0m")
def log_error(msg): print(f"\033[91m❗ {msg}\033[0m")

def clean_database_timestamps():
    """
    Reads all logs, standardizes timestamps using a comprehensive list of explicit
    format templates, and updates them in the database.
    """
    log_info("--- Starting Final Timestamp Cleaning Process (Template-Based) ---")

    conn = sqlite3.connect(DATABASE_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, timestamp FROM logs")
        all_logs = cursor.fetchall()
        log_info(f"Found {len(all_logs)} total log entries to check.")

        updates_to_make = []
        
        # --- THE FIX: An updated list of all known format templates in your database ---
        known_formats = [
            '%Y-%m-%dT%H:%M:%S.%f%z',  # Format: 2025-08-15T20:07:57.024163+00:00
            '%Y-%m-%dT%H:%M:%S.%f',     # NEW:   Handles 2025-08-16T17:50:35.014000
            '%Y-%m-%dT%H:%M:%S',        # Format: 2025-08-16T00:40:51
            '%Y-%m-%d %H:%M:%S.%f',     # Format: 2025-07-25 00:22:57.360241
            '%b %d, %Y %H:%M:%S',      # Format: Jul 19, 2025 10:56:46
        ]

        for log_id, original_timestamp_str in tqdm(all_logs, desc="Standardizing Timestamps"):
            parsed_time = None
            
            # Try to parse the timestamp using our list of known templates
            for fmt in known_formats:
                try:
                    ts_to_parse = original_timestamp_str
                    # Special handling for timezone format with a colon (e.g., +00:00)
                    if '%z' in fmt and ts_to_parse[-3] == ':':
                        ts_to_parse = ts_to_parse[:-3] + ts_to_parse[-2:]
                    
                    parsed_time = datetime.strptime(ts_to_parse, fmt)
                    break # Stop on the first successful parse
                except (ValueError, TypeError):
                    continue # Try the next format

            if parsed_time:
                # Convert to our standard format: UTC, then made naive for SQLite compatibility
                standard_iso_format = parsed_time.replace(tzinfo=None).isoformat(sep='T', timespec='milliseconds')
                
                if standard_iso_format != original_timestamp_str:
                    updates_to_make.append((standard_iso_format, log_id))
            else:
                log_warn(f"Could not parse timestamp for log ID {log_id}: '{original_timestamp_str}'")

        if not updates_to_make:
            log_success("All timestamps are already in a standard format. No changes needed.")
            return

        log_info(f"\nFound {len(updates_to_make)} timestamps to standardize. Updating database...")
        
        cursor.executemany("UPDATE logs SET timestamp = ? WHERE id = ?", updates_to_make)
        conn.commit()
        
        log_success(f"✅ Successfully cleaned and standardized {len(updates_to_make)} timestamps.")

    except Exception as e:
        log_error(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    clean_database_timestamps()
