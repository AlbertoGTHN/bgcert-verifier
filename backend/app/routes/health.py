"""Health check endpoint."""
from fastapi import APIRouter
from app.database import check_db_health

router = APIRouter()


@router.get("/health")
async def health_check():
    db_ok = await check_db_health()
    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "ok" if db_ok else "error",
        "version": "1.0.0",
    }
