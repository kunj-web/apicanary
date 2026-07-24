from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID

from app.core.header_crypto import redact_headers


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

    @field_validator("headers", mode="before")
    @classmethod
    def redact_sensitive_headers(cls, value):
        return redact_headers(value)

    class Config:
        from_attributes = True
