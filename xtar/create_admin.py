import sqlite3
import os
from passlib.context import CryptContext

# --- Configuration ---
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATABASE_FILE = os.path.join(BASE_DIR, "log_database.db")
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin"

# --- Main Script Logic ---
def setup_admin_user():
    """
    Deletes any existing admin user and creates a new one with a valid hashed password.
    """
    print(f"--- Setting up default admin user: {ADMIN_USERNAME} ---")
    
    # Use the same password hashing context as your auth.py file
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    # Hash the desired password
    hashed_password = pwd_context.hash(ADMIN_PASSWORD)
    
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()
    
    try:
        # Step 1: Delete any existing, potentially corrupted admin user
        print(f"Checking for existing user '{ADMIN_USERNAME}'...")
        cursor.execute("DELETE FROM users WHERE username = ?", (ADMIN_USERNAME,))
        if cursor.rowcount > 0:
            print(f"Removed existing user '{ADMIN_USERNAME}'.")

        # Step 2: Insert the new user with a correctly hashed password
        print(f"Creating new user '{ADMIN_USERNAME}' with a secure password hash...")
        cursor.execute("INSERT INTO users (username, hashed_password) VALUES (?, ?)", (ADMIN_USERNAME, hashed_password))
        
        conn.commit()
        print("✅ Success! Admin user has been created/reset successfully.")
        
    except Exception as e:
        print(f"❗ An error occurred: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    setup_admin_user()
