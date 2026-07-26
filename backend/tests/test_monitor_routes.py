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
    delete_monitor,
    get_monitor,
    list_monitors,
    pause_monitor,
    resume_monitor,
    test_monitor as test_monitor_route,
    update_monitor,
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
        self.other_user_id = uuid4()
        self.other_monitor_id = uuid4()

        with self.TestSession.begin() as db:
            db.add_all(
                [
                    User(
                        id=self.user_id,
                        email="owner@example.com",
                        password_hash="hash",
                        full_name="Owner",
                    ),
                    User(
                        id=self.other_user_id,
                        email="other@example.com",
                        password_hash="hash",
                        full_name="Other",
                    ),
                    Monitor(
                        id=self.monitor_id,
                        user_id=self.user_id,
                        name="API",
                        url="https://example.com/health",
                        method="GET",
                        expected_status=200,
                        check_interval=5,
                        status="active",
                    ),
                    Monitor(
                        id=self.other_monitor_id,
                        user_id=self.other_user_id,
                        name="Other API",
                        url="https://other.example.com/health",
                        method="GET",
                        expected_status=200,
                        check_interval=5,
                        status="active",
                    ),
                ]
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

    def test_monitor_crud_lifecycle_preserves_the_response_contract(self):
        with self.TestSession() as db:
            user = self.get_user(db)
            listed = asyncio.run(list_monitors(current_user=user, db=db))
            fetched = asyncio.run(
                get_monitor(
                    monitor_id=self.monitor_id,
                    current_user=user,
                    db=db,
                )
            )
            updated = asyncio.run(
                update_monitor(
                    monitor_id=self.monitor_id,
                    monitor_data=MonitorCreate(
                        name="Updated API",
                        url="https://example.com/readiness",
                        method="HEAD",
                        expected_status=204,
                        check_interval=10,
                    ),
                    current_user=user,
                    db=db,
                )
            )
            deleted = asyncio.run(
                delete_monitor(
                    monitor_id=self.monitor_id,
                    current_user=user,
                    db=db,
                )
            )

        self.assertEqual(len(listed), 1)
        self.assertEqual(fetched.id, self.monitor_id)
        self.assertEqual(updated.name, "Updated API")
        self.assertEqual(updated.method, "HEAD")
        self.assertEqual(updated.status, "active")
        self.assertEqual(deleted["message"], "Monitor deleted")
        with self.TestSession() as db:
            self.assertIsNone(db.get(Monitor, self.monitor_id))

    @patch("app.routes.monitors.check_monitor.delay")
    def test_cross_user_monitor_actions_are_hidden(self, delay):
        with self.TestSession() as db:
            user = self.get_user(db)
            actions = (
                lambda: get_monitor(
                    self.other_monitor_id,
                    current_user=user,
                    db=db,
                ),
                lambda: update_monitor(
                    self.other_monitor_id,
                    MonitorCreate(
                        name="Stolen",
                        url="https://example.com",
                    ),
                    current_user=user,
                    db=db,
                ),
                lambda: delete_monitor(
                    self.other_monitor_id,
                    current_user=user,
                    db=db,
                ),
                lambda: test_monitor_route(
                    self.other_monitor_id,
                    current_user=user,
                    db=db,
                ),
            )
            for action in actions:
                with self.assertRaises(HTTPException) as raised:
                    asyncio.run(action())
                self.assertEqual(raised.exception.status_code, 404)

        delay.assert_not_called()


if __name__ == "__main__":
    unittest.main()
