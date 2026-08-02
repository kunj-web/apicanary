import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

from sqlalchemy import create_engine, select
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
from app.tasks import monitor_checks
from app.tasks.monitor_checks import (
    CheckResult,
    MonitorSnapshot,
    _perform_http_check,
    is_monitor_due,
)


class MonitorDueTests(unittest.TestCase):
    def test_new_monitor_is_due(self):
        now = datetime.now(timezone.utc)
        self.assertTrue(is_monitor_due(None, 5, now))

    def test_monitor_waits_for_its_interval(self):
        now = datetime.now(timezone.utc)
        self.assertFalse(
            is_monitor_due(now - timedelta(minutes=4), 5, now)
        )
        self.assertTrue(
            is_monitor_due(now - timedelta(minutes=5), 5, now)
        )

    def test_naive_database_timestamp_is_treated_as_utc(self):
        now = datetime.now(timezone.utc)
        naive_last_check = (now - timedelta(minutes=10)).replace(tzinfo=None)
        self.assertTrue(is_monitor_due(naive_last_check, 5, now))


class HttpCheckTests(unittest.TestCase):
    def setUp(self):
        self.monitor = MonitorSnapshot(
            id=uuid4(),
            name="Example",
            url="https://example.com/health",
            method="GET",
            headers=None,
            body=None,
            expected_status=200,
            status="active",
        )

    @patch("app.tasks.monitor_checks.validate_monitor_target")
    @patch("app.tasks.monitor_checks.requests.Session")
    def test_successful_response_is_recorded_as_up(
        self,
        session_factory,
        validate_target,
    ):
        response = MagicMock()
        response.status_code = 200
        response.text = "ok"
        session = session_factory.return_value.__enter__.return_value
        session.request.return_value.__enter__.return_value = response

        result = _perform_http_check(self.monitor)

        validate_target.assert_called_once_with(self.monitor.url)
        self.assertFalse(session.trust_env)
        self.assertFalse(session.request.call_args.kwargs["allow_redirects"])
        self.assertEqual(result.status, 1)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.response_body, "ok")
        self.assertIsNone(result.error_message)

    @patch("app.tasks.monitor_checks.validate_monitor_target")
    @patch("app.tasks.monitor_checks.requests.Session")
    def test_unexpected_status_is_recorded_as_failure(
        self,
        session_factory,
        _validate_target,
    ):
        response = MagicMock()
        response.status_code = 503
        response.text = "unavailable"
        session = session_factory.return_value.__enter__.return_value
        session.request.return_value.__enter__.return_value = response

        result = _perform_http_check(self.monitor)

        self.assertEqual(result.status, 0)
        self.assertEqual(result.status_code, 503)
        self.assertEqual(result.error_message, "Expected 200, got 503")

    @patch("app.tasks.monitor_checks.validate_monitor_target")
    @patch("app.tasks.monitor_checks.requests.Session")
    def test_any_request_exception_becomes_a_check_result(
        self,
        session_factory,
        _validate_target,
    ):
        session = session_factory.return_value.__enter__.return_value
        session.request.side_effect = (
            monitor_checks.requests.exceptions.InvalidURL(
            "bad URL"
            )
        )

        result = _perform_http_check(self.monitor)

        self.assertEqual(result.status, -1)
        self.assertIsNone(result.status_code)
        self.assertEqual(result.error_message, "Request failed: InvalidURL")


