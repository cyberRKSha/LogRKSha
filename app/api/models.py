# app/api/models.py
from pydantic import BaseModel, Field
from typing import Optional, Dict
from enum import Enum

class UserRole(str, Enum):
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"

class SearchQuery(BaseModel):
    keyword: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    # label: Optional[int] = None
    source: Optional[str] = None
    ip_address: Optional[str] = None
    detection_method: Optional[str] = None
    risk_score_min: Optional[float] = Field(None, ge=0, le=1) # ge=0, le=1 adds validation
    filter_logic: str = 'and' # Default to 'and'
    chart_images: Optional[Dict[str, str]] = None

class ReviewUpdateItem(BaseModel):
    id: int
    new_label: int

class AlertStatusUpdate(BaseModel):
    status: str

class BulkLabelUpdate(BaseModel):
    new_label: int

class ManualLogsQuery(BaseModel):
    sort_by: str = "timestamp"
    sort_order: str = "desc"

from datetime import datetime

class HoneytokenType(str, Enum):
    AWS_KEY = "AWS Access Key"
    DB_CREDS = "Database Credentials"
    GENERIC = "Generic Token"

class HoneytokenCreate(BaseModel):
    type: HoneytokenType
    description: str

class HoneytokenResponse(BaseModel):
    id: int
    token: str
    type: str
    description: str
    created_at: datetime
    created_by: Optional[str] = None
    trigger_count: int
    is_active: bool
    
    class Config:
        from_attributes = True
