import requests
import time
from datetime import datetime, timezone
from uuid import uuid4
from app.tasks.celery import celery_app
from app.core.database import SessionLocal
from app.models import Monitor, Check, Incident, Alert
from app.services.alert_service import send_email_alert, send_recovery_email

@celery_app.task
def check_monitor(monitor_id: str):
    """Check a single monitor and record result"""
    db = SessionLocal()
    try:
        monitor = db.query(Monitor).filter(Monitor.id == monitor_id).first()
        if not monitor or monitor.status not in ("active", "down"):
            return

        start_time = time.time()
        status = 0
        status_code = None
        response_body = None
        error_message = None

        try:
            response = requests.request(
                method=monitor.method,
                url=monitor.url,
                headers=monitor.headers or {},
                json=monitor.body,
                timeout=30,
            )
            response_time = int((time.time() - start_time) * 1000)
            status_code = response.status_code
            response_body = response.text[:1000]

            if status_code == monitor.expected_status:
                status = 1
            else:
                status = 0
                error_message = f"Expected {monitor.expected_status}, got {status_code}"

        except requests.exceptions.Timeout:
            response_time = 30000
            status = -1
            error_message = "Request timed out"

        except requests.exceptions.ConnectionError:
            response_time = 0
            status = -1
            error_message = "Connection failed"

        # Save check result
        check = Check(
            id=uuid4(),
            monitor_id=monitor.id,
            status=status,
            response_time=response_time,
            status_code=status_code,
            response_body=response_body,
            error_message=error_message,
            checked_at=datetime.now(timezone.utc),
        )
        db.add(check)
        db.commit()

        # Handle incidents
        if status != 1:
            existing_incident = db.query(Incident).filter(
                Incident.monitor_id == monitor.id,
                Incident.status == "ongoing"
            ).first()

            if not existing_incident:
                incident = Incident(
                    id=uuid4(),
                    monitor_id=monitor.id,
                    started_at=datetime.now(timezone.utc),
                    status="ongoing",
                )
                db.add(incident)
                db.commit()

                # Update monitor status to down
                monitor.status = "down"
                db.commit()

                # Send alert emails — only on new incident
                alerts = db.query(Alert).filter(
                    Alert.monitor_id == monitor.id,
                    Alert.is_active,
                    Alert.alert_type == "email"
                ).all()

                for alert in alerts:
                    send_email_alert(
                        recipient=alert.recipient,
                        monitor_name=monitor.name,
                        monitor_url=monitor.url,
                        error_message=error_message or "Unknown error",
                    )

        else:
            ongoing = db.query(Incident).filter(
                Incident.monitor_id == monitor.id,
                Incident.status == "ongoing"
            ).first()

            if ongoing:
                ongoing.resolved_at = datetime.now(timezone.utc)
                ongoing.status = "resolved"
                duration = datetime.now(timezone.utc) - ongoing.started_at
                ongoing.duration_minutes = int(duration.total_seconds() / 60)
                db.commit()

                # Update monitor status back to active
                monitor.status = "active"
                db.commit()

                # Send recovery emails — only when incident resolves
                alerts = db.query(Alert).filter(
                    Alert.monitor_id == monitor.id,
                    Alert.is_active,
                    Alert.alert_type == "email"
                ).all()

                for alert in alerts:
                    send_recovery_email(
                        recipient=alert.recipient,
                        monitor_name=monitor.name,
                        monitor_url=monitor.url,
                        duration_minutes=ongoing.duration_minutes or 0,
                    )

    finally:
        db.close()


@celery_app.task
def schedule_all_monitors():
    """Schedule checks for all active monitors"""
    db = SessionLocal()
    try:
        monitors = db.query(Monitor).filter(Monitor.status.in_(["active", "down"])).all()
        for monitor in monitors:
            check_monitor.delay(str(monitor.id))
    finally:
        db.close()