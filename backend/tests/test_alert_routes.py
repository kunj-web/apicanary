import asyncio
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("SMTP_HOST", "localhost")
os.environ.setdefault("SMTP_PORT", "1025")
os.environ.setdefault("SMTP_USER", "test")
os.environ.setdefault("SMTP_PASSWORD", "test")
os.environ.setdefault("ALERT_FROM_EMAIL", "alerts@example.com")

from app.models import Base, Check, Incident, Monitor, User
from app.routes.alerts import create_alert
from app.schemas import AlertCreate


class AlertThresholdRouteTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.TestSession = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
        )
        self.user_id = uuid4()
        self.monitor_id = uuid4()
        self.started_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

        with self.TestSession.begin() as db:
            db.add(
                User(
                    id=self.user_id,
                    email="owner@example.com",
                    password_hash="hash",
                    full_name="Owner",
                )
            )
            db.add(
                Monitor(
                    id=self.monitor_id,
                    user_id=self.user_id,
                    name="API",
                    url="https://example.com/health",
                    method="GET",
                    expected_status=200,
                    check_interval=5,
                    status="down",
                )
            )
            db.add(
                Incident(
                    monitor_id=self.monitor_id,
                    started_at=self.started_at,
                    status="ongoing",
                )
            )

    def tearDown(self):
        self.engine.dispose()

    def add_failures(self, count):
        with self.TestSession.begin() as db:
            for index in range(count):
                db.add(
                    Check(
                        monitor_id=self.monitor_id,
                        status=0,
                        response_time=20,
                        status_code=503,
                        checked_at=self.started_at
                        + timedelta(minutes=index),
                    )
                )

    def create_threshold_alert(self, threshold):
        with self.TestSession() as db:
            return asyncio.run(
                create_alert(
                    alert_data=AlertCreate(
                        monitor_id=self.monitor_id,
                        alert_type="email",
                        recipient="owner@example.com",
                        threshold_failures=threshold,
                    ),
                    current_user=db.get(User, self.user_id),
                    db=db,
                )
            )

    @patch("app.routes.alerts.send_email_alert")
    def test_new_alert_waits_until_its_threshold(self, send_email):
        self.add_failures(1)

        alert = self.create_threshold_alert(threshold=2)

        self.assertEqual(alert.threshold_failures, 2)
        send_email.assert_not_called()

    @patch("app.routes.alerts.send_email_alert")
    def test_new_alert_sends_when_incident_already_crossed_threshold(
        self,
        send_email,
    ):
        self.add_failures(2)

        self.create_threshold_alert(threshold=2)

        send_email.assert_called_once()


if __name__ == "__main__":
    unittest.main()
