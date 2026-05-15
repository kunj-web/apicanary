from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID


class AlertResponse(BaseModel):
    id: UUID
    monitor_id: UUID
    alert_type: str
    recipient: str
    threshold_failures: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True