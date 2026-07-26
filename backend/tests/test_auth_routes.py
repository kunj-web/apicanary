import asyncio
import os
import unittest
from uuid import uuid4

from fastapi import HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")

from app.core.dependencies import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.models import Base, User
from app.routes.auth import login, logout, signup
from app.schemas import UserCreate, UserLogin


def make_request(method="GET", headers=None, cookie=None):
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
            "path": "/api/auth",
            "query_string": b"",
            "headers": raw_headers,
            "client": ("127.0.0.1", 1234),
            "server": ("localhost", 8000),
        }
    )


class AuthenticationRouteTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
        )

    def tearDown(self):
        self.engine.dispose()

    def add_user(self, email="owner@example.com", password="ValidPass1!"):
        user_id = uuid4()
        with self.Session.begin() as db:
            db.add(
                User(
                    id=user_id,
                    email=email,
                    password_hash=hash_password(password),
                    full_name="Owner",
                )
            )
        return user_id

    def test_signup_hashes_password_sets_cookie_and_rejects_duplicates(self):
        payload = UserCreate(
            email="new@example.com",
            password="ValidPass1!",
            full_name="New Owner",
        )
        response = Response()
        with self.Session() as db:
            result = asyncio.run(signup(payload, response, db))
            stored = (
                db.query(User)
                .filter(User.email == "new@example.com")
                .one()
            )
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(signup(payload, Response(), db))

        self.assertEqual(result["token_type"], "bearer")
        self.assertEqual(result["user"].email, "new@example.com")
        self.assertNotEqual(stored.password_hash, "ValidPass1!")
        self.assertTrue(verify_password("ValidPass1!", stored.password_hash))
        self.assertIn("httponly", response.headers["set-cookie"].lower())
        self.assertEqual(raised.exception.status_code, 400)

    def test_login_rejects_unknown_email_and_wrong_password(self):
        self.add_user()
        cases = (
            UserLogin(email="missing@example.com", password="ValidPass1!"),
            UserLogin(email="owner@example.com", password="WrongPass1!"),
        )
        with self.Session() as db:
            for credentials in cases:
                with self.subTest(email=credentials.email):
                    with self.assertRaises(HTTPException) as raised:
                        asyncio.run(login(credentials, Response(), db))
                    self.assertEqual(raised.exception.status_code, 401)

    def test_missing_invalid_and_deleted_user_tokens_are_rejected(self):
        user_id = self.add_user()
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="not-a-jwt",
        )
        with self.Session() as db:
            with self.assertRaises(HTTPException) as missing:
                asyncio.run(
                    get_current_user(
                        request=make_request(),
                        credentials=None,
                        db=db,
                    )
                )
            with self.assertRaises(HTTPException) as invalid:
                asyncio.run(
                    get_current_user(
                        request=make_request(),
                        credentials=credentials,
                        db=db,
                    )
                )
            db.delete(db.get(User, user_id))
            db.commit()
            deleted_credentials = HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials=create_access_token({"sub": str(user_id)}),
            )
            with self.assertRaises(HTTPException) as deleted:
                asyncio.run(
                    get_current_user(
                        request=make_request(),
                        credentials=deleted_credentials,
                        db=db,
                    )
                )

        self.assertEqual(missing.exception.status_code, 401)
        self.assertEqual(invalid.exception.status_code, 401)
        self.assertEqual(deleted.exception.status_code, 401)

    def test_logout_clears_the_session_cookie(self):
        response = Response()

        result = asyncio.run(
            logout(make_request(method="POST"), response)
        )

        self.assertEqual(result["message"], "Logged out successfully")
        cookie = response.headers["set-cookie"].lower()
        self.assertIn("apicanary_session=", cookie)
        self.assertIn("max-age=0", cookie)
        self.assertEqual(response.headers["cache-control"], "no-store")


if __name__ == "__main__":
    unittest.main()
