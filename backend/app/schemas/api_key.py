"""
Legrand GeoAI — Schémas Pydantic pour les clés d'API.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Nom de la clé")
    description: str | None = Field(None, description="Usage prévu")


class ApiKeyRead(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    key_prefix: str
    is_active: bool
    last_used_at: datetime | None
    expires_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApiKeyCreated(ApiKeyRead):
    """Retourné UNE SEULE FOIS à la création — contient la clé brute."""
    raw_key: str = Field(..., description="Clé brute — copiez-la maintenant, elle ne sera plus affichée")
