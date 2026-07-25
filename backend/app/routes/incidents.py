from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.models import Incident, Monitor, User
from app.schemas.monitor_analytics import (
    IncidentResponse,
    PaginatedIncidentsResponse,
)

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


def _incident_response(
    incident: Incident,
    monitor_name: str,
) -> IncidentResponse:
    return IncidentResponse(
        id=incident.id,
        monitor_id=incident.monitor_id,
        monitor_name=monitor_name,
        started_at=incident.started_at,
        resolved_at=incident.resolved_at,
        duration_minutes=incident.duration_minutes,
        status=incident.status,
        created_at=incident.created_at,
    )


@router.get("", response_model=PaginatedIncidentsResponse)
async def list_incidents(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    incident_status: Optional[Literal["ongoing", "resolved"]] = Query(
        default=None,
        alias="status",
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List incidents for every monitor owned by the current user."""
    base_query = (
        db.query(Incident, Monitor.name)
        .join(Monitor, Monitor.id == Incident.monitor_id)
        .filter(Monitor.user_id == current_user.id)
    )
    if incident_status:
        base_query = base_query.filter(Incident.status == incident_status)

    total = (
        base_query.with_entities(func.count(Incident.id)).scalar() or 0
    )
    rows = (
        base_query.order_by(
            Incident.started_at.desc(),
            Incident.id.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PaginatedIncidentsResponse(
        items=[
            _incident_response(incident, monitor_name)
            for incident, monitor_name in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/{incident_id}", response_model=IncidentResponse)
async def get_incident(
    incident_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get an incident only when its monitor belongs to the current user."""
    row = (
        db.query(Incident, Monitor.name)
        .join(Monitor, Monitor.id == Incident.monitor_id)
        .filter(
            Incident.id == incident_id,
            Monitor.user_id == current_user.id,
        )
        .first()
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )

    incident, monitor_name = row
    return _incident_response(incident, monitor_name)
