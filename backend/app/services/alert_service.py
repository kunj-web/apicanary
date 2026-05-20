import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


def send_email_alert(recipient: str, monitor_name: str, monitor_url: str, error_message: str):
    """Send email alert when a monitor goes down"""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"🚨 Alert: {monitor_name} is down"
        msg["From"] = settings.ALERT_FROM_EMAIL
        msg["To"] = recipient

        # Plain text fallback
        text = f"""
APICanary Alert

{monitor_name} is down.
URL: {monitor_url}
Reason: {error_message}

Login to your dashboard to view details.
        """

        # HTML version
        html = f"""
        <div style="font-family: sans-serif; max-width: 500px; margin: 0 auto; padding: 24px;">
            <h2 style="color: #ef4444;">🚨 Monitor Down</h2>
            <p style="color: #111827; font-size: 16px; font-weight: 600;">{monitor_name}</p>
            <p style="color: #6b7280; font-size: 14px;">URL: <code>{monitor_url}</code></p>
            <p style="color: #6b7280; font-size: 14px;">Reason: {error_message}</p>
            <a href="http://localhost:3000/dashboard"
               style="display:inline-block; margin-top:16px; background:#111827;
                      color:white; padding:10px 20px; border-radius:8px;
                      text-decoration:none; font-size:14px;">
                View Dashboard
            </a>
            <p style="color:#9ca3af; font-size:12px; margin-top:24px;">APICanary — API Monitoring</p>
        </div>
        """

        msg.attach(MIMEText(text, "plain"))
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.ALERT_FROM_EMAIL, recipient, msg.as_string())

        logger.info(f"Alert email sent to {recipient} for monitor {monitor_name}")

    except Exception as e:
        logger.error(f"Failed to send email alert: {e}")


def send_recovery_email(recipient: str, monitor_name: str, monitor_url: str, duration_minutes: int):
    """Send email when monitor recovers"""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"✅ Recovered: {monitor_name} is back up"
        msg["From"] = settings.ALERT_FROM_EMAIL
        msg["To"] = recipient

        text = f"""
APICanary — Monitor Recovered

{monitor_name} is back up.
URL: {monitor_url}
Downtime: {duration_minutes} minutes
        """

        html = f"""
        <div style="font-family: sans-serif; max-width: 500px; margin: 0 auto; padding: 24px;">
            <h2 style="color: #10b981;">✅ Monitor Recovered</h2>
            <p style="color: #111827; font-size: 16px; font-weight: 600;">{monitor_name}</p>
            <p style="color: #6b7280; font-size: 14px;">URL: <code>{monitor_url}</code></p>
            <p style="color: #6b7280; font-size: 14px;">Downtime: {duration_minutes} minutes</p>
            <a href="http://localhost:3000/dashboard"
               style="display:inline-block; margin-top:16px; background:#111827;
                      color:white; padding:10px 20px; border-radius:8px;
                      text-decoration:none; font-size:14px;">
                View Dashboard
            </a>
            <p style="color:#9ca3af; font-size:12px; margin-top:24px;">APICanary — API Monitoring</p>
        </div>
        """

        msg.attach(MIMEText(text, "plain"))
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.ALERT_FROM_EMAIL, recipient, msg.as_string())

        logger.info(f"Recovery email sent to {recipient} for monitor {monitor_name}")

    except Exception as e:
        logger.error(f"Failed to send recovery email: {e}")