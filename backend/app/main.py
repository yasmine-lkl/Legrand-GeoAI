"""
Legrand GeoAI — Application FastAPI principale.

Point d'entrée de l'API backend.
"""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings

# Map log level string to stdlib int
import logging
_LOG_LEVEL = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

# Configuration structlog
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(_LOG_LEVEL),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestion du cycle de vie de l'application."""
    # --- Startup ---
    logger.info("app_startup", service="Legrand GeoAI Backend", version="1.0.0")

    # Créer la table api_keys si elle n'existe pas encore
    try:
        from sqlalchemy import text
        from app.database import engine
        from app.models.api_key import ApiKey  # noqa: F401
        from app.models.base import Base
        async with engine.begin() as conn:
            await conn.run_sync(
                lambda sync_conn: Base.metadata.create_all(
                    sync_conn, tables=[ApiKey.__table__], checkfirst=True
                )
            )
            # Widen key_prefix if it was created with the old VARCHAR(12)
            await conn.execute(
                text(
                    "ALTER TABLE api_keys "
                    "ALTER COLUMN key_prefix TYPE VARCHAR(20)"
                )
            )
        logger.info("api_keys_table_ready")
    except Exception as e:
        logger.warning("api_keys_table_failed", error=str(e))

    # Pré-charger le client Hatchet (construction paresseuse + en cache).
    # Tolère l'absence de jeton : le backend démarre quand même, seules les
    # routes d'ingestion échoueront proprement tant que le jeton n'est pas posé.
    try:
        from app.hatchet.client import get_hatchet

        get_hatchet()
        logger.info("hatchet_client_ready")
    except Exception as e:
        logger.warning("hatchet_client_unavailable", error=str(e))

    yield

    # --- Shutdown ---
    logger.info("app_shutdown")

    from app.database import engine

    await engine.dispose()


# --- Création de l'app ---
app = FastAPI(
    title="Legrand GeoAI",
    description="Agent IA interne pour la géomatique — API Backend",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
    redirect_slashes=False,
)

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En production : restreindre au domaine Caddy
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Sécurité ---
from app.middleware import RateLimitMiddleware, SecurityHeadersMiddleware

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware, requests_per_minute=120, burst=20)


# --- Exception handler global ---
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Capture toutes les exceptions non gérées."""
    logger.error(
        "unhandled_exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Erreur interne du serveur"},
    )


# --- Enregistrement des routes ---
from app.routes.api_keys import router as api_keys_router
from app.routes.auth import router as auth_router
from app.routes.chat import router as chat_router
from app.routes.collections import router as collections_router
from app.routes.documents import router as documents_router
from app.routes.health import router as health_router
from app.routes.users import router as users_router

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(collections_router)
app.include_router(documents_router)
app.include_router(chat_router)
app.include_router(api_keys_router)
