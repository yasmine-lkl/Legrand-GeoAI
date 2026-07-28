"""
Legrand GeoAI — Worker Hatchet.

Point d'entrée du processus worker : enregistre tous les workflows
(ingestion, OCR par page, ré-indexation, crons) et démarre l'exécution.

Lancement :
    python -m app.hatchet.worker
"""

import structlog
from hatchet_sdk import RateLimitDuration

from app.hatchet.client import get_hatchet
from app.hatchet.workflows import (
    ALL_WORKFLOWS,
    EMBED_RATE_LIMIT_KEY,
    lifespan,
)

logger = structlog.get_logger()

# Nombre de tâches que le worker peut suivre simultanément.
# La VRAIE protection des ressources (GPU/Ollama) est assurée par les clés de
# concurrence des tâches (OCR max 2, embeddings max 2). Les slots, plus larges,
# permettent aux tâches « parentes » en attente de fan-out de ne pas bloquer.
WORKER_SLOTS = 10

# Débit max d'appels d'embedding vers Ollama (protège le service).
EMBED_RATE_PER_MINUTE = 60


def main() -> None:
    """Configure et démarre le worker Hatchet."""
    hatchet = get_hatchet()

    # Crée/maj le rate limit statique référencé par la tâche d'embedding.
    try:
        hatchet.rate_limits.put(
            EMBED_RATE_LIMIT_KEY,
            limit=EMBED_RATE_PER_MINUTE,
            duration=RateLimitDuration.MINUTE,
        )
    except Exception as exc:  # pragma: no cover - best effort au démarrage
        logger.warning("hatchet_rate_limit_put_failed", error=str(exc))

    worker = hatchet.worker(
        "geoai-ingestion-worker",
        slots=WORKER_SLOTS,
        workflows=ALL_WORKFLOWS,
        lifespan=lifespan,
    )
    logger.info("hatchet_worker_starting", slots=WORKER_SLOTS)
    worker.start()


if __name__ == "__main__":
    main()
