import asyncio
import os
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi import HTTPException
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

from app.models import Base, Monitor, User
from app.routes.monitors import (
    create_monitor,
    pause_monitor,
    resume_monitor,
    test_monitor as test_monitor_route,
)
from app.schemas import MonitorCreate


class MonitorActionRouteTests(unittest.TestCase):
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
                    status="active",
                )
            )

    def tearDown(self):
        self.engine.dispose()

    def get_user(self, db):
        return db.get(User, self.user_id)

    @patch("app.routes.monitors.check_monitor.delay")
    def test_manual_check_is_queued_with_paused_override(self, delay):
        delay.return_value = MagicMock(id="task-123")

        with self.TestSession() as db:
            result = asyncio.run(
                test_monitor_route(
                    monitor_id=self.monitor_id,
                    current_user=self.get_user(db),
                    db=db,
                )
            )

        delay.assert_called_once_with(str(self.monitor_id), True)
        self.assertEqual(result["message"], "Check queued")
        self.assertEqual(result["task_id"], "task-123")

    @patch(
        "app.routes.monitors.check_monitor.delay",
        side_effect=ConnectionError("redis unavailable"),
    )
    def test_manual_check_reports_worker_unavailability(self, _delay):
        with self.TestSession() as db:
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(
                    test_monitor_route(
                        monitor_id=self.monitor_id,
                        current_user=self.get_user(db),
                        db=db,
                    )
                )

        self.assertEqual(raised.exception.status_code, 503)

    def test_pause_and_resume_preserve_the_monitor_contract(self):
        with self.TestSession() as db:
            user = self.get_user(db)
            paused = asyncio.run(
                pause_monitor(
                    monitor_id=self.monitor_id,
                    current_user=user,
                    db=db,
                )
            )
            resumed = asyncio.run(
                resume_monitor(
                    monitor_id=self.monitor_id,
                    current_user=user,
                    db=db,
                )
            )

        self.assertEqual(paused.status, "paused")
        self.assertEqual(resumed.status, "active")

    def test_sensitive_headers_are_encrypted_and_response_is_redacted(self):
        with self.TestSession() as db:
            created = asyncio.run(
                create_monitor(
                    monitor_data=MonitorCreate(
                        name="Secured API",
                        url="https://example.com/private",
                        headers={
                            "Authorization": "Bearer top-secret",
                            "Accept": "application/json",
                        },
                    ),
                    current_user=self.get_user(db),
                    db=db,
                )
            )
            stored = db.get(Monitor, created.id)

        self.assertNotIn("top-secret", stored.headers["Authorization"])
        self.assertEqual(
            created.headers["Authorization"],
            "[REDACTED]",
        )
        self.assertEqual(
            created.headers["Accept"],
            "application/json",
        )


if __name__ == "__main__":
    unittest.main()
