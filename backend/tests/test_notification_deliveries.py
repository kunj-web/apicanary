import os
import unittest
from datetime import datetime, timedelta, timezone
from email import message_from_string
from unittest.mock import ANY, patch
from uuid import uuid4

from celery.exceptions import Retry
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
    Monitor,
    NotificationDelivery,
    User,
)
from app.services import alert_service
from app.services.alert_service import NotificationDeliveryError
from app.services.notification_delivery import create_notification_delivery
from app.tasks import notifications


class NotificationDeliveryTaskTests(unittest.TestCase):
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
            notifications,
            "SessionLocal",
            self.TestSession,
        )
        self.session_patch.start()

        self.user_id = uuid4()
        self.monitor_id = uuid4()
        self.alert_id = uuid4()
        with self.TestSession.begin() as db:
            db.add(
                User(
                    id=self.user_id,
                    email="owner@example.com",
                    password_hash="hash",
                )
            )
            db.add(
                Monitor(
                    id=self.monitor_id,
                    user_id=self.user_id,
                    name="Checkout API",
                    url="https://example.com/health",
                    method="GET",
                    expected_status=200,
                    check_interval=5,
                    status="active",
                )
            )
            db.add(
                Alert(
                    id=self.alert_id,
                    user_id=self.user_id,
                    monitor_id=self.monitor_id,
                    alert_type="email",
                    recipient="owner@example.com",
                    threshold_failures=1,
                    is_active=True,
                )
            )

    def tearDown(self):
        self.session_patch.stop()
        self.engine.dispose()

    def add_delivery(self, status="pending", event_type="failure"):
        delivery_id = uuid4()
        with self.TestSession.begin() as db:
            db.add(
                NotificationDelivery(
                    id=delivery_id,
                    user_id=self.user_id,
                    alert_id=self.alert_id,
                    monitor_id=self.monitor_id,
                    event_type=event_type,
                    channel="email",
                    recipient="owner@example.com",
                    status=status,
                    idempotency_key=f"delivery:{delivery_id}",
                    payload={
                        "monitor_name": "Checkout API",
                        "monitor_url": "https://example.com/health",
                        "error_message": "Expected 200, got 503",
                    },
                )
            )
        return delivery_id

    @patch("app.tasks.notifications.send_email_alert")
    def test_success_is_recorded_and_duplicate_tasks_do_not_resend(self, send):
        delivery_id = self.add_delivery()

        first = notifications.send_notification_delivery.run(str(delivery_id))
        second = notifications.send_notification_delivery.run(str(delivery_id))

        with self.TestSession() as db:
            delivery = db.get(NotificationDelivery, delivery_id)

        self.assertEqual(first["state"], "sent")
        self.assertEqual(second["state"], "skipped")
        self.assertEqual(delivery.status, "sent")
        self.assertEqual(delivery.attempt_count, 1)
        self.assertIsNotNone(delivery.sent_at)
        send.assert_called_once()

    @patch("app.tasks.notifications.send_test_email")
    def test_test_event_uses_a_clearly_labeled_test_email(self, send_test):
        delivery_id = self.add_delivery(event_type="test")

        result = notifications.send_notification_delivery.run(str(delivery_id))

        self.assertEqual(result["state"], "sent")
        send_test.assert_called_once_with(
            recipient="owner@example.com",
            monitor_name="Checkout API",
            monitor_url="https://example.com/health",
        )

    @patch("app.tasks.notifications.secrets.randbelow", return_value=0)
    @patch(
        "app.tasks.notifications.send_email_alert",
        side_effect=NotificationDeliveryError(
            "SMTP delivery failed: TimeoutError"
        ),
    )
    def test_transient_failure_records_retry_with_backoff(
        self,
        _send,
        _randbelow,
    ):
        delivery_id = self.add_delivery()

        with patch.object(
            notifications.send_notification_delivery,
            "retry",
            side_effect=Retry(),
        ) as retry:
            with self.assertRaises(Retry):
                notifications.send_notification_delivery.run(str(delivery_id))

        with self.TestSession() as db:
            delivery = db.get(NotificationDelivery, delivery_id)

        self.assertEqual(delivery.status, "retrying")
        self.assertEqual(delivery.attempt_count, 1)
        self.assertEqual(
            delivery.last_error,
            "SMTP delivery failed: TimeoutError",
        )
        self.assertIsNotNone(delivery.next_attempt_at)
        retry.assert_called_once_with(
            exc=ANY,
            countdown=30,
            max_retries=5,
        )

    @patch(
        "app.tasks.notifications.send_email_alert",
        side_effect=NotificationDeliveryError(
            "SMTP delivery failed: SMTPServerDisconnected"
        ),
    )
    def test_exhausted_delivery_is_recorded_as_failed(self, _send):
        delivery_id = self.add_delivery()

        with patch.object(
            notifications.settings,
            "NOTIFICATION_MAX_RETRIES",
            0,
        ):
            with self.assertRaises(NotificationDeliveryError):
                notifications.send_notification_delivery.run(str(delivery_id))

        with self.TestSession() as db:
            delivery = db.get(NotificationDelivery, delivery_id)

        self.assertEqual(delivery.status, "failed")
        self.assertEqual(delivery.attempt_count, 1)
        self.assertIsNone(delivery.next_attempt_at)

    @patch(
        "app.tasks.notifications.send_notification_delivery.apply_async",
        side_effect=ConnectionError("redis unavailable"),
    )
    def test_broker_failure_leaves_delivery_pending_for_dispatcher(self, _delay):
        delivery_id = self.add_delivery()

        queued = notifications.enqueue_notification_delivery(delivery_id)

        with self.TestSession() as db:
            delivery = db.get(NotificationDelivery, delivery_id)

        self.assertFalse(queued)
        self.assertEqual(delivery.status, "pending")
        self.assertIsNone(delivery.queued_at)

    def test_idempotency_key_reuses_the_existing_delivery(self):
        with self.TestSession.begin() as db:
            alert = db.get(Alert, self.alert_id)
            monitor = db.get(Monitor, self.monitor_id)
            first, first_created = create_notification_delivery(
                db,
                alert=alert,
                monitor=monitor,
                event_type="failure",
                idempotency_key="same-event",
                error_message="down",
            )
            second, second_created = create_notification_delivery(
                db,
                alert=alert,
                monitor=monitor,
                event_type="failure",
                idempotency_key="same-event",
                error_message="down",
            )

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first.id, second.id)
        with self.TestSession() as db:
            self.assertEqual(db.query(NotificationDelivery).count(), 1)

    @patch("app.tasks.notifications.enqueue_notification_delivery")
    def test_dispatcher_recovers_pending_and_abandoned_deliveries(self, enqueue):
        enqueue.return_value = True
        pending_id = self.add_delivery()
        stale_id = self.add_delivery(status="queued")
        with self.TestSession.begin() as db:
            stale = db.get(NotificationDelivery, stale_id)
            stale.queued_at = datetime.now(timezone.utc) - timedelta(hours=1)

        result = notifications.dispatch_pending_deliveries.run()

        self.assertEqual(result, {"eligible": 2, "queued": 2})
        self.assertEqual(
            {call.args[0] for call in enqueue.call_args_list},
            {pending_id, stale_id},
        )


