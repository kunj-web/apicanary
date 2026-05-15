from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID


class AlertCreate(BaseModel):
    monitor_id: UUID
    alert_type: str = Field(...)
    recipient: str = Field(..., min_length=1, max_length=500)
    threshold_failures: int = Field(default=1, ge=1, le=100)