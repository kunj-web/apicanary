from pydantic import BaseModel, EmailStr, Field
from pydantic import field_validator
import re


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=2, max_length=255)

    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        if not re.search(r'[A-Z]', v):
            raise ValueError(
                'Password must contain uppercase letter'
            )

        if not re.search(r'[a-z]', v):
            raise ValueError(
                'Password must contain lowercase letter'
            )

        if not re.search(r'[0-9]', v):
            raise ValueError(
                'Password must contain digit'
            )

        if not re.search(
            r'[@#$!%^&*()_+\-=\[\]{};:\'",.<>?/\\|`~]',
            v
        ):
            raise ValueError(
                'Password must contain special character'
            )

        return v

    @field_validator('full_name')
    @classmethod
    def validate_full_name(cls, v):
        cleaned = " ".join(v.split())

        if len(cleaned.split()) < 2:
            raise ValueError(
                'Full name must contain first and last name'
            )

        return cleaned