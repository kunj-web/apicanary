from typing import Any, Dict, Literal, Optional

from pydantic import AnyHttpUrl, BaseModel, Field, field_validator


class MonitorCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    url: AnyHttpUrl = Field(..., max_length=2048)
    method: Literal[
        "GET",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
        "HEAD",
        "OPTIONS",
    ] = "GET"
    headers: Optional[Dict[str, str]] = None
    body: Optional[Dict[str, Any]] = None
    expected_status: int = Field(default=200, ge=100, le=599)
    check_interval: int = Field(default=5, ge=1, le=1440)

    @field_validator("method", mode="before")
    @classmethod
    def normalize_method(cls, value):
        return value.upper() if isinstance(value, str) else value

    @field_validator("url")
    @classmethod
    def reject_url_credentials(cls, value):
        if value.username is not None or value.password is not None:
            raise ValueError("Credentials in monitor URLs are not allowed")
        return value
