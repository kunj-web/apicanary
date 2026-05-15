from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID


class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True