from pydantic import BaseModel, Field
from typing import Optional, Dict, Any


class MonitorCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    url: str = Field(..., min_length=1, max_length=2048)
    method: str = Field(default="GET")
    headers: Optional[Dict[str, str]] = None
    body: Optional[Dict[str, Any]] = None
    expected_status: int = Field(default=200, ge=100, le=599)
    check_interval: int = Field(default=5, ge=1, le=1440)