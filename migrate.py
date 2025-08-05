# migrate_csv_to_db.py
import pandas as pd
import sqlite3
import os

# --- Configuration ---
CSV_FILE = "/home/rksha/Documents/Projects/log-anamoly-detector/Linux/logs/real_log.csv"
DATABASE_FILE = "log_database.db"

def migrate_data():
    """
    Reads data from the old real_log.csv and inserts it into the
    new SQLite database. This is a one-time operation.
    """
    if not os.path.exists(CSV_FILE):
        print(f"Error: CSV file not found at {CSV_FILE}. Aborting.")
        return

    if not os.path.exists(DATABASE_FILE):
        print(f"Error: Database file not found at {DATABASE_FILE}.")
        print("Please run 'python init_db.py' first to create the database.")
        return

    print(f"Reading data from {CSV_FILE}...")
    try:
        # Read the existing ground-truth data
        df = pd.read_csv(CSV_FILE)
        print(f"Found {len(df)} records to migrate.")

        # --- Prepare the DataFrame to match the new database schema ---
        # The 'label' column in the CSV is the final, corrected label.
        df.rename(columns={'label': 'final_label'}, inplace=True)

        # For historical data, we can assume the predicted_label was the same as the final one.
        df['predicted_label'] = df['final_label']

        # All data in real_log.csv is considered reviewed.
        df['is_reviewed'] = 1

        # Reorder columns to match the database table exactly
        df = df[['timestamp', 'source', 'content', 'predicted_label', 'final_label', 'is_reviewed']]

        # --- Connect to the database and insert the data ---
        conn = sqlite3.connect(DATABASE_FILE)
        print(f"Connecting to database {DATABASE_FILE}...")

        # Use df.to_sql() for an efficient bulk insert.
        # 'if_exists="append"' ensures we don't delete any existing data.
        df.to_sql('logs', conn, if_exists='append', index=False)

        conn.close()
        print(f"✅ Successfully migrated {len(df)} records to the 'logs' table.")

    except Exception as e:
        print(f"An error occurred during migration: {e}")

if __name__ == "__main__":
    migrate_data()
