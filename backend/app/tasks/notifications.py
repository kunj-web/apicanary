import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, NoReturn, Optional
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import NotificationDelivery
from app.services.alert_service import (
    NotificationDeliveryError,
    send_email_alert,
    send_recovery_email,
    send_test_email,
)
from app.tasks.celery import celery_app

logger = logging.getLogger(__name__)

DELIVERY_BATCH_SIZE = 100
MAX_ERROR_LENGTH = 1000


class PermanentNotificationError(RuntimeError):
    """A delivery problem that retrying cannot correct."""


@dataclass(frozen=True)
class DeliverySnapshot:
    id: UUID
    event_type: str
    channel: str
    recipient: str
    payload: dict[str, Any]


def _as_uuid(value: str | UUID) -> Optional[UUID]:
    if isinstance(value, UUID):
        return value
    try:
        return UUID(value)
    except (TypeError, ValueError, AttributeError):
        return None


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _retry_delay(retry_number: int) -> int:
    base = max(settings.NOTIFICATION_RETRY_BASE_SECONDS, 1)
    maximum = max(settings.NOTIFICATION_RETRY_MAX_SECONDS, base)
    exponential = min(base * (2 ** max(retry_number, 0)), maximum)
    jitter_limit = min(base, max(maximum - exponential, 0))
    jitter = secrets.randbelow(jitter_limit + 1) if jitter_limit else 0
    return exponential + jitter


def enqueue_notification_delivery(delivery_id: str | UUID) -> bool:
    """Queue a durable delivery and leave it pending if Redis is unavailable."""
    delivery_uuid = _as_uuid(delivery_id)
    if delivery_uuid is None:
        return False

    now = datetime.now(timezone.utc)
    with SessionLocal.begin() as db:
        delivery = db.execute(
            select(NotificationDelivery)
            .where(NotificationDelivery.id == delivery_uuid)
            .with_for_update()
        ).scalar_one_or_none()
        if not delivery or delivery.status in {"sent", "failed", "sending"}:
            return False
        if (
            delivery.status == "retrying"
            and delivery.next_attempt_at
            and _as_utc(delivery.next_attempt_at) > now
        ):
            return False
        delivery.status = "queued"
        delivery.queued_at = now

    try:
        send_notification_delivery.apply_async(
            args=[str(delivery_uuid)],
            retry=False,
        )
        return True
    except Exception:
        logger.exception(
            "Could not queue notification delivery %s",
            delivery_uuid,
        )
        with SessionLocal.begin() as db:
            delivery = db.execute(
                select(NotificationDelivery)
                .where(NotificationDelivery.id == delivery_uuid)
                .with_for_update()
            ).scalar_one_or_none()
            if delivery and delivery.status == "queued":
                delivery.status = "pending"
                delivery.queued_at = None
        return False


def _claim_delivery(delivery_id: str) -> Optional[DeliverySnapshot]:
    delivery_uuid = _as_uuid(delivery_id)
    if delivery_uuid is None:
        return None

    now = datetime.now(timezone.utc)
    with SessionLocal.begin() as db:
        delivery = db.execute(
            select(NotificationDelivery)
            .where(NotificationDelivery.id == delivery_uuid)
            .with_for_update()
        ).scalar_one_or_none()
        if not delivery or delivery.status in {"sent", "failed", "sending"}:
            return None
        if (
            delivery.status == "retrying"
            and delivery.next_attempt_at
            and _as_utc(delivery.next_attempt_at) > now
        ):
            return None

        delivery.status = "sending"
        delivery.attempt_count += 1
        delivery.next_attempt_at = None
        return DeliverySnapshot(
            id=delivery.id,
            event_type=delivery.event_type,
            channel=delivery.channel,
            recipient=delivery.recipient,
            payload=dict(delivery.payload),
        )


def _mark_sent(delivery_id: UUID) -> None:
    with SessionLocal.begin() as db:
        delivery = db.execute(
            select(NotificationDelivery)
            .where(NotificationDelivery.id == delivery_id)
            .with_for_update()
        ).scalar_one_or_none()
        if delivery:
            delivery.status = "sent"
            delivery.sent_at = datetime.now(timezone.utc)
            delivery.next_attempt_at = None
            delivery.last_error = None


def _mark_failed_attempt(
    delivery_id: UUID,
    error: Exception,
    *,
    final: bool,
    retry_at: Optional[datetime] = None,
) -> None:
    with SessionLocal.begin() as db:
        delivery = db.execute(
            select(NotificationDelivery)
            .where(NotificationDelivery.id == delivery_id)
            .with_for_update()
        ).scalar_one_or_none()
        if delivery:
            delivery.status = "failed" if final else "retrying"
            delivery.last_error = str(error)[:MAX_ERROR_LENGTH]
            delivery.next_attempt_at = None if final else retry_at


