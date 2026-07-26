from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from app.schemas import AlertCreate, AlertResponse
from app.models import User, Alert, Monitor, Incident, Check
from app.core.dependencies import get_db, get_current_user
from app.services.alert_service import send_email_alert
from uuid import UUID, uuid4

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

@router.post("", response_model=AlertResponse)
async def create_alert(
    alert_data: AlertCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create new alert"""
    monitor = db.query(Monitor).filter(
        Monitor.id == alert_data.monitor_id,
        Monitor.user_id == current_user.id
    ).first()

    if not monitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Monitor not found"
        )

    alert = Alert(
        id=uuid4(),
        user_id=current_user.id,
        monitor_id=alert_data.monitor_id,
        alert_type=alert_data.alert_type,
        recipient=alert_data.recipient,
        threshold_failures=alert_data.threshold_failures,
        is_active=True,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)

    # If monitor is already down, send alert immediately
    if monitor.status == "down":
        ongoing = db.query(Incident).filter(
            Incident.monitor_id == monitor.id,
            Incident.status == "ongoing"
        ).first()

        failure_count = 0
        if ongoing:
            failure_count = db.query(Check).filter(
                Check.monitor_id == monitor.id,
                Check.checked_at >= ongoing.started_at,
                Check.status != 1,
            ).count()

        if (
            ongoing
            and alert_data.alert_type == "email"
            and failure_count >= alert_data.threshold_failures
        ):
            send_email_alert(
                recipient=alert_data.recipient,
                monitor_name=monitor.name,
                monitor_url=monitor.url,
                error_message="Monitor was already down when alert was created",
            )

    return AlertResponse.model_validate(alert)


@router.get("", response_model=list[AlertResponse])
async def list_alerts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all alerts for current user"""
    alerts = db.query(Alert).filter(Alert.user_id == current_user.id).all()
    return [AlertResponse.model_validate(a) for a in alerts]


@router.delete("/{alert_id}")
async def delete_alert(
    alert_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete alert"""
    alert = db.query(Alert).filter(
        Alert.id == alert_id,
        Alert.user_id == current_user.id
    ).first()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found"
        )

    db.delete(alert)
    db.commit()
    return {"message": "Alert deleted"}
