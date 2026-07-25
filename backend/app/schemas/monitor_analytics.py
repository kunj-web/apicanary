from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class CheckResponse(BaseModel):
    id: UUID
    monitor_id: UUID
    status: int
    response_time: Optional[int]
    status_code: Optional[int]
    error_message: Optional[str]
    checked_at: datetime

    class Config:
        from_attributes = True


class PaginatedChecksResponse(BaseModel):
    items: list[CheckResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class IncidentResponse(BaseModel):
    id: UUID
    monitor_id: UUID
    monitor_name: str
    started_at: datetime
    resolved_at: Optional[datetime]
    duration_minutes: Optional[int]
    status: str
    created_at: datetime


class PaginatedIncidentsResponse(BaseModel):
    items: list[IncidentResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class UptimeResponse(BaseModel):
    monitor_id: UUID
    window_hours: int
    from_time: datetime
    to_time: datetime
    uptime_percentage: Optional[float]
    total_checks: int
    successful_checks: int
    failed_checks: int


class ResponseTimePoint(BaseModel):
    checked_at: datetime
    response_time: int
    status: int
    status_code: Optional[int]


class ResponseTimeResponse(BaseModel):
    monitor_id: UUID
    window_hours: int
    average_ms: Optional[float]
    minimum_ms: Optional[int]
    maximum_ms: Optional[int]
    p95_ms: Optional[int]
    points: list[ResponseTimePoint]


class LatestStatusResponse(BaseModel):
    monitor_id: UUID
    monitor_status: str
    latest_check: Optional[CheckResponse]
