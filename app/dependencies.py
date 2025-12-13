# app/dependencies.py
from fastapi import Depends, HTTPException, status, Request
from typing import List
from app import auth_utils
from app.config import settings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Database Setup
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class RoleChecker:
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles

    async def __call__(self, request: Request):
        user = await auth_utils.get_current_user(request)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
        
        # Default to 'analyst' if role is missing (backward compatibility)
        user_role = user.get("role", "analyst")
        
        if user_role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail=f"Operation not permitted for role: {user_role}"
            )
        return user