class PersistenceTests(unittest.TestCase):
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
        self.session_patch = patch.object(
            monitor_checks,
            "SessionLocal",
            self.TestSession,
        )
        self.session_patch.start()

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
        self.session_patch.stop()
        self.engine.dispose()

    def result(self, status, minute):
        return CheckResult(
            status=status,
            response_time=25,
            status_code=200 if status == 1 else 503,
            response_body="body",
            error_message=None if status == 1 else "Expected 200, got 503",
            checked_at=datetime(2026, 1, 1, 0, minute, tzinfo=timezone.utc),
        )

    def add_alert(self, threshold):
        with self.TestSession.begin() as db:
            db.add(
                Alert(
                    id=uuid4(),
                    user_id=self.user_id,
                    monitor_id=self.monitor_id,
                    alert_type="email",
                    recipient="owner@example.com",
                    threshold_failures=threshold,
                    is_active=True,
                )
            )

    def test_threshold_alerts_once_and_recovery_follows(self):
        self.add_alert(threshold=2)

        state, first_notifications = monitor_checks._persist_check_result(
            str(self.monitor_id),
            self.result(0, 1),
            False,
        )
        _, second_notifications = monitor_checks._persist_check_result(
            str(self.monitor_id),
            self.result(0, 2),
            False,
        )
        _, third_notifications = monitor_checks._persist_check_result(
            str(self.monitor_id),
            self.result(0, 3),
            False,
        )
        _, recovery_notifications = monitor_checks._persist_check_result(
            str(self.monitor_id),
            self.result(1, 4),
            False,
        )

        self.assertEqual(state, "recorded")
        self.assertEqual(first_notifications, [])
        self.assertEqual(len(second_notifications), 1)
        self.assertEqual(third_notifications, [])
        self.assertEqual(len(recovery_notifications), 1)

        with self.TestSession() as db:
            monitor = db.get(Monitor, self.monitor_id)
            incidents = db.scalars(select(Incident)).all()
            checks = db.scalars(select(Check)).all()
            deliveries = db.scalars(
                select(NotificationDelivery).order_by(
                    NotificationDelivery.created_at.asc()
                )
            ).all()

        self.assertEqual(monitor.status, "active")
        self.assertEqual(len(checks), 4)
        self.assertEqual(len(incidents), 1)
        self.assertEqual(incidents[0].status, "resolved")
        self.assertEqual(
            {str(delivery.id) for delivery in deliveries},
            {second_notifications[0], recovery_notifications[0]},
        )
        self.assertEqual(
            {delivery.event_type for delivery in deliveries},
            {"failure", "recovery"},
        )

    def test_paused_manual_check_does_not_change_monitor_state(self):
        with self.TestSession.begin() as db:
            db.get(Monitor, self.monitor_id).status = "paused"

        state, notifications = monitor_checks._persist_check_result(
            str(self.monitor_id),
            self.result(0, 1),
            True,
        )

        with self.TestSession() as db:
            monitor = db.get(Monitor, self.monitor_id)
            incident_count = db.query(Incident).count()
            check_count = db.query(Check).count()

        self.assertEqual(state, "recorded")
        self.assertEqual(notifications, [])
        self.assertEqual(monitor.status, "paused")
        self.assertEqual(incident_count, 0)
        self.assertEqual(check_count, 1)

    def test_legacy_plaintext_headers_are_protected_on_first_check(self):
        with self.TestSession.begin() as db:
            monitor = db.get(Monitor, self.monitor_id)
            monitor.headers = {
                "Authorization": "Bearer legacy-secret",
                "Accept": "application/json",
            }

        snapshot = monitor_checks._load_monitor_snapshot(
            str(self.monitor_id),
            False,
        )

        with self.TestSession() as db:
            stored = db.get(Monitor, self.monitor_id)

        self.assertEqual(
            snapshot.headers["Authorization"],
            "Bearer legacy-secret",
        )
        self.assertNotIn(
            "legacy-secret",
            stored.headers["Authorization"],
        )

    def test_incident_failure_rolls_back_the_entire_result(self):
        self.add_alert(threshold=1)

        with patch.object(
            monitor_checks,
            "_incident_failure_count",
            side_effect=RuntimeError("database failure"),
        ):
            with self.assertRaises(RuntimeError):
                monitor_checks._persist_check_result(
                    str(self.monitor_id),
                    self.result(0, 1),
                    False,
                )

        with self.TestSession() as db:
            monitor = db.get(Monitor, self.monitor_id)
            incident_count = db.query(Incident).count()
            check_count = db.query(Check).count()

        self.assertEqual(monitor.status, "active")
        self.assertEqual(incident_count, 0)
        self.assertEqual(check_count, 0)

    @patch("app.tasks.monitor_checks.check_monitor.delay")
    def test_scheduler_queues_only_due_monitors(self, delay):
        recent_id = uuid4()
        old_id = uuid4()
        paused_id = uuid4()
        now = datetime.now(timezone.utc)

        with self.TestSession.begin() as db:
            for monitor_id, status in (
                (recent_id, "active"),
                (old_id, "down"),
                (paused_id, "paused"),
            ):
                db.add(
                    Monitor(
                        id=monitor_id,
                        user_id=self.user_id,
                        name=str(monitor_id),
                        url="https://example.com",
                        method="GET",
                        expected_status=200,
                        check_interval=5,
                        status=status,
                    )
                )
            db.add(
                Check(
                    monitor_id=recent_id,
                    status=1,
                    response_time=10,
                    status_code=200,
                    checked_at=now - timedelta(minutes=1),
                )
            )
            db.add(
                Check(
                    monitor_id=old_id,
                    status=0,
                    response_time=10,
                    status_code=503,
                    checked_at=now - timedelta(minutes=10),
                )
            )

        result = monitor_checks.schedule_all_monitors.run()
        queued_ids = {call.args[0] for call in delay.call_args_list}

        self.assertEqual(result["queued"], 2)
        self.assertEqual(
            queued_ids,
            {str(self.monitor_id), str(old_id)},
        )


if __name__ == "__main__":
    unittest.main()
