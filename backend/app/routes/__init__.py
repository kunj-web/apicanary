from app.routes.auth import router as auth_router
from app.routes.monitors import router as monitors_router
from app.routes.alerts import router as alerts_router

__all__ = ["auth_router", "monitors_router", "alerts_router"]