from html import escape
import logging
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.core.config import settings

logger = logging.getLogger(__name__)


class NotificationDeliveryError(RuntimeError):
    """A retryable failure raised by a notification transport."""


def _dashboard_url() -> str:
    return f"{settings.PUBLIC_APP_URL.rstrip('/')}/dashboard"


def _send_email(message: MIMEMultipart, recipient: str) -> None:
    if settings.SMTP_USE_SSL and settings.SMTP_USE_TLS:
        raise NotificationDeliveryError(
            "SMTP_USE_SSL and SMTP_USE_TLS cannot both be enabled"
        )

    try:
        smtp_class = smtplib.SMTP_SSL if settings.SMTP_USE_SSL else smtplib.SMTP
        with smtp_class(
            settings.SMTP_HOST,
            settings.SMTP_PORT,
            timeout=settings.SMTP_TIMEOUT_SECONDS,
        ) as server:
            if settings.SMTP_USE_TLS:
                server.starttls(context=ssl.create_default_context())
            if settings.SMTP_AUTH_REQUIRED:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(
                settings.ALERT_FROM_EMAIL,
                recipient,
                message.as_string(),
            )
    except NotificationDeliveryError:
        raise
    except (OSError, TimeoutError, smtplib.SMTPException) as exc:
        raise NotificationDeliveryError(
            f"SMTP delivery failed: {exc.__class__.__name__}"
        ) from exc


def send_email_alert(
    recipient: str,
    monitor_name: str,
    monitor_url: str,
    error_message: str,
) -> None:
    """Send an email alert when a monitor goes down."""
    message = MIMEMultipart("alternative")
    message["Subject"] = f"🚨 Alert: {monitor_name} is down"
    message["From"] = settings.ALERT_FROM_EMAIL
    message["To"] = recipient
    dashboard_url = _dashboard_url()

    text = f"""
APICanary Alert

{monitor_name} is down.
URL: {monitor_url}
Reason: {error_message}

View dashboard: {dashboard_url}
    """

    html = f"""
        <div style="font-family: sans-serif; max-width: 500px; margin: 0 auto; padding: 24px;">
            <h2 style="color: #ef4444;">🚨 Monitor Down</h2>
            <p style="color: #111827; font-size: 16px; font-weight: 600;">{escape(monitor_name)}</p>
            <p style="color: #6b7280; font-size: 14px;">URL: <code>{escape(monitor_url)}</code></p>
            <p style="color: #6b7280; font-size: 14px;">Reason: {escape(error_message)}</p>
            <a href="{escape(dashboard_url, quote=True)}"
               style="display:inline-block; margin-top:16px; background:#111827;
                      color:white; padding:10px 20px; border-radius:8px;
                      text-decoration:none; font-size:14px;">
                View Dashboard
            </a>
            <p style="color:#9ca3af; font-size:12px; margin-top:24px;">APICanary — API Monitoring</p>
        </div>
    """

    message.attach(MIMEText(text, "plain"))
    message.attach(MIMEText(html, "html"))
    _send_email(message, recipient)
    logger.info("Alert email sent for monitor %s", monitor_name)


def send_test_email(
    recipient: str,
    monitor_name: str,
    monitor_url: str,
) -> None:
    """Send a clearly labeled test email for an alert rule."""
    message = MIMEMultipart("alternative")
    message["Subject"] = f"🧪 Test alert: {monitor_name}"
    message["From"] = settings.ALERT_FROM_EMAIL
    message["To"] = recipient
    dashboard_url = _dashboard_url()

    text = f"""
APICanary Test Alert

Your email notification for {monitor_name} is configured correctly.
URL: {monitor_url}

View dashboard: {dashboard_url}
    """

    html = f"""
        <div style="font-family: sans-serif; max-width: 500px; margin: 0 auto; padding: 24px;">
            <h2 style="color: #2563eb;">🧪 Test Alert</h2>
            <p style="color: #111827; font-size: 16px; font-weight: 600;">{escape(monitor_name)}</p>
            <p style="color: #6b7280; font-size: 14px;">Your email notification is configured correctly.</p>
            <p style="color: #6b7280; font-size: 14px;">URL: <code>{escape(monitor_url)}</code></p>
            <a href="{escape(dashboard_url, quote=True)}"
               style="display:inline-block; margin-top:16px; background:#111827;
                      color:white; padding:10px 20px; border-radius:8px;
                      text-decoration:none; font-size:14px;">
                View Dashboard
            </a>
            <p style="color:#9ca3af; font-size:12px; margin-top:24px;">APICanary — API Monitoring</p>
        </div>
    """

    message.attach(MIMEText(text, "plain"))
    message.attach(MIMEText(html, "html"))
    _send_email(message, recipient)
    logger.info("Test email sent for monitor %s", monitor_name)


def send_recovery_email(
    recipient: str,
    monitor_name: str,
    monitor_url: str,
    duration_minutes: int,
) -> None:
    """Send an email when a monitor recovers."""
    message = MIMEMultipart("alternative")
    message["Subject"] = f"✅ Recovered: {monitor_name} is back up"
    message["From"] = settings.ALERT_FROM_EMAIL
    message["To"] = recipient
    dashboard_url = _dashboard_url()

    text = f"""
APICanary — Monitor Recovered

{monitor_name} is back up.
URL: {monitor_url}
Downtime: {duration_minutes} minutes
View dashboard: {dashboard_url}
    """

    html = f"""
        <div style="font-family: sans-serif; max-width: 500px; margin: 0 auto; padding: 24px;">
            <h2 style="color: #10b981;">✅ Monitor Recovered</h2>
            <p style="color: #111827; font-size: 16px; font-weight: 600;">{escape(monitor_name)}</p>
            <p style="color: #6b7280; font-size: 14px;">URL: <code>{escape(monitor_url)}</code></p>
            <p style="color: #6b7280; font-size: 14px;">Downtime: {duration_minutes} minutes</p>
            <a href="{escape(dashboard_url, quote=True)}"
               style="display:inline-block; margin-top:16px; background:#111827;
                      color:white; padding:10px 20px; border-radius:8px;
                      text-decoration:none; font-size:14px;">
                View Dashboard
            </a>
            <p style="color:#9ca3af; font-size:12px; margin-top:24px;">APICanary — API Monitoring</p>
        </div>
    """

    message.attach(MIMEText(text, "plain"))
    message.attach(MIMEText(html, "html"))
    _send_email(message, recipient)
    logger.info("Recovery email sent for monitor %s", monitor_name)
