from pydantic import BaseModel

from app.schemas.user_response import UserResponse


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse