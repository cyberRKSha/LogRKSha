# app/api/models.py
from pydantic import BaseModel, Field
from typing import Optional, Dict

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