class EmailTransportTests(unittest.TestCase):
    @patch("app.services.alert_service.ssl.create_default_context")
    @patch("app.services.alert_service.smtplib.SMTP")
    def test_email_uses_timeout_tls_auth_and_public_dashboard_url(
        self,
        smtp,
        create_context,
    ):
        server = smtp.return_value.__enter__.return_value
        with (
            patch.object(
                alert_service.settings,
                "PUBLIC_APP_URL",
                "https://status.example/",
            ),
            patch.object(alert_service.settings, "SMTP_TIMEOUT_SECONDS", 7.5),
            patch.object(alert_service.settings, "SMTP_USE_TLS", True),
            patch.object(alert_service.settings, "SMTP_USE_SSL", False),
            patch.object(alert_service.settings, "SMTP_AUTH_REQUIRED", True),
        ):
            alert_service.send_email_alert(
                recipient="owner@example.com",
                monitor_name="Checkout <API>",
                monitor_url="https://example.com/health",
                error_message="Unavailable",
            )

        smtp.assert_called_once_with("localhost", 1025, timeout=7.5)
        server.starttls.assert_called_once_with(
            context=create_context.return_value
        )
        server.login.assert_called_once_with("test", "test")
        message = server.sendmail.call_args.args[2]
        self.assertIn("https://status.example/dashboard", message)
        parsed = message_from_string(message)
        html = parsed.get_payload()[1].get_payload(decode=True).decode("utf-8")
        self.assertIn("Checkout &lt;API&gt;", html)

    @patch(
        "app.services.alert_service.smtplib.SMTP",
        side_effect=TimeoutError("timed out"),
    )
    def test_transport_failures_are_raised_for_retry(self, _smtp):
        with (
            patch.object(alert_service.settings, "SMTP_USE_TLS", True),
            patch.object(alert_service.settings, "SMTP_USE_SSL", False),
        ):
            with self.assertRaises(NotificationDeliveryError) as raised:
                alert_service.send_email_alert(
                    recipient="owner@example.com",
                    monitor_name="Checkout API",
                    monitor_url="https://example.com/health",
                    error_message="Unavailable",
                )

        self.assertEqual(
            str(raised.exception),
            "SMTP delivery failed: TimeoutError",
        )


if __name__ == "__main__":
    unittest.main()
