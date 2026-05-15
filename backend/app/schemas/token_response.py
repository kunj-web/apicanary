from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse