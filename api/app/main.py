"""Tempmail Server FastAPI application"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import threading
import logging
import os

from app.config import settings
from app.database import check_db_connection
from app.routers import addresses_router, emails_router
from app.cleanup import run_cleanup_loop

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Tempmail Server API",
    description="Tempmail backend API - receive and manage temporary email addresses",
    version="1.0.0",
    docs_url="/docs" if settings.DOCS_ENABLED else None,
    redoc_url="/redoc" if settings.DOCS_ENABLED else None,
    openapi_url="/openapi.json" if settings.DOCS_ENABLED else None
)

# CORS middleware - configured via config.yaml
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOW_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)


@app.on_event("startup")
async def startup_event():
    """Run on application startup"""
    # Skip startup tasks in test mode
    if os.getenv("TESTING"):
        logger.info("Running in test mode - skipping startup tasks")
        return

    logger.info("Tempmail Server API starting...")

    # Check database connection
    if not check_db_connection():
        logger.error("Failed to connect to database!")
        raise Exception("Database connection failed")

    logger.info("Database connection successful")
    logger.info(f"Configured domains: {settings.DOMAINS}")
    logger.info(f"Address lifetime: {settings.ADDRESS_LIFETIME_HOURS}h")
    logger.info(f"CORS allowed origins: {settings.CORS_ALLOW_ORIGINS}")

    # Start cleanup thread
    cleanup_thread = threading.Thread(target=run_cleanup_loop, daemon=True)
    cleanup_thread.start()
    logger.info("Cleanup thread started")

    logger.info("Tempmail Server API ready!")


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown"""
    logger.info("Tempmail Server API shutting down...")


# Health check endpoint
@app.get("/api/v1/health")
def health_check():
    """Health check endpoint for monitoring"""
    db_ok = check_db_connection()

    return JSONResponse(
        status_code=200 if db_ok else 503,
        content={
            "status": "healthy" if db_ok else "unhealthy",
            "database": "connected" if db_ok else "disconnected",
            "domains": settings.DOMAINS
        }
    )


# Include routers
app.include_router(addresses_router)
app.include_router(emails_router)


# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={"detail": "Not found"}
    )


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    logger.error(f"Internal error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True,  # For development
        log_level=settings.LOG_LEVEL.lower()
    )
