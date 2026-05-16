from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID


class MonitorResponse(BaseModel):
    id: UUID
    name: str
    url: str
    method: str
    headers: Optional[Dict[str, str]]
    body: Optional[Dict[str, Any]]
    expected_status: int
    check_interval: int
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True