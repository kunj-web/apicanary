import asyncio
import os
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi import HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import ValidationError
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
os.environ.setdefault("ENVIRONMENT", "test")

from app.core.dependencies import get_current_user
from app.core.header_crypto import (
    ENCRYPTED_VALUE_PREFIX,
    REDACTED_VALUE,
    protect_headers,
    protect_updated_headers,
    redact_headers,
    reveal_headers,
)
from app.core.security import (
    AUTH_COOKIE_NAME,
    CSRF_HEADER_NAME,
    CSRF_HEADER_VALUE,
    create_access_token,
    resolve_cookie_secure,
    resolve_secret_key,
    set_access_cookie,
    validate_cookie_request,
)
from app.models import Base, User
from app.routes.auth import login, migrate_browser_session
from app.schemas import AlertCreate, MonitorCreate, UserLogin
from app.services.monitor_security import (
    UnsafeMonitorTarget,
    validate_monitor_target,
)


def make_request(
    method="GET",
    headers=None,
    cookie=None,
):
    raw_headers = [
        (name.lower().encode(), value.encode())
        for name, value in (headers or {}).items()
    ]
    if cookie:
        raw_headers.append((b"cookie", cookie.encode()))
    return Request(
        {
            "type": "http",
            "method": method,
            "scheme": "http",
            "path": "/api/monitors",
            "query_string": b"",
            "headers": raw_headers,
            "client": ("127.0.0.1", 1234),
            "server": ("localhost", 8000),
        }
    )


class SecretAndCookieTests(unittest.TestCase):
    def test_production_rejects_missing_or_weak_secrets(self):
        with self.assertRaises(RuntimeError):
            resolve_secret_key(None, "production")
        with self.assertRaises(RuntimeError):
            resolve_secret_key("short", "production")

    def test_production_accepts_a_unique_long_secret(self):
        secret = "unique-production-secret-value-that-is-long-enough"
        self.assertEqual(resolve_secret_key(secret, "production"), secret)

    def test_production_cookies_are_always_secure(self):
        self.assertTrue(resolve_cookie_secure("production", "false"))
        self.assertFalse(resolve_cookie_secure("development", "false"))

    def test_session_cookie_is_http_only_and_same_site(self):
        response = Response()
        set_access_cookie(response, "signed-token")

        cookie = response.headers["set-cookie"].lower()
        self.assertIn("httponly", cookie)
        self.assertIn("samesite=lax", cookie)
        self.assertIn("path=/", cookie)

    def test_cookie_mutation_requires_origin_and_custom_header(self):
        valid = make_request(
            method="POST",
            headers={
                "Origin": "http://localhost:3000",
                CSRF_HEADER_NAME: CSRF_HEADER_VALUE,
                "Sec-Fetch-Site": "same-origin",
            },
        )
        validate_cookie_request(valid)

        invalid = make_request(
            method="POST",
            headers={
                "Origin": "https://attacker.example",
                CSRF_HEADER_NAME: CSRF_HEADER_VALUE,
                "Sec-Fetch-Site": "cross-site",
            },
        )
        with self.assertRaises(HTTPException) as raised:
            validate_cookie_request(invalid)
        self.assertEqual(raised.exception.status_code, 403)


class HeaderProtectionTests(unittest.TestCase):
    def test_sensitive_headers_encrypt_round_trip_and_redact(self):
        headers = {
            "Authorization": "Bearer top-secret",
            "X-API-Key": "api-secret",
            "Accept": "application/json",
        }

        protected = protect_headers(headers)

        self.assertTrue(
            protected["Authorization"].startswith(ENCRYPTED_VALUE_PREFIX)
        )
        self.assertNotIn("top-secret", protected["Authorization"])
        self.assertEqual(reveal_headers(protected), headers)
        self.assertEqual(
            redact_headers(protected)["Authorization"],
            REDACTED_VALUE,
        )
        self.assertEqual(
            redact_headers(protected)["Accept"],
            "application/json",
        )

    def test_redacted_update_preserves_the_existing_secret(self):
        protected = protect_headers(
            {"Authorization": "Bearer original-secret"}
        )

        updated = protect_updated_headers(
            protected,
            {"authorization": REDACTED_VALUE},
        )

        self.assertEqual(
            reveal_headers(updated)["authorization"],
            "Bearer original-secret",
        )


