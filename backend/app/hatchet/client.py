"""
Legrand GeoAI — Client Hatchet partagé.

Le SDK Hatchet lit sa configuration depuis les variables d'environnement
`HATCHET_CLIENT_*`. En déploiement Docker, `env_file: .env` les fournit
directement ; en développement local, on les propage depuis la config Pydantic
(qui charge le .env racine) vers `os.environ`.

Le client est construit **paresseusement** : la construction échoue tant qu'un
jeton (JWT) valide n'est pas configuré. On évite donc d'importer le client au
chargement des modules non liés à Hatchet (le backend continue de démarrer même
avant la génération du jeton ; seules les routes d'ingestion échouent alors
proprement). Le worker, lui, exige un jeton valide — ce qui est attendu.
"""

import os
from functools import lru_cache
from typing import TYPE_CHECKING

from app.config import settings

if TYPE_CHECKING:
    from hatchet_sdk import Hatchet


def _prepare_env() -> None:
    """Propage la config vers l'environnement attendu par le SDK Hatchet."""
    if settings.HATCHET_CLIENT_TOKEN:
        os.environ.setdefault("HATCHET_CLIENT_TOKEN", settings.HATCHET_CLIENT_TOKEN)
    os.environ.setdefault("HATCHET_CLIENT_HOST_PORT", settings.HATCHET_CLIENT_HOST_PORT)
    os.environ.setdefault(
        "HATCHET_CLIENT_TLS_STRATEGY", settings.HATCHET_CLIENT_TLS_STRATEGY
    )


@lru_cache(maxsize=1)
def get_hatchet() -> "Hatchet":
    """Construit (une seule fois) le client Hatchet.

    Lève une erreur claire si le jeton n'est pas configuré.
    """
    _prepare_env()
    from hatchet_sdk import Hatchet

    return Hatchet()
