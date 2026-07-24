import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit

from dotenv import load_dotenv
from fastapi import HTTPException, Request, Response, status
from jose import JWTError, jwt
from passlib.context import CryptContext

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
AUTH_COOKIE_NAME = "apicanary_session"
CSRF_HEADER_NAME = "X-Requested-With"
CSRF_HEADER_VALUE = "APICanary"
SAFE_HTTP_METHODS = {"GET", "HEAD", "OPTIONS"}
DEVELOPMENT_SECRET = (
    "apicanary-development-only-secret-never-use-in-production"
)
KNOWN_WEAK_SECRETS = {
    "your-secret-key-change-in-production",
    DEVELOPMENT_SECRET,
}
DEFAULT_TRUSTED_ORIGINS = (
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
)

# Password hashing with Argon2
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def resolve_secret_key(
    configured_secret: Optional[str],
    environment: str,
) -> str:
    """Require a strong configured secret outside development and tests."""
    normalized_environment = environment.strip().lower()
    secret = (configured_secret or "").strip()
    insecure_environment = normalized_environment in {"development", "test"}

    if not secret and insecure_environment:
        logger.warning(
            "SECRET_KEY is not set; using the development-only fallback"
        )
        return DEVELOPMENT_SECRET

    if (
        len(secret) < 32
        or secret in KNOWN_WEAK_SECRETS
    ):
        if not insecure_environment:
            raise RuntimeError(
                "SECRET_KEY must be a unique value of at least 32 characters"
            )
        logger.warning(
            "SECRET_KEY is weak and must not be used outside development"
        )

    return secret or DEVELOPMENT_SECRET


def resolve_cookie_secure(
    environment: str,
    configured_value: Optional[str],
) -> bool:
    if environment.strip().lower() not in {"development", "test"}:
        return True
    return (configured_value or "false").lower() == "true"


ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
SECRET_KEY = resolve_secret_key(os.getenv("SECRET_KEY"), ENVIRONMENT)
COOKIE_SECURE = resolve_cookie_secure(
    ENVIRONMENT,
    os.getenv("COOKIE_SECURE"),
)


def get_trusted_origins() -> tuple[str, ...]:
    configured = os.getenv("TRUSTED_ORIGINS")
    if not configured:
        return DEFAULT_TRUSTED_ORIGINS
    return tuple(
        origin.strip().rstrip("/")
        for origin in configured.split(",")
        if origin.strip()
    )


def _origin_from_referer(referer: str) -> Optional[str]:
    try:
        parsed = urlsplit(referer)
    except ValueError:
        return None
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}".rstrip("/")


def validate_cookie_request(request: Request) -> None:
    """Protect cookie-authenticated mutations from cross-site requests."""
    if request.method.upper() in SAFE_HTTP_METHODS:
        return

    if request.headers.get("sec-fetch-site", "").lower() == "cross-site":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cross-site request blocked",
        )

    if request.headers.get(CSRF_HEADER_NAME) != CSRF_HEADER_VALUE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing request verification header",
        )

    source_origin = request.headers.get("origin")
    if not source_origin:
        referer = request.headers.get("referer")
        source_origin = _origin_from_referer(referer) if referer else None

    trusted_origins = get_trusted_origins()
    if source_origin:
        if source_origin.rstrip("/") not in trusted_origins:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Untrusted request origin",
            )
        return

    if request.headers.get("sec-fetch-site", "").lower() != "same-origin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Request origin could not be verified",
        )


def set_access_cookie(response: Response, token: str) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        path="/",
    )


def clear_access_cookie(response: Response) -> None:
    response.delete_cookie(
        key=AUTH_COOKIE_NAME,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        path="/",
    )


def hash_password(password: str) -> str:
    """Hash a password using Argon2."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a signed JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta
        else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and verify a JWT access token."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
