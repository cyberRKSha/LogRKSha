from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List
from app.dependencies import get_db, RoleChecker
from app.api.models import HoneytokenCreate, HoneytokenResponse, UserRole
from app.services.honeytoken import HoneytokenService
from app.auth_utils import get_current_user
from fastapi.templating import Jinja2Templates
from app.config import settings

templates = Jinja2Templates(directory=settings.TEMPLATES_PATH)

router = APIRouter(tags=["Security Operations"])

allow_analyst_write = RoleChecker([UserRole.ADMIN, UserRole.ANALYST])

@router.get("/security/setup-2fa", include_in_schema=False)
async def setup_2fa_page(request: Request, current_user = Depends(get_current_user)):
    return templates.TemplateResponse("setup_2fa.html", {"request": request, "user": current_user})

@router.get("/security", include_in_schema=False)
async def security_page(request: Request, current_user = Depends(get_current_user)):
    return templates.TemplateResponse("security.html", {"request": request, "user": current_user})

@router.get("/api/security/honeytokens", response_model=List[HoneytokenResponse])
def list_honeytokens(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return HoneytokenService.get_all(db)

@router.post("/api/security/honeytokens", response_model=HoneytokenResponse, dependencies=[Depends(allow_analyst_write)])
def create_honeytoken(
    ht_data: HoneytokenCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    # Pass current user's username (using dict access)
    return HoneytokenService.create_honeytoken(db, ht_data.type, ht_data.description, current_user['username'])

@router.delete("/api/security/honeytokens/{ht_id}", dependencies=[Depends(allow_analyst_write)])
def delete_honeytoken(
    ht_id: int,
    db: Session = Depends(get_db)
):
    HoneytokenService.delete_token(db, ht_id)
    return {"status": "deleted"}
