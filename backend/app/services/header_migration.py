from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.header_crypto import protect_headers
from app.models import Monitor


def protect_existing_monitor_headers() -> int:
    """Encrypt legacy plaintext monitor credentials in place."""
    migrated = 0
    with SessionLocal.begin() as db:
        monitors = db.execute(
            select(Monitor).where(Monitor.headers.is_not(None))
        ).scalars()
        for monitor in monitors:
            protected = protect_headers(monitor.headers)
            if protected != monitor.headers:
                monitor.headers = protected
                migrated += 1
    return migrated
