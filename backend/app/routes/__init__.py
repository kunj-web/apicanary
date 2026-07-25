from app.routes.auth import router as auth_router
from app.routes.monitors import router as monitors_router
from app.routes.alerts import router as alerts_router
from app.routes.incidents import router as incidents_router

__all__ = [
    "alerts_router",
    "auth_router",
    "incidents_router",
    "monitors_router",
]
