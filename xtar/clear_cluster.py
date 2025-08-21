# scripts/clear_clusters.py
import sqlite3
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATABASE_FILE = os.path.join(PROJECT_ROOT, "log_database.db")

def clear_cluster_data():
    try:
        con = sqlite3.connect(DATABASE_FILE)
        cur = con.cursor()
        print("Connecting to database...")

        # Deleting all data from the logCluster table
        cur.execute("DELETE FROM logCluster")
        print("✅ Cleared all data from 'logCluster' table.")

        # Deleting all data from the cluster table
        cur.execute("DELETE FROM cluster")
        print("✅ Cleared all data from 'cluster' table.")

        con.commit()
        con.close()
        print("🚀 Database cleanup complete. You can now re-run the preparation process.")

    except Exception as e:
        print(f"❗ An error occurred: {e}")

if __name__ == "__main__":
    clear_cluster_data()
