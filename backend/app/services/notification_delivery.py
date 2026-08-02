from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Alert, Monitor, NotificationDelivery


def create_notification_delivery(
    db: Session,
    *,
    alert: Alert,
    monitor: Monitor,
    event_type: str,
    idempotency_key: str,
    error_message: Optional[str] = None,
    duration_minutes: Optional[int] = None,
) -> tuple[NotificationDelivery, bool]:
    """Create one durable delivery for an event, or return its existing row."""
    existing = db.scalar(
        select(NotificationDelivery).where(
            NotificationDelivery.idempotency_key == idempotency_key
        )
    )
    if existing:
        return existing, False

    payload = {
        "monitor_name": monitor.name,
        "monitor_url": monitor.url,
    }
    if error_message is not None:
        payload["error_message"] = error_message
    if duration_minutes is not None:
        payload["duration_minutes"] = duration_minutes

    delivery = NotificationDelivery(
        user_id=alert.user_id,
        alert_id=alert.id,
        monitor_id=monitor.id,
        event_type=event_type,
        channel=alert.alert_type,
        recipient=alert.recipient,
        status="pending",
        idempotency_key=idempotency_key,
        payload=payload,
    )
    db.add(delivery)
    db.flush()
    return delivery, True

