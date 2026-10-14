import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class ActivityItem(BaseModel):
    id: str
    event_type: str
    status: str
    monitor_id: uuid.UUID
    monitor_name: str
    monitor_url: str
    timestamp: datetime
    title: str
    summary: str
    version_id: Optional[uuid.UUID] = None
    comparison_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ActivityListResponse(BaseModel):
    items: List[ActivityItem]
    total: int
