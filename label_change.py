# cleanup_db_labels.py
import sqlite3

DATABASE_FILE = "log_database.db"

def clean_labels():
    """
    Connects to the database and runs UPDATE queries to replace
    string labels with their integer equivalents.
    """
    print(f"Connecting to {DATABASE_FILE} to clean labels...")
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    # --- Define the updates ---
    updates = {
        'final_label': 0,
        'predicted_label': 0
    }
    
    try:
        # Update 'normal' to 0 in both columns
        cursor.execute("UPDATE logs SET final_label = 0 WHERE final_label = 'normal'")
        cursor.execute("UPDATE logs SET predicted_label = 0 WHERE predicted_label = 'normal'")
        print(f"Updated {cursor.rowcount} 'normal' labels to 0.")
        
        # Update 'anomaly' to 1 in both columns
        cursor.execute("UPDATE logs SET final_label = 1 WHERE final_label = 'anomaly'")
        cursor.execute("UPDATE logs SET predicted_label = 1 WHERE predicted_label = 'anomaly'")
        print(f"Updated {cursor.rowcount} 'anomaly' labels to 1.")
        
        conn.commit()
        print("✅ Database cleanup complete. All labels are now integers.")
        
    except Exception as e:
        print(f"An error occurred: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    clean_labels()
