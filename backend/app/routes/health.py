"""
Legrand GeoAI — Routes de santé.

Endpoints pour vérifier l'état des services.
"""

import httpx
import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db

router = APIRouter(prefix="/api/health", tags=["Santé"])
logger = structlog.get_logger()


@router.get("")
async def health_check():
    """Vérification basique — toujours 200 si le backend tourne."""
    return {"status": "ok", "service": "Legrand GeoAI Backend"}


@router.get("/live")
async def liveness():
    """Liveness probe — le processus est vivant."""
    return {"status": "alive"}


@router.get("/ready")
async def readiness(db: AsyncSession = Depends(get_db)):
    """
    Readiness probe — vérifie tous les services dépendants.

    Returns:
        État de chaque service (postgres, redis, ollama, chromadb).
        503 si un service critique est indisponible.
    """
    checks = {}
    all_ok = True

    # --- PostgreSQL ---
    try:
        await db.execute(text("SELECT 1"))
        checks["postgres"] = {"status": "ok"}
    except Exception as e:
        checks["postgres"] = {"status": "error", "detail": str(e)}
        all_ok = False
        logger.error("health_check_postgres_failed", error=str(e))

    # --- Hatchet (orchestrateur du pipeline) ---
    try:
        from app.hatchet.client import get_hatchet

        hatchet = get_hatchet()
        version = await hatchet.aio_get_engine_version()
        checks["hatchet"] = {"status": "ok", "engine_version": str(version)}
    except Exception as e:
        checks["hatchet"] = {"status": "error", "detail": str(e)}
        all_ok = False
        logger.error("health_check_hatchet_failed", error=str(e))

    # --- Ollama ---
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            resp.raise_for_status()
            models = resp.json().get("models", [])
            model_names = [m.get("name", "") for m in models]
            checks["ollama"] = {
                "status": "ok",
                "models_loaded": model_names,
            }
    except Exception as e:
        checks["ollama"] = {"status": "error", "detail": str(e)}
        all_ok = False
        logger.error("health_check_ollama_failed", error=str(e))

    # --- ChromaDB ---
    try:
        import chromadb

        client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
        heartbeat = client.heartbeat()
        collections = client.list_collections()
        checks["chromadb"] = {
            "status": "ok",
            "heartbeat": heartbeat,
            "collections_count": len(collections),
        }
    except Exception as e:
        checks["chromadb"] = {"status": "error", "detail": str(e)}
        all_ok = False
        logger.error("health_check_chromadb_failed", error=str(e))

    from fastapi.responses import JSONResponse

    status_code = 200 if all_ok else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": "ok" if all_ok else "degraded", "checks": checks},
    )
