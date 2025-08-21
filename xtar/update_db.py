# scripts/update_db.py
import sqlite3
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATABASE_FILE = os.path.join(PROJECT_ROOT, "log_database.db")

def setup_database():
    con = sqlite3.connect(DATABASE_FILE)
    cur = con.cursor()
    print("Adding new tables for review clustering...")

    # Table to store metadata for each identified cluster
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cluster (
            cluster_id TEXT PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'pending',
            log_count INTEGER NOT NULL,
            representative_log TEXT,
            first_seen TEXT,
            last_seen TEXT
        )
    """)

    # Table to map each log ID to its assigned cluster ID
    cur.execute("""
        CREATE TABLE IF NOT EXISTS logCluster (
            log_id INTEGER PRIMARY KEY,
            cluster_id TEXT NOT NULL,
            FOREIGN KEY (log_id) REFERENCES logs (id)
        )
    """)

    con.commit()
    con.close()
    print("✅ Database schema updated successfully.")

if __name__ == "__main__":
    setup_database()
