from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from app.schemas import MonitorCreate, MonitorResponse
from app.models import User, Monitor
from app.core.dependencies import get_db, get_current_user
from uuid import uuid4
from datetime import datetime, timezone

router = APIRouter(prefix="/api/monitors", tags=["monitors"])

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
        headers=monitor_data.headers,
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

@router.get("/{monitor_id}", response_model=MonitorResponse)
async def get_monitor(
    monitor_id: str,
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
    monitor_id: str,
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
    monitor.headers = monitor_data.headers
    monitor.body = monitor_data.body
    monitor.expected_status = monitor_data.expected_status
    monitor.check_interval = monitor_data.check_interval
    monitor.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(monitor)
    return MonitorResponse.model_validate(monitor)

@router.delete("/{monitor_id}")
async def delete_monitor(
    monitor_id: str,
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

@router.post("/{monitor_id}/test")
async def test_monitor(
    monitor_id: str,
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
    
    # TODO: Implement actual check logic
    return {"message": "Check initiated"}

@router.post("/{monitor_id}/pause")
async def pause_monitor(
    monitor_id: str,
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