from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID


class UserLogin(BaseModel):
    email: EmailStr
    password: str