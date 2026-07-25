import logging
import math

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func
from sqlalchemy.orm import Session
from app.schemas import (
    CheckResponse,
    IncidentResponse,
    LatestStatusResponse,
    MonitorCreate,
    MonitorResponse,
    PaginatedChecksResponse,
    PaginatedIncidentsResponse,
    ResponseTimePoint,
    ResponseTimeResponse,
    UptimeResponse,
)
from app.models import Check, Incident, Monitor, User
from app.core.dependencies import get_db, get_current_user
from app.core.header_crypto import protect_headers, protect_updated_headers
from app.tasks.monitor_checks import check_monitor
from uuid import UUID, uuid4
from datetime import datetime, timedelta, timezone

router = APIRouter(prefix="/api/monitors", tags=["monitors"])
logger = logging.getLogger(__name__)


def _owned_monitor(db: Session, monitor_id: UUID, user_id: UUID) -> Monitor:
    monitor = db.query(Monitor).filter(
        Monitor.id == monitor_id,
        Monitor.user_id == user_id,
    ).first()
    if not monitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Monitor not found",
        )
    return monitor


def _pagination(total: int, page: int, page_size: int) -> dict[str, int]:
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.post("", response_model=MonitorResponse)
async def create_monitor(
    monitor_data: MonitorCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create new monitor"""
    monitor = Monitor(
        id=uuid4(),
        user_id=current_user.id,
        name=monitor_data.name,
        url=str(monitor_data.url),
        method=monitor_data.method,
        headers=protect_headers(monitor_data.headers),
        body=monitor_data.body,
        expected_status=monitor_data.expected_status,
        check_interval=monitor_data.check_interval,
        status="active",
    )
    db.add(monitor)
    db.commit()
    db.refresh(monitor)
    return MonitorResponse.model_validate(monitor)


@router.get("", response_model=list[MonitorResponse])
async def list_monitors(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all monitors for current user"""
    monitors = db.query(Monitor).filter(Monitor.user_id == current_user.id).all()
    return [MonitorResponse.model_validate(m) for m in monitors]


@router.get(
    "/{monitor_id}/checks",
    response_model=PaginatedChecksResponse,
)
async def list_monitor_checks(
    monitor_id: UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return newest checks first with stable, bounded pagination."""
    _owned_monitor(db, monitor_id, current_user.id)
    query = db.query(Check).filter(Check.monitor_id == monitor_id)
    total = query.with_entities(func.count(Check.id)).scalar() or 0
    checks = (
        query.order_by(Check.checked_at.desc(), Check.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PaginatedChecksResponse(
        items=[CheckResponse.model_validate(check) for check in checks],
        **_pagination(total, page, page_size),
    )


@router.get(
    "/{monitor_id}/incidents",
    response_model=PaginatedIncidentsResponse,
)
async def list_monitor_incidents(
    monitor_id: UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return incidents for an owned monitor, newest first."""
    monitor = _owned_monitor(db, monitor_id, current_user.id)
    query = db.query(Incident).filter(Incident.monitor_id == monitor_id)
    total = query.with_entities(func.count(Incident.id)).scalar() or 0
    incidents = (
        query.order_by(Incident.started_at.desc(), Incident.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PaginatedIncidentsResponse(
        items=[
            IncidentResponse(
                id=incident.id,
                monitor_id=incident.monitor_id,
                monitor_name=monitor.name,
                started_at=incident.started_at,
                resolved_at=incident.resolved_at,
                duration_minutes=incident.duration_minutes,
                status=incident.status,
                created_at=incident.created_at,
            )
            for incident in incidents
        ],
        **_pagination(total, page, page_size),
    )


@router.get("/{monitor_id}/uptime", response_model=UptimeResponse)
async def get_monitor_uptime(
    monitor_id: UUID,
    hours: int = Query(default=24, ge=1, le=8760),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Calculate successful-check uptime for a bounded time window."""
    _owned_monitor(db, monitor_id, current_user.id)
    to_time = datetime.now(timezone.utc)
    from_time = to_time - timedelta(hours=hours)
    total, successful = (
        db.query(
            func.count(Check.id),
            func.coalesce(
                func.sum(case((Check.status == 1, 1), else_=0)),
                0,
            ),
        )
        .filter(
            Check.monitor_id == monitor_id,
            Check.checked_at >= from_time,
        )
        .one()
    )
    total = int(total)
    successful = int(successful)
    return UptimeResponse(
        monitor_id=monitor_id,
        window_hours=hours,
        from_time=from_time,
        to_time=to_time,
        uptime_percentage=(
            round((successful / total) * 100, 3) if total else None
        ),
        total_checks=total,
        successful_checks=successful,
        failed_checks=total - successful,
    )


@router.get(
    "/{monitor_id}/response-time",
    response_model=ResponseTimeResponse,
)
async def get_monitor_response_time(
    monitor_id: UUID,
    hours: int = Query(default=24, ge=1, le=8760),
    max_points: int = Query(default=120, ge=10, le=1000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return response-time aggregates and a bounded recent chart series."""
    _owned_monitor(db, monitor_id, current_user.id)
    from_time = datetime.now(timezone.utc) - timedelta(hours=hours)
    query = (
        db.query(Check)
        .filter(
            Check.monitor_id == monitor_id,
            Check.checked_at >= from_time,
            Check.response_time.is_not(None),
        )
    )
    total, average, minimum, maximum = query.with_entities(
        func.count(Check.id),
        func.avg(Check.response_time),
        func.min(Check.response_time),
        func.max(Check.response_time),
    ).one()
    total = int(total)
    p95 = None
    if total:
        p95_index = max(0, math.ceil(total * 0.95) - 1)
        p95 = (
            query.with_entities(Check.response_time)
            .order_by(Check.response_time.asc())
            .offset(p95_index)
            .limit(1)
            .scalar()
        )
    sampled_rows = list(
        reversed(
            query.order_by(Check.checked_at.desc(), Check.id.desc())
            .limit(max_points)
            .all()
        )
    )

    return ResponseTimeResponse(
        monitor_id=monitor_id,
        window_hours=hours,
        average_ms=round(float(average), 2) if average is not None else None,
        minimum_ms=int(minimum) if minimum is not None else None,
        maximum_ms=int(maximum) if maximum is not None else None,
        p95_ms=int(p95) if p95 is not None else None,
        points=[
            ResponseTimePoint(
                checked_at=check.checked_at,
                response_time=int(check.response_time),
                status=check.status,
                status_code=check.status_code,
            )
            for check in sampled_rows
        ],
    )


@router.get("/{monitor_id}/status", response_model=LatestStatusResponse)
async def get_monitor_latest_status(
    monitor_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return monitor state and its most recently recorded check."""
    monitor = _owned_monitor(db, monitor_id, current_user.id)
    latest_check = (
        db.query(Check)
        .filter(Check.monitor_id == monitor_id)
        .order_by(Check.checked_at.desc(), Check.id.desc())
        .first()
    )
    return LatestStatusResponse(
        monitor_id=monitor_id,
        monitor_status=monitor.status,
        latest_check=(
            CheckResponse.model_validate(latest_check)
            if latest_check
            else None
        ),
    )


@router.get("/{monitor_id}", response_model=MonitorResponse)
async def get_monitor(
    monitor_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get single monitor"""
    monitor = db.query(Monitor).filter(
        Monitor.id == monitor_id,
        Monitor.user_id == current_user.id
    ).first()
    
    if not monitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Monitor not found"
        )
    
    return MonitorResponse.model_validate(monitor)

@router.put("/{monitor_id}", response_model=MonitorResponse)
async def update_monitor(
    monitor_id: UUID,
    monitor_data: MonitorCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update monitor"""
    monitor = db.query(Monitor).filter(
        Monitor.id == monitor_id,
        Monitor.user_id == current_user.id
    ).first()
    
    if not monitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Monitor not found"
        )
    
    monitor.name = monitor_data.name
    monitor.url = str(monitor_data.url)
    monitor.method = monitor_data.method
    monitor.headers = protect_updated_headers(
        monitor.headers,
        monitor_data.headers,
    )
    monitor.body = monitor_data.body
    monitor.expected_status = monitor_data.expected_status
    monitor.check_interval = monitor_data.check_interval
    monitor.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(monitor)
    return MonitorResponse.model_validate(monitor)

@router.delete("/{monitor_id}")
async def delete_monitor(
    monitor_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete monitor"""
    monitor = db.query(Monitor).filter(
        Monitor.id == monitor_id,
        Monitor.user_id == current_user.id
    ).first()
    
    if not monitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Monitor not found"
        )
    
    db.delete(monitor)
    db.commit()
    return {"message": "Monitor deleted"}

@router.post("/{monitor_id}/test", status_code=status.HTTP_202_ACCEPTED)
async def test_monitor(
    monitor_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Run manual check on monitor"""
    monitor = db.query(Monitor).filter(
        Monitor.id == monitor_id,
        Monitor.user_id == current_user.id
    ).first()
    
    if not monitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Monitor not found"
        )
    
    try:
        task = check_monitor.delay(str(monitor.id), True)
    except Exception as exc:
        logger.exception("Failed to queue manual check for monitor %s", monitor.id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Monitoring worker is unavailable",
        ) from exc

    return {"message": "Check queued", "task_id": task.id}

@router.post("/{monitor_id}/pause", response_model=MonitorResponse)
async def pause_monitor(
    monitor_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Pause monitoring"""
    monitor = db.query(Monitor).filter(
        Monitor.id == monitor_id,
        Monitor.user_id == current_user.id
    ).first()
    
    if not monitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Monitor not found"
        )
    
    monitor.status = "paused"
    monitor.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(monitor)
    return MonitorResponse.model_validate(monitor)


@router.post("/{monitor_id}/resume", response_model=MonitorResponse)
async def resume_monitor(
    monitor_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Resume automatic monitoring."""
    monitor = db.query(Monitor).filter(
        Monitor.id == monitor_id,
        Monitor.user_id == current_user.id
    ).first()

    if not monitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Monitor not found"
        )

    monitor.status = "active"
    monitor.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(monitor)
    return MonitorResponse.model_validate(monitor)
