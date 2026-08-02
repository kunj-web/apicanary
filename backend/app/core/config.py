from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]

class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str
    SMTP_HOST: str
    SMTP_PORT: int
    SMTP_USER: str
    SMTP_PASSWORD: str
    ALERT_FROM_EMAIL: str
    PUBLIC_APP_URL: str = "http://localhost:3000"
    SMTP_TIMEOUT_SECONDS: float = 10.0
    SMTP_USE_TLS: bool = True
    SMTP_USE_SSL: bool = False
    SMTP_AUTH_REQUIRED: bool = True
    NOTIFICATION_MAX_RETRIES: int = 5
    NOTIFICATION_RETRY_BASE_SECONDS: int = 30
    NOTIFICATION_RETRY_MAX_SECONDS: int = 900
    NOTIFICATION_DELIVERY_LEASE_SECONDS: int = 600

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        extra="ignore",
    )

settings = Settings()
