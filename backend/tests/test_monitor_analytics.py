import asyncio
import os
import unittest
from datetime import datetime, timedelta, timezone
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

from app.models import Base, Check, Incident, Monitor, User
from app.routes.incidents import get_incident, list_incidents
from app.routes.monitors import (
    get_monitor_latest_status,
    get_monitor_response_time,
    get_monitor_uptime,
    list_monitor_checks,
    list_monitor_incidents,
)


class MonitorAnalyticsRouteTests(unittest.TestCase):
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
        self.other_user_id = uuid4()
        self.monitor_id = uuid4()
        self.other_monitor_id = uuid4()
        self.now = datetime.now(timezone.utc)

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
                        name="Primary API",
                        url="https://example.com/health",
                        method="GET",
                        expected_status=200,
                        check_interval=5,
                        status="down",
                    ),
                    Monitor(
                        id=self.other_monitor_id,
                        user_id=self.other_user_id,
                        name="Private API",
                        url="https://other.example.com/health",
                        method="GET",
                        expected_status=200,
                        check_interval=5,
                        status="active",
                    ),
                ]
            )

        with self.TestSession.begin() as db:
            for index, check_status in enumerate([1, 1, 0, -1, 1]):
                db.add(
                    Check(
                        monitor_id=self.monitor_id,
                        status=check_status,
                        response_time=(index + 1) * 10,
                        status_code=200 if check_status == 1 else 503,
                        error_message=(
                            None if check_status == 1 else "Unavailable"
                        ),
                        checked_at=self.now
                        - timedelta(minutes=5 - index),
                    )
                )
            db.add(
                Check(
                    monitor_id=self.other_monitor_id,
                    status=1,
                    response_time=999,
                    status_code=200,
                    checked_at=self.now,
                )
            )
            db.add_all(
                [
                    Incident(
                        monitor_id=self.monitor_id,
                        started_at=self.now - timedelta(hours=2),
                        resolved_at=self.now - timedelta(hours=1),
                        duration_minutes=60,
                        status="resolved",
                    ),
                    Incident(
                        monitor_id=self.monitor_id,
                        started_at=self.now - timedelta(minutes=10),
                        status="ongoing",
                    ),
                    Incident(
                        monitor_id=self.other_monitor_id,
                        started_at=self.now - timedelta(minutes=5),
                        status="ongoing",
                    ),
                ]
            )

    def tearDown(self):
        self.engine.dispose()

    def get_user(self, db):
        return db.get(User, self.user_id)

    def test_checks_are_paginated_newest_first(self):
        with self.TestSession() as db:
            result = asyncio.run(
                list_monitor_checks(
                    monitor_id=self.monitor_id,
                    page=1,
                    page_size=2,
                    current_user=self.get_user(db),
                    db=db,
                )
            )

        self.assertEqual(result.total, 5)
        self.assertEqual(result.total_pages, 3)
        self.assertEqual(len(result.items), 2)
        self.assertEqual(result.items[0].response_time, 50)
        self.assertEqual(result.items[1].response_time, 40)

    def test_uptime_and_response_time_exclude_other_users_data(self):
        with self.TestSession() as db:
            user = self.get_user(db)
            uptime = asyncio.run(
                get_monitor_uptime(
                    monitor_id=self.monitor_id,
                    hours=24,
                    current_user=user,
                    db=db,
                )
            )
            response_time = asyncio.run(
                get_monitor_response_time(
                    monitor_id=self.monitor_id,
                    hours=24,
                    max_points=10,
                    current_user=user,
                    db=db,
                )
            )

        self.assertEqual(uptime.total_checks, 5)
        self.assertEqual(uptime.successful_checks, 3)
        self.assertEqual(uptime.failed_checks, 2)
        self.assertEqual(uptime.uptime_percentage, 60.0)
        self.assertEqual(response_time.average_ms, 30.0)
        self.assertEqual(response_time.minimum_ms, 10)
        self.assertEqual(response_time.maximum_ms, 50)
        self.assertEqual(response_time.p95_ms, 50)
        self.assertEqual(len(response_time.points), 5)

    def test_latest_status_returns_the_latest_check(self):
        with self.TestSession() as db:
            result = asyncio.run(
                get_monitor_latest_status(
                    monitor_id=self.monitor_id,
                    current_user=self.get_user(db),
                    db=db,
                )
            )

        self.assertEqual(result.monitor_status, "down")
        self.assertIsNotNone(result.latest_check)
        self.assertEqual(result.latest_check.response_time, 50)

    def test_monitor_and_global_incidents_are_owner_scoped(self):
        with self.TestSession() as db:
            user = self.get_user(db)
            monitor_result = asyncio.run(
                list_monitor_incidents(
                    monitor_id=self.monitor_id,
                    page=1,
                    page_size=20,
                    current_user=user,
                    db=db,
                )
            )
            global_result = asyncio.run(
                list_incidents(
                    page=1,
                    page_size=20,
                    incident_status=None,
                    current_user=user,
                    db=db,
                )
            )

        self.assertEqual(monitor_result.total, 2)
        self.assertEqual(global_result.total, 2)
        self.assertEqual(global_result.items[0].status, "ongoing")
        self.assertTrue(
            all(
                incident.monitor_id == self.monitor_id
                for incident in global_result.items
            )
        )

    def test_incident_detail_does_not_leak_another_users_incident(self):
        with self.TestSession() as db:
            other_incident = (
                db.query(Incident)
                .filter(Incident.monitor_id == self.other_monitor_id)
                .first()
            )
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(
                    get_incident(
                        incident_id=other_incident.id,
                        current_user=self.get_user(db),
                        db=db,
                    )
                )

        self.assertEqual(raised.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
