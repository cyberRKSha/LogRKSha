# app/api/users.py
"""
User Management API.
Handles user signup (viewer only) and admin user management.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from sqlalchemy import create_engine, text
import logging

from app.config import settings
from app import auth_utils
from app.dependencies import RoleChecker
from app.api.models import UserRole
from app.audit import audit
from app.rate_limiter import limiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/users", tags=["Users"])

# Role checkers
admin_only = RoleChecker([UserRole.ADMIN])


class UserSignup(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[str] = None
    password: str = Field(..., min_length=8)
    role: str = "viewer"  # Only viewer allowed via self-signup


class UserCreate(BaseModel):
    """For admin creating users"""
    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[str] = None
    password: str = Field(..., min_length=8)
    role: str = Field(..., pattern="^(admin|analyst|viewer)$")


class UserResponse(BaseModel):
    id: int
    username: str
    email: Optional[str]
    role: str
    is_two_factor_enabled: bool


class UserUpdate(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = Field(None, pattern="^(admin|analyst|viewer)$")
    password: Optional[str] = Field(None, min_length=8)


@router.post("/signup", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def signup(
    request: Request,
    user_data: UserSignup,
    background_tasks: BackgroundTasks
):
    """
    Public signup endpoint. Only allows viewer role.
    """
    # Force viewer role for public signup
    if user_data.role != "viewer":
        raise HTTPException(
            status_code=403,
            detail="Only viewer accounts can be created via signup. Contact an admin for elevated access."
        )
    
    engine = create_engine(settings.DATABASE_URL)
    
    # Check if username exists
    with engine.connect() as conn:
        existing = conn.execute(
            text("SELECT id FROM users WHERE username = :username"),
            {"username": user_data.username}
        ).fetchone()
        
        if existing:
            raise HTTPException(
                status_code=400,
                detail="Username already exists"
            )
    
    # Hash password and create user
    hashed_password = auth_utils.pwd_context.hash(user_data.password)
    
    with engine.connect() as conn:
        with conn.begin():
            result = conn.execute(
                text("""
                    INSERT INTO users (username, hashed_password, role, is_two_factor_enabled)
                    VALUES (:username, :password, :role, 0)
                    RETURNING id
                """),
                {
                    "username": user_data.username,
                    "password": hashed_password,
                    "role": "viewer"
                }
            )
            user_id = result.scalar()
    
    # Audit log
    client_ip = request.client.host if request.client else "unknown"
    background_tasks.add_task(
        audit.log, user_data.username, audit.ACTION_USER_CREATED,
        f"Self-signup as viewer", client_ip, "success"
    )
    
    logger.info(f"New viewer account created: {user_data.username}")
    
    return {"message": "Account created successfully", "user_id": user_id}


@router.get("/", response_model=List[UserResponse])
async def list_users(user: dict = Depends(admin_only)):
    """
    List all users. Admin only.
    """
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT id, username, role, is_two_factor_enabled
            FROM users ORDER BY username
        """)).fetchall()
        
        return [
            UserResponse(
                id=row.id,
                username=row.username,
                email=None,  # Not stored currently
                role=row.role or "analyst",
                is_two_factor_enabled=row.is_two_factor_enabled or False
            )
            for row in result
        ]


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_user(
    request: Request,
    user_data: UserCreate,
    background_tasks: BackgroundTasks,
    admin: dict = Depends(admin_only)
):
    """
    Create a new user with any role. Admin only.
    """
    engine = create_engine(settings.DATABASE_URL)
    
    # Check if username exists
    with engine.connect() as conn:
        existing = conn.execute(
            text("SELECT id FROM users WHERE username = :username"),
            {"username": user_data.username}
        ).fetchone()
        
        if existing:
            raise HTTPException(
                status_code=400,
                detail="Username already exists"
            )
    
    # Hash password and create user
    hashed_password = auth_utils.pwd_context.hash(user_data.password)
    
    with engine.connect() as conn:
        with conn.begin():
            result = conn.execute(
                text("""
                    INSERT INTO users (username, hashed_password, role, is_two_factor_enabled)
                    VALUES (:username, :password, :role, 0)
                    RETURNING id
                """),
                {
                    "username": user_data.username,
                    "password": hashed_password,
                    "role": user_data.role
                }
            )
            user_id = result.scalar()
    
    # Audit log
    client_ip = request.client.host if request.client else "unknown"
    background_tasks.add_task(
        audit.log, admin.get("username"), audit.ACTION_USER_CREATED,
        f"Created user {user_data.username} as {user_data.role}", client_ip, "success"
    )
    
    logger.info(f"Admin {admin.get('username')} created user: {user_data.username} ({user_data.role})")
    
    return {"message": f"User '{user_data.username}' created as {user_data.role}", "user_id": user_id}


@router.put("/{user_id}")
async def update_user(
    user_id: int,
    request: Request,
    user_data: UserUpdate,
    background_tasks: BackgroundTasks,
    admin: dict = Depends(admin_only)
):
    """
    Update a user's role or password. Admin only.
    """
    engine = create_engine(settings.DATABASE_URL)
    
    updates = []
    params = {"user_id": user_id}
    
    if user_data.role:
        updates.append("role = :role")
        params["role"] = user_data.role
    
    if user_data.password:
        updates.append("hashed_password = :password")
        params["password"] = auth_utils.pwd_context.hash(user_data.password)
    
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")
    
    with engine.connect() as conn:
        with conn.begin():
            conn.execute(
                text(f"UPDATE users SET {', '.join(updates)} WHERE id = :user_id"),
                params
            )
    
    # Audit log
    client_ip = request.client.host if request.client else "unknown"
    background_tasks.add_task(
        audit.log, admin.get("username"), "USER_UPDATED",
        f"Updated user ID {user_id}", client_ip, "success"
    )
    
    return {"message": f"User {user_id} updated successfully"}


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    request: Request,
    background_tasks: BackgroundTasks,
    admin: dict = Depends(admin_only)
):
    """
    Delete a user. Admin only.
    """
    # Prevent self-deletion
    if admin.get("id") == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        with conn.begin():
            conn.execute(
                text("DELETE FROM users WHERE id = :user_id"),
                {"user_id": user_id}
            )
    
    # Audit log
    client_ip = request.client.host if request.client else "unknown"
    background_tasks.add_task(
        audit.log, admin.get("username"), "USER_DELETED",
        f"Deleted user ID {user_id}", client_ip, "success"
    )
    
    return {"message": f"User {user_id} deleted successfully"}
