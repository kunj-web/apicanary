import asyncio
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

from fastapi import BackgroundTasks, HTTPException
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

from app.models import (
    Alert,
    Base,
    Check,
    Incident,
    Monitor,
    NotificationDelivery,
    User,
)
from app.routes.alerts import (
    create_alert,
    delete_alert,
    list_alerts,
    list_notification_deliveries,
    test_alert as send_test_alert,
)
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
        self.other_user_id = uuid4()
        self.other_monitor_id = uuid4()
        self.started_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

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
                        status="down",
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
            async def run_route():
                background_tasks = BackgroundTasks()
                response = await create_alert(
                    alert_data=AlertCreate(
                        monitor_id=self.monitor_id,
                        alert_type="email",
                        recipient="owner@example.com",
                        threshold_failures=threshold,
                    ),
                    background_tasks=background_tasks,
                    current_user=db.get(User, self.user_id),
                    db=db,
                )
                await background_tasks()
                return response

            return asyncio.run(run_route())

    @patch("app.routes.alerts._queue_deliveries")
    def test_new_alert_waits_until_its_threshold(self, queue_deliveries):
        self.add_failures(1)

        alert = self.create_threshold_alert(threshold=2)

        self.assertEqual(alert.threshold_failures, 2)
        queue_deliveries.assert_called_once_with([])
        with self.TestSession() as db:
            self.assertEqual(db.query(NotificationDelivery).count(), 0)

    @patch("app.routes.alerts._queue_deliveries")
    def test_new_alert_sends_when_incident_already_crossed_threshold(
        self,
        queue_deliveries,
    ):
        self.add_failures(2)

        self.create_threshold_alert(threshold=2)

        with self.TestSession() as db:
            delivery = db.query(NotificationDelivery).one()

        queue_deliveries.assert_called_once_with([delivery.id])
        self.assertEqual(delivery.event_type, "failure")
        self.assertEqual(delivery.status, "pending")
        self.assertEqual(delivery.payload["monitor_name"], "API")

    def test_alert_creation_cannot_target_another_users_monitor(self):
        with self.TestSession() as db:
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(
                    create_alert(
                        alert_data=AlertCreate(
                            monitor_id=self.other_monitor_id,
                            alert_type="email",
                            recipient="owner@example.com",
                        ),
                        background_tasks=BackgroundTasks(),
                        current_user=db.get(User, self.user_id),
                        db=db,
                    )
                )

        self.assertEqual(raised.exception.status_code, 404)

    def test_alert_listing_and_deletion_are_owner_scoped(self):
        own_alert_id = uuid4()
        other_alert_id = uuid4()
        with self.TestSession.begin() as db:
            db.add_all(
                [
                    Alert(
                        id=own_alert_id,
                        user_id=self.user_id,
                        monitor_id=self.monitor_id,
                        alert_type="email",
                        recipient="owner@example.com",
                        threshold_failures=1,
                        is_active=True,
                    ),
                    Alert(
                        id=other_alert_id,
                        user_id=self.other_user_id,
                        monitor_id=self.other_monitor_id,
                        alert_type="email",
                        recipient="other@example.com",
                        threshold_failures=1,
                        is_active=True,
                    ),
                ]
            )

        with self.TestSession() as db:
            user = db.get(User, self.user_id)
            listed = asyncio.run(list_alerts(current_user=user, db=db))
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(
                    delete_alert(
                        alert_id=other_alert_id,
                        current_user=user,
                        db=db,
                    )
                )
            deleted = asyncio.run(
                delete_alert(
                    alert_id=own_alert_id,
                    current_user=user,
                    db=db,
                )
            )

        self.assertEqual([alert.id for alert in listed], [own_alert_id])
        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(deleted["message"], "Alert deleted")

    @patch("app.routes.alerts.enqueue_notification_delivery", return_value=True)
    def test_alert_can_queue_a_test_delivery(self, enqueue):
        alert = self.create_threshold_alert(threshold=3)

        with self.TestSession() as db:
            async def run_route():
                background_tasks = BackgroundTasks()
                response = await send_test_alert(
                    alert_id=alert.id,
                    background_tasks=background_tasks,
                    current_user=db.get(User, self.user_id),
                    db=db,
                )
                await background_tasks()
                return response

            response = asyncio.run(run_route())

        with self.TestSession() as db:
            delivery = db.get(NotificationDelivery, response.delivery_id)

        self.assertEqual(response.status, "pending")
        self.assertEqual(delivery.event_type, "test")
        self.assertEqual(delivery.status, "pending")
        enqueue.assert_called_once_with(delivery.id)

    def test_test_alert_does_not_expose_another_users_rule(self):
        other_alert_id = uuid4()
        with self.TestSession.begin() as db:
            db.add(
                Alert(
                    id=other_alert_id,
                    user_id=self.other_user_id,
                    monitor_id=self.other_monitor_id,
                    alert_type="email",
                    recipient="other@example.com",
                    threshold_failures=1,
                    is_active=True,
                )
            )

        with self.TestSession() as db:
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(
                    send_test_alert(
                        alert_id=other_alert_id,
                        background_tasks=BackgroundTasks(),
                        current_user=db.get(User, self.user_id),
                        db=db,
                    )
                )

        self.assertEqual(raised.exception.status_code, 404)

    def test_delivery_history_is_paginated_and_owner_scoped(self):
        own_alert_id = uuid4()
        other_alert_id = uuid4()
        own_delivery_id = uuid4()
        with self.TestSession.begin() as db:
            db.add_all(
                [
                    Alert(
                        id=own_alert_id,
                        user_id=self.user_id,
                        monitor_id=self.monitor_id,
                        alert_type="email",
                        recipient="owner@example.com",
                        threshold_failures=1,
                        is_active=True,
                    ),
                    Alert(
                        id=other_alert_id,
                        user_id=self.other_user_id,
                        monitor_id=self.other_monitor_id,
                        alert_type="email",
                        recipient="other@example.com",
                        threshold_failures=1,
                        is_active=True,
                    ),
                ]
            )
            db.flush()
            db.add_all(
                [
                    NotificationDelivery(
                        id=own_delivery_id,
                        user_id=self.user_id,
                        alert_id=own_alert_id,
                        monitor_id=self.monitor_id,
                        event_type="test",
                        channel="email",
                        recipient="owner@example.com",
                        status="sent",
                        idempotency_key=f"test:{own_delivery_id}",
                        payload={"monitor_name": "API", "monitor_url": "url"},
                        attempt_count=1,
                        sent_at=datetime.now(timezone.utc),
                    ),
                    NotificationDelivery(
                        user_id=self.other_user_id,
                        alert_id=other_alert_id,
                        monitor_id=self.other_monitor_id,
                        event_type="failure",
                        channel="email",
                        recipient="other@example.com",
                        status="failed",
                        idempotency_key=f"other:{uuid4()}",
                        payload={
                            "monitor_name": "Other API",
                            "monitor_url": "url",
                        },
                    ),
                ]
            )

        with self.TestSession() as db:
            response = asyncio.run(
                list_notification_deliveries(
                    alert_id=None,
                    page=1,
                    page_size=10,
                    current_user=db.get(User, self.user_id),
                    db=db,
                )
            )

        self.assertEqual(response.total, 1)
        self.assertEqual(response.total_pages, 1)
        self.assertEqual([item.id for item in response.items], [own_delivery_id])


if __name__ == "__main__":
    unittest.main()
