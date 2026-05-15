from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import os
from contextlib import asynccontextmanager

# Load environment variables FIRST
load_dotenv()

# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
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
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Include routers
from app.routes import auth_router, monitors_router, alerts_router

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