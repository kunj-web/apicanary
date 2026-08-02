import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

import requests
from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.core.header_crypto import (
    HeaderDecryptionError,
    protect_headers,
    reveal_headers,
)
from app.models import Alert, Check, Incident, Monitor
from app.services.notification_delivery import create_notification_delivery
from app.services.monitor_security import (
    UnsafeMonitorTarget,
    validate_monitor_target,
)
from app.tasks.celery import celery_app
from app.tasks.notifications import enqueue_notification_delivery

logger = logging.getLogger(__name__)

MONITORED_STATUSES = ("active", "down")
MAX_RESPONSE_BODY_LENGTH = 1000
REQUEST_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class MonitorSnapshot:
    id: Any
    name: str
    url: str
    method: str
    headers: Optional[dict[str, str]]
    body: Optional[dict[str, Any]]
    expected_status: int
    status: str
    configuration_error: Optional[str] = None


@dataclass(frozen=True)
class CheckResult:
    status: int
    response_time: int
    status_code: Optional[int]
    response_body: Optional[str]
    error_message: Optional[str]
    checked_at: datetime


def is_monitor_due(
    last_checked_at: Optional[datetime],
    check_interval: int,
    now: Optional[datetime] = None,
) -> bool:
    """Return whether a monitor is due for its next scheduled check."""
    if last_checked_at is None:
        return True

    current_time = now or datetime.now(timezone.utc)
    if last_checked_at.tzinfo is None:
        last_checked_at = last_checked_at.replace(tzinfo=timezone.utc)

    return current_time >= last_checked_at + timedelta(minutes=check_interval)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _as_uuid(value: str | UUID) -> Optional[UUID]:
    if isinstance(value, UUID):
        return value
    try:
        return UUID(value)
    except (TypeError, ValueError, AttributeError):
        return None


def _load_monitor_snapshot(
    monitor_id: str,
    allow_paused: bool,
) -> Optional[MonitorSnapshot]:
    monitor_uuid = _as_uuid(monitor_id)
    if monitor_uuid is None:
        return None

    with SessionLocal() as db:
        monitor = db.query(Monitor).filter(Monitor.id == monitor_uuid).first()
        allowed_statuses = MONITORED_STATUSES + (("paused",) if allow_paused else ())

        if not monitor or monitor.status not in allowed_statuses:
            return None

        raw_headers = dict(monitor.headers) if monitor.headers else None
        configuration_error = None
        try:
            request_headers = reveal_headers(raw_headers)
        except HeaderDecryptionError:
            request_headers = None
            configuration_error = (
                "Stored monitor credentials could not be decrypted"
            )

        # Transparently protect legacy plaintext credentials on first use.
        protected_headers = protect_headers(raw_headers)
        if protected_headers != raw_headers:
            monitor.headers = protected_headers
            db.commit()

        return MonitorSnapshot(
            id=monitor.id,
            name=monitor.name,
            url=monitor.url,
            method=monitor.method,
            headers=request_headers,
            body=dict(monitor.body) if monitor.body else None,
            expected_status=monitor.expected_status,
            status=monitor.status,
            configuration_error=configuration_error,
        )


def _perform_http_check(monitor: MonitorSnapshot) -> CheckResult:
    """Execute a monitor request and convert every outcome into a check result."""
    started_at = time.monotonic()

    if monitor.configuration_error:
        return CheckResult(
            status=-1,
            response_time=0,
            status_code=None,
            response_body=None,
            error_message=monitor.configuration_error,
            checked_at=datetime.now(timezone.utc),
        )

    try:
        validate_monitor_target(monitor.url)
        with requests.Session() as session:
            session.trust_env = False
            with session.request(
                method=monitor.method,
                url=monitor.url,
                headers=monitor.headers or {},
                json=monitor.body,
                timeout=REQUEST_TIMEOUT_SECONDS,
                allow_redirects=False,
            ) as response:
                response_time = int((time.monotonic() - started_at) * 1000)
                status_code = response.status_code
                response_body = response.text[:MAX_RESPONSE_BODY_LENGTH]

        if status_code == monitor.expected_status:
            return CheckResult(
                status=1,
                response_time=response_time,
                status_code=status_code,
                response_body=response_body,
                error_message=None,
                checked_at=datetime.now(timezone.utc),
            )

        return CheckResult(
            status=0,
            response_time=response_time,
            status_code=status_code,
            response_body=response_body,
            error_message=(
                f"Expected {monitor.expected_status}, got {status_code}"
            ),
            checked_at=datetime.now(timezone.utc),
        )
    except UnsafeMonitorTarget as exc:
        error_message = f"Blocked unsafe target: {exc}"
    except requests.exceptions.Timeout:
        error_message = "Request timed out"
    except requests.exceptions.ConnectionError:
        error_message = "Connection failed"
    except requests.exceptions.RequestException as exc:
        error_message = f"Request failed: {exc.__class__.__name__}"
        logger.warning(
            "Monitor request failed for %s: %s",
            monitor.id,
            exc,
        )
    except Exception as exc:
        error_message = f"Unexpected check failure: {exc.__class__.__name__}"
        logger.exception("Unexpected monitor check failure for %s", monitor.id)

    return CheckResult(
        status=-1,
        response_time=int((time.monotonic() - started_at) * 1000),
        status_code=None,
        response_body=None,
        error_message=error_message,
        checked_at=datetime.now(timezone.utc),
    )