class MonitorTargetTests(unittest.TestCase):
    @patch("app.services.monitor_security.socket.getaddrinfo")
    def test_public_target_is_allowed(self, getaddrinfo):
        getaddrinfo.return_value = [
            (2, 1, 6, "", ("93.184.216.34", 443)),
        ]

        addresses = validate_monitor_target(
            "https://example.com/health"
        )

        self.assertEqual(addresses, ("93.184.216.34",))

    @patch("app.services.monitor_security.socket.getaddrinfo")
    def test_any_private_resolution_blocks_the_target(self, getaddrinfo):
        getaddrinfo.return_value = [
            (2, 1, 6, "", ("93.184.216.34", 443)),
            (2, 1, 6, "", ("10.0.0.5", 443)),
        ]

        with self.assertRaises(UnsafeMonitorTarget):
            validate_monitor_target("https://example.com/health")

    def test_localhost_url_credentials_and_unsafe_schemes_are_blocked(self):
        blocked = (
            "http://localhost/health",
            "http://user:pass@example.com/health",
            "file:///etc/passwd",
        )
        for url in blocked:
            with self.subTest(url=url):
                with self.assertRaises(UnsafeMonitorTarget):
                    validate_monitor_target(url)


class InputValidationTests(unittest.TestCase):
    def test_monitor_method_is_normalized_and_restricted(self):
        monitor = MonitorCreate(
            name="API",
            url="https://example.com/health",
            method="post",
        )
        self.assertEqual(monitor.method, "POST")

        with self.assertRaises(ValidationError):
            MonitorCreate(
                name="API",
                url="https://example.com",
                method="TRACE",
            )

    def test_monitor_url_and_alert_recipient_are_validated(self):
        with self.assertRaises(ValidationError):
            MonitorCreate(
                name="API",
                url="file:///etc/passwd",
            )
        with self.assertRaises(ValidationError):
            MonitorCreate(
                name="API",
                url="https://user:pass@example.com",
            )
        with self.assertRaises(ValidationError):
            AlertCreate(
                monitor_id=uuid4(),
                alert_type="slack",
                recipient="not-an-email",
            )


class AuthenticationCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.user_id = uuid4()
        with self.Session.begin() as db:
            db.add(
                User(
                    id=self.user_id,
                    email="owner@example.com",
                    password_hash="hash",
                    full_name="Owner",
                )
            )
        self.token = create_access_token({"sub": str(self.user_id)})

    def tearDown(self):
        self.engine.dispose()

    def test_bearer_auth_remains_compatible(self):
        request = make_request(
            method="POST",
            headers={"Sec-Fetch-Site": "cross-site"},
        )
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=self.token,
        )
        with self.Session() as db:
            user = asyncio.run(
                get_current_user(
                    request=request,
                    credentials=credentials,
                    db=db,
                )
            )
        self.assertEqual(user.id, self.user_id)

    def test_cookie_auth_works_with_csrf_verification(self):
        request = make_request(
            method="POST",
            headers={
                "Origin": "http://localhost:3000",
                CSRF_HEADER_NAME: CSRF_HEADER_VALUE,
                "Sec-Fetch-Site": "same-origin",
            },
            cookie=f"{AUTH_COOKIE_NAME}={self.token}",
        )
        with self.Session() as db:
            user = asyncio.run(
                get_current_user(
                    request=request,
                    credentials=None,
                    db=db,
                )
            )
        self.assertEqual(user.id, self.user_id)

    @patch("app.routes.auth.verify_password", return_value=True)
    def test_login_keeps_bearer_response_and_sets_http_only_cookie(
        self,
        _verify_password,
    ):
        response = Response()
        with self.Session() as db:
            result = asyncio.run(
                login(
                    credentials=UserLogin(
                        email="owner@example.com",
                        password="password",
                    ),
                    response=response,
                    db=db,
                )
            )

        self.assertIn("access_token", result)
        self.assertEqual(result["token_type"], "bearer")
        self.assertIn("httponly", response.headers["set-cookie"].lower())

    def test_existing_bearer_session_can_migrate_without_relogin(self):
        response = Response()
        with self.Session() as db:
            user = db.get(User, self.user_id)
            migrated = asyncio.run(
                migrate_browser_session(
                    response=response,
                    current_user=user,
                )
            )

        self.assertEqual(migrated.id, self.user_id)
        self.assertIn("httponly", response.headers["set-cookie"].lower())


if __name__ == "__main__":
    unittest.main()
