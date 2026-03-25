# app/api/cases.py
"""
Case Management API - Investigation ticketing system
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import create_engine, text
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from app.config import settings
from app import auth_utils
from app.dependencies import RoleChecker
from app.audit import audit

router = APIRouter(prefix="/api/cases", tags=["Cases"])

# Role checkers
allow_analyst = RoleChecker(["admin", "analyst"])


class CaseCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str = "Medium"
    assigned_to: Optional[int] = None


class CaseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    assigned_to: Optional[int] = None


class AlertLink(BaseModel):
    alert_ids: List[int]


def get_db_connection():
    engine = create_engine(settings.DATABASE_URL)
    return engine.connect()


@router.get("")
async def list_cases(
    status_filter: Optional[str] = None,
    user: dict = Depends(allow_analyst)
):
    """List all cases, optionally filtered by status"""
    query = """
        SELECT c.*, u.username as assigned_to_name,
               (SELECT COUNT(*) FROM case_alerts WHERE case_id = c.id) as alert_count
        FROM cases c
        LEFT JOIN users u ON c.assigned_to = u.id
    """
    params = {}
    
    if status_filter:
        query += " WHERE c.status = :status"
        params["status"] = status_filter
    
    query += " ORDER BY c.created_at DESC"
    
    with get_db_connection() as conn:
        result = conn.execute(text(query), params)
        cases = [dict(row._mapping) for row in result]
    
    return cases


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_case(
    case: CaseCreate,
    user: dict = Depends(allow_analyst)
):
    """Create a new investigation case"""
    query = text("""
        INSERT INTO cases (title, description, priority, assigned_to, created_by)
        VALUES (:title, :description, :priority, :assigned_to, :created_by)
        RETURNING id, created_at
    """)
    
    with get_db_connection() as conn:
        with conn.begin():
            result = conn.execute(query, {
                "title": case.title,
                "description": case.description,
                "priority": case.priority,
                "assigned_to": case.assigned_to,
                "created_by": user.get("id")
            })
            row = result.fetchone()
    
    # audit.log is synchronous, no await needed
    audit.log(user.get("username", "unknown"), "case_created", f"/api/cases/{row.id}", "", "success", case.title)
    
    return {"id": row.id, "created_at": row.created_at}


@router.get("/{case_id}")
async def get_case(case_id: int, user: dict = Depends(allow_analyst)):
    """Get case details including linked alerts"""
    case_query = text("""
        SELECT c.*, u.username as assigned_to_name
        FROM cases c
        LEFT JOIN users u ON c.assigned_to = u.id
        WHERE c.id = :case_id
    """)
    
    alerts_query = text("""
        SELECT a.*, ca.added_at
        FROM alerts a
        JOIN case_alerts ca ON a.id = ca.alert_id
        WHERE ca.case_id = :case_id
        ORDER BY a.timestamp DESC
    """)
    
    with get_db_connection() as conn:
        case_result = conn.execute(case_query, {"case_id": case_id})
        case = case_result.fetchone()
        
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        
        alerts_result = conn.execute(alerts_query, {"case_id": case_id})
        alerts = [dict(row._mapping) for row in alerts_result]
    
    return {**dict(case._mapping), "alerts": alerts}


@router.patch("/{case_id}")
async def update_case(
    case_id: int,
    updates: CaseUpdate,
    user: dict = Depends(allow_analyst)
):
    """Update case details"""
    set_clauses = []
    params = {"case_id": case_id}
    
    for field, value in updates.model_dump(exclude_none=True).items():
        set_clauses.append(f"{field} = :{field}")
        params[field] = value
    
    if not set_clauses:
        raise HTTPException(status_code=400, detail="No updates provided")
    
    set_clauses.append("updated_at = NOW()")
    
    query = text(f"UPDATE cases SET {', '.join(set_clauses)} WHERE id = :case_id")
    
    with get_db_connection() as conn:
        with conn.begin():
            result = conn.execute(query, params)
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Case not found")
    
    return {"status": "updated"}


@router.post("/{case_id}/alerts")
async def link_alerts_to_case(
    case_id: int,
    link: AlertLink,
    user: dict = Depends(allow_analyst)
):
    """Link alerts to a case"""
    query = text("""
        INSERT INTO case_alerts (case_id, alert_id)
        VALUES (:case_id, :alert_id)
        ON CONFLICT DO NOTHING
    """)
    
    with get_db_connection() as conn:
        with conn.begin():
            for alert_id in link.alert_ids:
                conn.execute(query, {"case_id": case_id, "alert_id": alert_id})
    
    return {"linked": len(link.alert_ids)}


@router.delete("/{case_id}/alerts/{alert_id}")
async def unlink_alert_from_case(
    case_id: int,
    alert_id: int,
    user: dict = Depends(allow_analyst)
):
    """Remove an alert from a case"""
    query = text("DELETE FROM case_alerts WHERE case_id = :case_id AND alert_id = :alert_id")
    
    with get_db_connection() as conn:
        with conn.begin():
            conn.execute(query, {"case_id": case_id, "alert_id": alert_id})
    
    return {"status": "unlinked"}


@router.delete("/{case_id}")
async def delete_case(case_id: int, user: dict = Depends(allow_analyst)):
    """Delete a case and its alert links"""
    with get_db_connection() as conn:
        with conn.begin():
            # First delete linked alerts
            conn.execute(text("DELETE FROM case_alerts WHERE case_id = :case_id"), {"case_id": case_id})
            # Then delete the case
            result = conn.execute(text("DELETE FROM cases WHERE id = :case_id"), {"case_id": case_id})
            if result.rowcount == 0:
                raise HTTPException(status_code=404, detail="Case not found")
    
    audit.log(user.get("username", "unknown"), "case_deleted", f"/api/cases/{case_id}", "", "success", str(case_id))
    return {"status": "deleted"}