def _incident_failure_count(db, incident: Incident) -> int:
    return int(
        db.scalar(
            select(func.count(Check.id)).where(
                Check.monitor_id == incident.monitor_id,
                Check.checked_at >= incident.started_at,
                Check.status != 1,
            )
        )
        or 0
    )


def _persist_check_result(
    monitor_id: str,
    result: CheckResult,
    allow_paused: bool,
) -> tuple[str, list[str]]:
    """Persist a check and its incident transition in one transaction."""
    notifications: list[str] = []
    monitor_uuid = _as_uuid(monitor_id)
    if monitor_uuid is None:
        return "invalid", notifications

    with SessionLocal.begin() as db:
        monitor = db.execute(
            select(Monitor)
            .where(Monitor.id == monitor_uuid)
            .with_for_update()
        ).scalar_one_or_none()

        if not monitor:
            return "deleted", notifications

        is_paused_manual_check = allow_paused and monitor.status == "paused"
        if monitor.status not in MONITORED_STATUSES and not is_paused_manual_check:
            return "skipped", notifications

        db.add(
            Check(
                monitor_id=monitor.id,
                status=result.status,
                response_time=result.response_time,
                status_code=result.status_code,
                response_body=result.response_body,
                error_message=result.error_message,
                checked_at=result.checked_at,
            )
        )
        db.flush()

        # A manual check may inspect a paused monitor, but it must not resume it,
        # open incidents, or send notifications.
        if is_paused_manual_check:
            return "recorded", notifications

        ongoing = db.execute(
            select(Incident)
            .where(
                Incident.monitor_id == monitor.id,
                Incident.status == "ongoing",
            )
            .with_for_update()
        ).scalar_one_or_none()

        if result.status != 1:
            if not ongoing:
                ongoing = Incident(
                    monitor_id=monitor.id,
                    started_at=result.checked_at,
                    status="ongoing",
                )
                db.add(ongoing)
                db.flush()

            monitor.status = "down"
            failure_count = _incident_failure_count(db, ongoing)
            alerts = db.execute(
                select(Alert).where(
                    Alert.monitor_id == monitor.id,
                    Alert.is_active.is_(True),
                    Alert.alert_type == "email",
                )
            ).scalars()

            for alert in alerts:
                if failure_count == alert.threshold_failures:
                    delivery, created = create_notification_delivery(
                        db,
                        alert=alert,
                        monitor=monitor,
                        event_type="failure",
                        idempotency_key=(
                            f"alert:{alert.id}:incident:{ongoing.id}:failure"
                        ),
                        error_message=(
                            result.error_message or "Unknown error"
                        ),
                    )
                    if created:
                        notifications.append(str(delivery.id))
        elif ongoing:
            failure_count = _incident_failure_count(db, ongoing)
            resolved_at = result.checked_at
            ongoing.resolved_at = resolved_at
            ongoing.status = "resolved"
            ongoing.duration_minutes = int(
                (
                    _as_utc(resolved_at) - _as_utc(ongoing.started_at)
                ).total_seconds()
                / 60
            )
            monitor.status = "active"

            alerts = db.execute(
                select(Alert).where(
                    Alert.monitor_id == monitor.id,
                    Alert.is_active.is_(True),
                    Alert.alert_type == "email",
                )
            ).scalars()

            for alert in alerts:
                if failure_count >= alert.threshold_failures:
                    delivery, created = create_notification_delivery(
                        db,
                        alert=alert,
                        monitor=monitor,
                        event_type="recovery",
                        idempotency_key=(
                            f"alert:{alert.id}:incident:{ongoing.id}:recovery"
                        ),
                        duration_minutes=ongoing.duration_minutes or 0,
                    )
                    if created:
                        notifications.append(str(delivery.id))

    return "recorded", notifications


def _enqueue_notifications(notifications: list[str]) -> None:
    for delivery_id in notifications:
        enqueue_notification_delivery(delivery_id)


@celery_app.task
def check_monitor(monitor_id: str, allow_paused: bool = False):
    """Check one monitor and atomically record its health transition."""
    snapshot = _load_monitor_snapshot(monitor_id, allow_paused)
    if not snapshot:
        return {"state": "skipped", "monitor_id": monitor_id}

    result = _perform_http_check(snapshot)

    try:
        state, notifications = _persist_check_result(
            monitor_id,
            result,
            allow_paused,
        )
    except Exception:
        logger.exception("Failed to persist check for monitor %s", monitor_id)
        raise

    # Notification jobs are queued only after the database transaction commits.
    _enqueue_notifications(notifications)

    return {
        "state": state,
        "monitor_id": monitor_id,
        "status": result.status,
        "status_code": result.status_code,
        "response_time": result.response_time,
    }


@celery_app.task
def schedule_all_monitors():
    """Queue only monitors whose configured interval has elapsed."""
    now = datetime.now(timezone.utc)
    last_check = (
        select(
            Check.monitor_id,
            func.max(Check.checked_at).label("last_checked_at"),
        )
        .group_by(Check.monitor_id)
        .subquery()
    )

    with SessionLocal() as db:
        rows = db.execute(
            select(
                Monitor.id,
                Monitor.check_interval,
                last_check.c.last_checked_at,
            )
            .outerjoin(last_check, last_check.c.monitor_id == Monitor.id)
            .where(Monitor.status.in_(MONITORED_STATUSES))
        ).all()

    queued = 0
    for monitor_id, check_interval, last_checked_at in rows:
        if is_monitor_due(last_checked_at, check_interval, now):
            check_monitor.delay(str(monitor_id))
            queued += 1

    return {"queued": queued, "eligible": len(rows)}
