#!/usr/bin/env python3
"""
Admin User Creation Script

Creates admin or analyst users from the command line.
Usage:
    python scripts/create_user.py --username admin --role admin --password viewer123
    python scripts/create_user.py --username analyst1 --role analyst --password analyst123
"""

import argparse
import sys
import getpass
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from app.config import settings
from app.auth_utils import pwd_context


def create_user(username: str, password: str, role: str):
    """Create a new user in the database."""
    
    if role not in ["admin", "analyst", "viewer"]:
        print(f"❌ Invalid role: {role}. Must be admin, analyst, or viewer.")
        return False
    
    engine = create_engine(settings.DATABASE_URL)
    
    # Check if user exists
    with engine.connect() as conn:
        existing = conn.execute(
            text("SELECT id FROM users WHERE username = :username"),
            {"username": username}
        ).fetchone()
        
        if existing:
            print(f"❌ User '{username}' already exists.")
            return False
    
    # Hash password
    hashed_password = pwd_context.hash(password)
    
    # Create user
    with engine.connect() as conn:
        with conn.begin():
            result = conn.execute(
                text("""
                    INSERT INTO users (username, hashed_password, role, is_two_factor_enabled)
                    VALUES (:username, :password, :role, 0)
                    RETURNING id
                """),
                {
                    "username": username,
                    "password": hashed_password,
                    "role": role
                }
            )
            user_id = result.scalar()
    
    print(f"✅ User created successfully!")
    print(f"   Username: {username}")
    print(f"   Role: {role}")
    print(f"   User ID: {user_id}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Create admin or analyst users for LogAD"
    )
    parser.add_argument(
        "--username", "-u",
        required=True,
        help="Username for the new account"
    )
    parser.add_argument(
        "--role", "-r",
        choices=["admin", "analyst", "viewer"],
        default="analyst",
        help="Role for the user (default: analyst)"
    )
    parser.add_argument(
        "--password", "-p",
        help="Password (will prompt if not provided)"
    )
    
    args = parser.parse_args()
    
    # Get password
    password = args.password
    if not password:
        password = getpass.getpass(f"Enter password for {args.username}: ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("❌ Passwords do not match.")
            sys.exit(1)
    
    if len(password) < 8:
        print("❌ Password must be at least 8 characters.")
        sys.exit(1)
    
    success = create_user(args.username, password, args.role)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
