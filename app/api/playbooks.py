# app/api/playbooks.py
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from pydantic import BaseModel, Field
from typing import List, Dict, Any
from sqlalchemy import create_engine, text
import json

from app.config import settings
from app import auth_utils
from app.audit import audit

router = APIRouter(prefix="/api/playbooks", tags=["Playbooks"])

from app.dependencies import RoleChecker
from app.api.models import UserRole

# Define Role Checkers
allow_analyst_write = RoleChecker([UserRole.ADMIN, UserRole.ANALYST])

# Pydantic models for request bodies
class PlaybookBase(BaseModel):
    name: str
    trigger_conditions: Dict[str, Any]
    actions: List[Dict[str, Any]]
    is_active: bool = True

class PlaybookCreate(PlaybookBase):
    pass

class PlaybookUpdate(PlaybookBase):
    pass

@router.get("/")
async def get_all_playbooks(user: dict = Depends(auth_utils.get_current_user)):
    """
    Fetches all playbooks from the database.
    """
    engine = create_engine(settings.DATABASE_URL)
    query = text("SELECT id, name, is_active, trigger_conditions, actions FROM playbooks ORDER BY name")
    
    with engine.connect() as connection:
        results = connection.execute(query).fetchall()
        playbooks = [dict(row._mapping) for row in results]
        return playbooks

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_playbook(playbook: PlaybookCreate, request: Request, background_tasks: BackgroundTasks, user: dict = Depends(allow_analyst_write)):
    """Creates a new playbook."""
    engine = create_engine(settings.DATABASE_URL)
    query = text("""
        INSERT INTO playbooks (name, is_active, trigger_conditions, actions)
        VALUES (:name, :is_active, :trigger_conditions, :actions)
        RETURNING id
    """)
    with engine.connect() as connection:
        with connection.begin() as transaction:
            result = connection.execute(query, {
                "name": playbook.name,
                "is_active": playbook.is_active,
                "trigger_conditions": json.dumps(playbook.trigger_conditions),
                "actions": json.dumps(playbook.actions)
            }).scalar_one_or_none()
    
    background_tasks.add_task(
        audit.log, user.get('username'), audit.ACTION_PLAYBOOK_CREATED, f"Playbook ID: {result}", request.client.host, "success"
    )
    return {"message": "Playbook created successfully", "id": result}

@router.put("/{playbook_id}", status_code=status.HTTP_200_OK)
async def update_playbook(playbook_id: int, playbook: PlaybookUpdate, request: Request, background_tasks: BackgroundTasks, user: dict = Depends(allow_analyst_write)):
    """Updates an existing playbook."""
    engine = create_engine(settings.DATABASE_URL)
    query = text("""
        UPDATE playbooks
        SET name = :name, is_active = :is_active, trigger_conditions = :trigger_conditions, actions = :actions
        WHERE id = :playbook_id
    """)
    with engine.connect() as connection:
        with connection.begin() as transaction:
            connection.execute(query, {
                "playbook_id": playbook_id,
                "name": playbook.name,
                "is_active": playbook.is_active,
                "trigger_conditions": json.dumps(playbook.trigger_conditions),
                "actions": json.dumps(playbook.actions)
            })
    background_tasks.add_task(
        audit.log, user.get('username'), audit.ACTION_PLAYBOOK_UPDATED, f"Playbook ID: {playbook_id}", request.client.host, "success"
    )
    return {"message": f"Playbook {playbook_id} updated successfully"}

@router.delete("/{playbook_id}", status_code=status.HTTP_200_OK)
async def delete_playbook(playbook_id: int, request: Request, background_tasks: BackgroundTasks, user: dict = Depends(allow_analyst_write)):
    """Deletes a playbook."""
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as connection:
        with connection.begin() as transaction:
            connection.execute(text("DELETE FROM playbooks WHERE id = :playbook_id"), {"playbook_id": playbook_id})
    background_tasks.add_task(
        audit.log, user.get('username'), audit.ACTION_PLAYBOOK_DELETED, f"Playbook ID: {playbook_id}", request.client.host, "success"
    )
    return {"message": f"Playbook {playbook_id} deleted successfully"}
