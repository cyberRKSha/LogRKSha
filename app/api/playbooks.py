# app/api/playbooks.py
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from pydantic import BaseModel, Field
from typing import List, Dict, Any
from sqlalchemy import create_engine, text
import json

from app.config import settings
from app import auth_utils
from app.audit import audit
from app.rate_limiter import limiter

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
@limiter.limit("10/minute")
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
@limiter.limit("10/minute")
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
@limiter.limit("10/minute")
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


# --- Phase 5: LLM-Powered Playbook Generation ---

class PlaybookGenerateRequest(BaseModel):
    description: str = Field(..., description="Natural language description of the playbook to create")


@router.post("/generate", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def generate_playbook_with_llm(req: PlaybookGenerateRequest, request: Request, user: dict = Depends(allow_analyst_write)):
    """
    Uses LLM to generate a playbook from natural language description.
    Returns structured JSON that can be used to create a playbook.
    """
    from app.services.llm_service import get_llm_manager
    
    prompt = f"""You are a security automation expert. Generate a JSON playbook configuration based on this description:

Description: {req.description}

The playbook must have this exact structure (respond with ONLY the JSON, no explanation):
{{
  "name": "Descriptive name for the playbook",
  "trigger_conditions": {{
    "risk_score": {{"operator": ">=", "value": 0.7}},
    "or": {{
      "rule_name": {{"contains": "suspicious"}}
    }}
  }},
  "actions": [
    {{"action": "send_slack_alert", "channel": "#security-alerts", "message": "Alert message"}},
    {{"action": "block_ip_ufw", "duration_hours": 24}},
    {{"action": "create_case", "priority": "High"}}
  ],
  "is_active": true
}}

Available actions:
- send_slack_alert: Send to Slack with channel and message
- send_email_alert: Send email with recipients and subject
- block_ip_ufw: Block IP with optional duration_hours
- create_case: Auto-create investigation case with priority
- run_script: Execute custom script with path

Available trigger operators: >=, <=, ==, !=, contains, regex

Respond with ONLY valid JSON:"""

    try:
        manager = get_llm_manager()
        response, provider = await manager.generate(prompt)
        
        # Try to parse the response as JSON
        import re
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            playbook_json = json.loads(json_match.group())
            return {
                "generated_playbook": playbook_json,
                "provider": provider,
                "raw_response": response
            }
        else:
            return {
                "error": "Could not parse LLM response as JSON",
                "raw_response": response,
                "provider": provider
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM generation failed: {str(e)}")


@router.get("/{playbook_id}/executions")
async def get_playbook_executions(playbook_id: int, user: dict = Depends(auth_utils.get_current_user)):
    """Get execution history for a playbook."""
    engine = create_engine(settings.DATABASE_URL)
    query = text("""
        SELECT id, playbook_id, playbook_name, triggered_by_log_id, triggered_at, actions_executed, status, error_message
        FROM playbook_executions
        WHERE playbook_id = :playbook_id
        ORDER BY triggered_at DESC
        LIMIT 50
    """)
    with engine.connect() as conn:
        result = conn.execute(query, {"playbook_id": playbook_id})
        executions = [dict(row._mapping) for row in result]
        return executions

