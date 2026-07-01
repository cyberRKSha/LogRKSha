import os
import io
import pyotp
import qrcode
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from jose import JWTError, jwt
from passlib.context import CryptContext
import psycopg2, psycopg2.extras
from pathlib import Path
from starlette.responses import StreamingResponse
from app.config import settings
from sqlalchemy import create_engine, text


# --- Security & Auth Setup ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_token_from_cookie(request: Request) -> Optional[str]:
    token = request.cookies.get("access_token")
    if token and token.startswith("Bearer "):
        return token.split("Bearer ")[1]
    return None

async def get_current_user(request: Request):
    # token = request.cookies.get("access_token")
    # if not token or not token.startswith("Bearer "):
    #     return None
    
    # token = token.split("Bearer ")[1]
    token = get_token_from_cookie(request)
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username = payload.get("sub")
        if not isinstance(username, str) or not username: 
            return None
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
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

# def get_user(username: str):
#     conn = psycopg2.connect(settings.DATABASE_FILE)
#     conn.row_factory = psycopg2.Row
#     user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
#     conn.close()
#     return dict(user) if user else None

def get_user(username: str):

    engine = create_engine(settings.DATABASE_URL)
    sql_query = text("SELECT * FROM users WHERE username = :username")
    
    try:
        with engine.connect() as connection:
            result = connection.execute(sql_query, {"username": username}).fetchone()
            if result:
                # Convert the SQLAlchemy Row object to a dictionary
                return dict(result._mapping)
            return None
    except Exception as error:
        print(f"Database error in get_user: {error}")
        return None

# --- 2FA Utilities ---
def generate_2fa_secret():
    return pyotp.random_base32()

def get_2fa_provisioning_uri(username: str, secret: str):
    return pyotp.totp.TOTP(secret).provisioning_uri(name=username, issuer_name="LogAnomalyApp")

def verify_2fa_code(secret: str, code: str) -> bool:
    if not secret: return False # Cannot verify if secret is missing
    totp = pyotp.TOTP(secret)
    return totp.verify(code)