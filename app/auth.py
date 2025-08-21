import os
import io
import pyotp
import qrcode
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from jose import JWTError, jwt
from passlib.context import CryptContext
import sqlite3
from pathlib import Path
from starlette.responses import StreamingResponse

# --- Configuration ---
DATABASE_FILE = Path(__file__).parent.parent / "log_database.db"
SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# --- Security & Auth Setup ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_token_from_cookie(request: Request) -> Optional[str]:
    token = request.cookies.get("access_token")
    if token and token.startswith("Bearer "):
        return token.split("Bearer ")[1]
    return None

async def get_current_user(request: Request):
    token = request.cookies.get("access_token")
    if not token or not token.startswith("Bearer "):
        return None
    
    token = token.split("Bearer ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None: return None
    except JWTError:
        return None
    
    user = get_user(username=username)
    return user

# --- Password Utilities ---
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_user(username: str):
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return dict(user) if user else None

# --- 2FA Utilities ---
def generate_2fa_secret():
    return pyotp.random_base32()

def get_2fa_provisioning_uri(username: str, secret: str):
    return pyotp.totp.TOTP(secret).provisioning_uri(name=username, issuer_name="LogAnomalyApp")

def verify_2fa_code(secret: str, code: str) -> bool:
    if not secret: return False # Cannot verify if secret is missing
    totp = pyotp.TOTP(secret)
    return totp.verify(code)