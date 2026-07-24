from fastapi import (
    APIRouter,
    HTTPException,
    Depends,
    Request,
    Response,
    status,
)
from sqlalchemy.orm import Session
from app.schemas import UserCreate, UserLogin, UserResponse, TokenResponse
from app.models import User
from app.core import hash_password, verify_password, create_access_token
from app.core.dependencies import get_db, get_current_user
from app.core.security import (
    AUTH_COOKIE_NAME,
    clear_access_cookie,
    set_access_cookie,
    validate_cookie_request,
)
from uuid import uuid4

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse)
async def signup(
    user_data: UserCreate,
    response: Response,
    db: Session = Depends(get_db),
):
    """Create new user account"""
    # Check if user exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    # Create new user
    user = User(
        id=uuid4(),
        email=user_data.email,
        password_hash=hash_password(user_data.password),
        full_name=user_data.full_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Create JWT token
    access_token = create_access_token(data={"sub": str(user.id)})
    set_access_cookie(response, access_token)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserResponse.model_validate(user),
    }


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    response: Response,
    db: Session = Depends(get_db),
):
    """Login user"""
    user = db.query(User).filter(User.email == credentials.email).first()

    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )

    # Create JWT token
    access_token = create_access_token(data={"sub": str(user.id)})
    set_access_cookie(response, access_token)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserResponse.model_validate(user),
    }


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user info"""
    return UserResponse.model_validate(current_user)


@router.post("/session", response_model=UserResponse)
async def migrate_browser_session(
    response: Response,
    current_user: User = Depends(get_current_user),
):
    """Exchange an existing bearer token for the browser session cookie."""
    access_token = create_access_token(data={"sub": str(current_user.id)})
    set_access_cookie(response, access_token)
    return UserResponse.model_validate(current_user)


@router.post("/logout")
async def logout(request: Request, response: Response):
    """Clear the browser session cookie."""
    if request.cookies.get(AUTH_COOKIE_NAME):
        validate_cookie_request(request)
    clear_access_cookie(response)
    response.headers["Cache-Control"] = "no-store"
    return {"message": "Logged out successfully"}
