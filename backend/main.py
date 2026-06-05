"""
ICCBPO Certificate QR Code Checker - FastAPI Application Entry Point
"""
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from loguru import logger

from app.config import settings
from app.database import engine, Base, AsyncSessionLocal
from app.routes import auth, upload, certificates, reports, admin, health
from app.utils.security import create_initial_admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    logger.info("Starting ICCBPO Certificate Checker...")

    # Create DB tables if they don't exist (handled by Alembic in prod)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create initial admin user if not exists
    async with AsyncSessionLocal() as session:
        await create_initial_admin(session)

    # Ensure required directories exist
    for directory in [settings.UPLOAD_DIR, settings.SCREENSHOT_DIR, settings.REPORTS_DIR]:
        os.makedirs(directory, exist_ok=True)

    logger.info("Application startup complete.")
    yield

    logger.info("Shutting down ICCBPO Certificate Checker...")
    await engine.dispose()


# Rate limiter
limiter = Limiter(key_func=get_remote_address)

# FastAPI app
app = FastAPI(
    title="ICCBPO Certificate QR Code Checker",
    description="""
    Enterprise-grade background check certificate validation system for BPO/HR compliance teams.

    ## Features
    - **PDF Upload**: Single and bulk PDF uploads with drag-and-drop
    - **OCR Analysis**: Multi-language OCR (English, Spanish, Portuguese, French)
    - **QR Extraction**: Automatic QR code detection and extraction
    - **Web Verification**: Headless browser verification of QR destinations
    - **Fraud Detection**: AI-assisted document tampering detection
    - **Reports**: PDF, Excel, CSV export

    ## Authentication
    Use `/api/v1/auth/login` to obtain a JWT token.
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Trusted hosts (production hardening)
if not settings.DEBUG:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.ALLOWED_HOSTS,
    )


# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if not settings.DEBUG:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"{request.method} {request.url.path} - {request.client.host if request.client else 'unknown'}")
    response = await call_next(request)
    logger.info(f"Response: {response.status_code}")
    return response


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error. Please contact support."}
    )


# Mount static files for screenshots
os.makedirs(settings.SCREENSHOT_DIR, exist_ok=True)
app.mount("/screenshots", StaticFiles(directory=settings.SCREENSHOT_DIR), name="screenshots")
app.mount("/reports", StaticFiles(directory=settings.REPORTS_DIR), name="reports")

# Register routers
app.include_router(health.router, tags=["Health"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(upload.router, prefix="/api/v1/upload", tags=["Upload"])
app.include_router(certificates.router, prefix="/api/v1/certificates", tags=["Certificates"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["Reports"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])
