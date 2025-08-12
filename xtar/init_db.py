# init_db.py
import sqlite3
import os

# --- Configuration ---
DATABASE_FILE = "log_database.db"

def initialize_database():
    """
    Initializes the database file and creates the necessary tables.
    """
    # Delete the old database file if it exists to start fresh
    if os.path.exists(DATABASE_FILE):
        os.remove(DATABASE_FILE)
        print(f"Removed old database file: {DATABASE_FILE}")

    # This will create the file
    connection = sqlite3.connect(DATABASE_FILE)
    cursor = connection.cursor()

    print(f"Creating new database file: {DATABASE_FILE}")

    # Create the logs table with the new schema
    cursor.execute('''
    CREATE TABLE logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        source TEXT NOT NULL,
        content TEXT NOT NULL,
        predicted_label INTEGER NOT NULL,
        final_label INTEGER NOT NULL,
        is_reviewed INTEGER NOT NULL DEFAULT 0
    );
    ''')

    print("✅ Table 'logs' created successfully.")

    # You can add more tables here in the future if needed

    connection.commit()
    connection.close()

if __name__ == "__main__":
    initialize_database()