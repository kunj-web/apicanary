from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from contextlib import asynccontextmanager
import logging

# Load environment variables FIRST
load_dotenv()

from app.core.security import get_trusted_origins  # noqa: E402
from app.routes import auth_router, monitors_router, alerts_router  # noqa: E402
from app.services.header_migration import (  # noqa: E402
    protect_existing_monitor_headers,
)

logger = logging.getLogger(__name__)

# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        migrated = protect_existing_monitor_headers()
        if migrated:
            logger.info(
                "Protected sensitive headers for %s existing monitors",
                migrated,
            )
    except Exception:
        logger.exception("Could not migrate legacy monitor headers")
    print("🚀 APICanary API starting...")
    yield
    print("🛑 APICanary API shutting down...")

app = FastAPI(
    title="APICanary",
    description="API monitoring tool - Watch your endpoints 24/7",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(get_trusted_origins()),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


app.include_router(auth_router)
app.include_router(monitors_router)
app.include_router(alerts_router)

# Health check endpoint
@app.get("/health")
async def health_check():
    return JSONResponse(
        status_code=200,
        content={"status": "ok", "message": "APICanary is running"}
    )

# Root endpoint
@app.get("/")
async def root():
    return JSONResponse(
        status_code=200,
        content={
            "message": "APICanary API",
            "version": "1.0.0",
            "docs": "/docs",
            "health": "/health"
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
