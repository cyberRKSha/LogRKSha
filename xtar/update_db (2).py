# scripts/update_db_again.py
import sqlite3
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATABASE_FILE = os.path.join(PROJECT_ROOT, "log_database.db")

def update_schema():
    con = sqlite3.connect(DATABASE_FILE)
    cur = con.cursor()
    print("Updating 'cluster' table to add column...")

    try:
        # Add a new column to store the cluster's vector representation (centroid)
        # cur.execute("ALTER TABLE cluster ADD COLUMN centroid BLOB")
        cur.execute("ALTER TABLE cluster ADD COLUMN name TEXT")
        cur.execute("ALTER TABLE cluster ADD COLUMN is_noise INTEGER DEFAULT 0")
        print("✅ column added successfully.")
    except sqlite3.OperationalError as e:
        # This will happen if the column already exists, which is fine.
        if "duplicate column name" in str(e):
            print("✅ column already exists.")
        else:
            raise e

    con.commit()
    con.close()

if __name__ == "__main__":
    update_schema()
