import base64
import hashlib
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app.core.security import ENVIRONMENT, SECRET_KEY, resolve_secret_key

ENCRYPTED_VALUE_PREFIX = "enc:v1:"
REDACTED_VALUE = "[REDACTED]"
SENSITIVE_HEADER_NAMES = {
    "authorization",
    "proxy-authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "api-key",
}
SENSITIVE_HEADER_MARKERS = ("api-key", "apikey", "token", "secret")
CONFIGURED_ENCRYPTION_KEY = os.getenv("MONITOR_ENCRYPTION_KEY")
ENCRYPTION_SECRET = (
    resolve_secret_key(CONFIGURED_ENCRYPTION_KEY, ENVIRONMENT)
    if CONFIGURED_ENCRYPTION_KEY
    else SECRET_KEY
)


class HeaderDecryptionError(ValueError):
    """Raised when stored monitor credentials cannot be decrypted."""


def _fernet() -> Fernet:
    digest = hashlib.sha256(
        f"apicanary-monitor-headers-v1:{ENCRYPTION_SECRET}".encode()
    ).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def is_sensitive_header(name: str) -> bool:
    normalized = name.strip().lower()
    return (
        normalized in SENSITIVE_HEADER_NAMES
        or any(marker in normalized for marker in SENSITIVE_HEADER_MARKERS)
    )


def protect_headers(
    headers: Optional[dict[str, str]],
) -> Optional[dict[str, str]]:
    """Encrypt sensitive header values before database persistence."""
    if headers is None:
        return None

    cipher = _fernet()
    protected: dict[str, str] = {}
    for name, value in headers.items():
        if (
            is_sensitive_header(name)
            and not value.startswith(ENCRYPTED_VALUE_PREFIX)
        ):
            token = cipher.encrypt(value.encode()).decode()
            protected[name] = f"{ENCRYPTED_VALUE_PREFIX}{token}"
        else:
            protected[name] = value
    return protected


def reveal_headers(
    headers: Optional[dict[str, str]],
) -> Optional[dict[str, str]]:
    """Decrypt protected values for outbound monitor requests."""
    if headers is None:
        return None

    cipher = _fernet()
    revealed: dict[str, str] = {}
    for name, value in headers.items():
        if not value.startswith(ENCRYPTED_VALUE_PREFIX):
            revealed[name] = value
            continue

        token = value.removeprefix(ENCRYPTED_VALUE_PREFIX)
        try:
            revealed[name] = cipher.decrypt(token.encode()).decode()
        except (InvalidToken, UnicodeDecodeError) as exc:
            raise HeaderDecryptionError(
                f"Could not decrypt header {name!r}"
            ) from exc
    return revealed


def protect_updated_headers(
    existing_headers: Optional[dict[str, str]],
    submitted_headers: Optional[dict[str, str]],
) -> Optional[dict[str, str]]:
    """Preserve stored secrets when a client submits redacted placeholders."""
    if submitted_headers is None:
        return None

    existing_by_name = {
        name.lower(): value
        for name, value in (existing_headers or {}).items()
    }
    merged: dict[str, str] = {}
    for name, value in submitted_headers.items():
        existing_value = existing_by_name.get(name.lower())
        if (
            is_sensitive_header(name)
            and value == REDACTED_VALUE
            and existing_value is not None
        ):
            merged[name] = existing_value
        else:
            merged[name] = value
    return protect_headers(merged)


def redact_headers(
    headers: Optional[dict[str, str]],
) -> Optional[dict[str, str]]:
    """Return a response-safe copy without credential values."""
    if headers is None:
        return None
    return {
        name: REDACTED_VALUE if is_sensitive_header(name) else value
        for name, value in headers.items()
    }