def _send(snapshot: DeliverySnapshot) -> None:
    if snapshot.channel != "email":
        raise PermanentNotificationError(
            f"Unsupported notification channel: {snapshot.channel}"
        )

    try:
        monitor_name = str(snapshot.payload["monitor_name"])
        monitor_url = str(snapshot.payload["monitor_url"])
    except KeyError as exc:
        raise PermanentNotificationError(
            f"Missing notification field: {exc.args[0]}"
        ) from exc

    if snapshot.event_type == "failure":
        send_email_alert(
            recipient=snapshot.recipient,
            monitor_name=monitor_name,
            monitor_url=monitor_url,
            error_message=str(
                snapshot.payload.get(
                    "error_message",
                    "APICanary test notification",
                )
            ),
        )
        return

    if snapshot.event_type == "test":
        send_test_email(
            recipient=snapshot.recipient,
            monitor_name=monitor_name,
            monitor_url=monitor_url,
        )
        return

    if snapshot.event_type == "recovery":
        try:
            duration_minutes = int(
                snapshot.payload.get("duration_minutes", 0)
            )
        except (TypeError, ValueError) as exc:
            raise PermanentNotificationError(
                "Invalid recovery duration"
            ) from exc
        send_recovery_email(
            recipient=snapshot.recipient,
            monitor_name=monitor_name,
            monitor_url=monitor_url,
            duration_minutes=duration_minutes,
        )
        return

    raise PermanentNotificationError(
        f"Unsupported notification event: {snapshot.event_type}"
    )


def _schedule_retry(self, snapshot: DeliverySnapshot, error: Exception) -> NoReturn:
    max_retries = max(settings.NOTIFICATION_MAX_RETRIES, 0)
    if self.request.retries >= max_retries:
        _mark_failed_attempt(snapshot.id, error, final=True)
        logger.error(
            "Notification delivery %s failed after %s attempts",
            snapshot.id,
            max_retries + 1,
        )
        raise error

    countdown = _retry_delay(self.request.retries)
    retry_at = datetime.now(timezone.utc) + timedelta(seconds=countdown)
    _mark_failed_attempt(
        snapshot.id,
        error,
        final=False,
        retry_at=retry_at,
    )
    raise self.retry(
        exc=error,
        countdown=countdown,
        max_retries=max_retries,
    )


@celery_app.task(
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
    autoretry_for=(SQLAlchemyError,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 5},
)
def send_notification_delivery(self, delivery_id: str):
    """Deliver one notification and persist every attempt outcome."""
    snapshot = _claim_delivery(delivery_id)
    if snapshot is None:
        return {"state": "skipped", "delivery_id": delivery_id}

    try:
        _send(snapshot)
    except PermanentNotificationError as exc:
        _mark_failed_attempt(snapshot.id, exc, final=True)
        logger.error("Notification delivery %s permanently failed", snapshot.id)
        return {"state": "failed", "delivery_id": delivery_id}
    except NotificationDeliveryError as exc:
        _schedule_retry(self, snapshot, exc)
    except Exception as exc:
        retryable = NotificationDeliveryError(
            f"Unexpected delivery failure: {exc.__class__.__name__}"
        )
        _schedule_retry(self, snapshot, retryable)

    _mark_sent(snapshot.id)
    return {"state": "sent", "delivery_id": delivery_id}


@celery_app.task
def dispatch_pending_deliveries():
    """Recover pending or abandoned delivery records into the worker queue."""
    now = datetime.now(timezone.utc)
    stale_before = now - timedelta(
        seconds=max(settings.NOTIFICATION_DELIVERY_LEASE_SECONDS, 60)
    )

    with SessionLocal.begin() as db:
        deliveries = db.execute(
            select(NotificationDelivery)
            .where(
                or_(
                    NotificationDelivery.status == "pending",
                    (
                        (NotificationDelivery.status == "retrying")
                        & or_(
                            NotificationDelivery.next_attempt_at.is_(None),
                            NotificationDelivery.next_attempt_at <= now,
                        )
                    ),
                    (
                        (NotificationDelivery.status == "queued")
                        & or_(
                            NotificationDelivery.queued_at.is_(None),
                            NotificationDelivery.queued_at <= stale_before,
                        )
                    ),
                    (
                        (NotificationDelivery.status == "sending")
                        & (NotificationDelivery.updated_at <= stale_before)
                    ),
                )
            )
            .order_by(NotificationDelivery.created_at.asc())
            .limit(DELIVERY_BATCH_SIZE)
            .with_for_update()
        ).scalars().all()

        delivery_ids = []
        for delivery in deliveries:
            delivery.status = "pending"
            delivery.queued_at = None
            delivery_ids.append(delivery.id)

    queued = sum(
        enqueue_notification_delivery(delivery_id)
        for delivery_id in delivery_ids
    )
    return {"eligible": len(delivery_ids), "queued": queued}
