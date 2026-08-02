from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class NotificationDeliveryResponse(BaseModel):
    id: UUID
    alert_id: Optional[UUID]
    monitor_id: Optional[UUID]
    event_type: str
    channel: str
    recipient: str
    status: str
    attempt_count: int
    last_error: Optional[str]
    next_attempt_at: Optional[datetime]
    sent_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PaginatedNotificationDeliveriesResponse(BaseModel):
    items: list[NotificationDeliveryResponse]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    total: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class TestAlertResponse(BaseModel):
    delivery_id: UUID
    status: str
    message: str

