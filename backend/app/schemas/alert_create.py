from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class AlertCreate(BaseModel):
    monitor_id: UUID
    alert_type: Literal["email"]
    recipient: Annotated[EmailStr, Field(max_length=254)]
    threshold_failures: int = Field(default=1, ge=1, le=100)
