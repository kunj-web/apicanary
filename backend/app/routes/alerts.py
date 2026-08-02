from typing import Optional
from uuid import UUID, uuid4

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, get_current_user
from app.models import (
    Alert,
    Check,
    Incident,
    Monitor,
    NotificationDelivery,
    User,
)
from app.schemas import (
    AlertCreate,
    AlertResponse,
    NotificationDeliveryResponse,
    PaginatedNotificationDeliveriesResponse,
    TestAlertResponse,
)
from app.services.notification_delivery import create_notification_delivery
from app.tasks.notifications import enqueue_notification_delivery

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


def _queue_deliveries(delivery_ids: list[UUID]) -> None:
    for delivery_id in delivery_ids:
        enqueue_notification_delivery(delivery_id)


@router.post("", response_model=AlertResponse)
async def create_alert(
    alert_data: AlertCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new alert rule."""
    monitor = db.query(Monitor).filter(
        Monitor.id == alert_data.monitor_id,
        Monitor.user_id == current_user.id,
    ).first()

    if not monitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Monitor not found",
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
    db.flush()
    delivery_ids: list[UUID] = []

    # If the monitor is already down, persist the notification before commit.
    if monitor.status == "down":
        ongoing = db.query(Incident).filter(
            Incident.monitor_id == monitor.id,
            Incident.status == "ongoing",
        ).first()

        failure_count = 0
        if ongoing:
            failure_count = db.query(Check).filter(
                Check.monitor_id == monitor.id,
                Check.checked_at >= ongoing.started_at,
                Check.status != 1,
            ).count()

        if ongoing and failure_count >= alert_data.threshold_failures:
            delivery, created = create_notification_delivery(
                db,
                alert=alert,
                monitor=monitor,
                event_type="failure",
                idempotency_key=(
                    f"alert:{alert.id}:incident:{ongoing.id}:failure"
                ),
                error_message="Monitor was already down when alert was created",
            )
            if created:
                delivery_ids.append(delivery.id)

    db.commit()
    db.refresh(alert)
    background_tasks.add_task(_queue_deliveries, delivery_ids)

    return AlertResponse.model_validate(alert)


@router.get("", response_model=list[AlertResponse])
async def list_alerts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all alert rules for the current user."""
    alerts = db.query(Alert).filter(Alert.user_id == current_user.id).all()
    return [AlertResponse.model_validate(a) for a in alerts]


@router.get(
    "/deliveries",
    response_model=PaginatedNotificationDeliveriesResponse,
)
async def list_notification_deliveries(
    alert_id: Optional[UUID] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return owner-scoped notification delivery history."""
    query = db.query(NotificationDelivery).filter(
        NotificationDelivery.user_id == current_user.id
    )
    if alert_id is not None:
        query = query.filter(NotificationDelivery.alert_id == alert_id)

    total = query.count()
    deliveries = (
        query.order_by(NotificationDelivery.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PaginatedNotificationDeliveriesResponse(
        items=[
            NotificationDeliveryResponse.model_validate(delivery)
            for delivery in deliveries
        ],
        page=page,
        page_size=page_size,
        total=total,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.post(
    "/{alert_id}/test",
    response_model=TestAlertResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def test_alert(
    alert_id: UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Persist and queue a test notification for an owned alert rule."""
    alert = db.query(Alert).filter(
        Alert.id == alert_id,
        Alert.user_id == current_user.id,
    ).first()
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    monitor = db.query(Monitor).filter(
        Monitor.id == alert.monitor_id,
        Monitor.user_id == current_user.id,
    ).first()
    if not monitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Monitor not found",
        )

    delivery, _ = create_notification_delivery(
        db,
        alert=alert,
        monitor=monitor,
        event_type="test",
        idempotency_key=f"test:{uuid4()}",
        error_message="This is a test alert from APICanary",
    )
    db.commit()
    delivery_id = delivery.id
    background_tasks.add_task(enqueue_notification_delivery, delivery_id)

    return TestAlertResponse(
        delivery_id=delivery_id,
        status="pending",
        message="Test alert saved for delivery",
    )


@router.delete("/{alert_id}")
async def delete_alert(
    alert_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete an alert rule."""
    alert = db.query(Alert).filter(
        Alert.id == alert_id,
        Alert.user_id == current_user.id
    ).first()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    db.delete(alert)
    db.commit()
    return {"message": "Alert deleted"}
