"""
Legrand GeoAI — Schémas Collection.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CollectionCreate(BaseModel):
    """Création d'une collection."""

    name: str = Field(min_length=2, max_length=255)
    description: str | None = None


class CollectionUpdate(BaseModel):
    """Mise à jour d'une collection."""

    name: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = None


class CollectionRead(BaseModel):
    """Collection en lecture."""

    id: uuid.UUID
    name: str
    description: str | None = None
    chroma_collection_name: str
    owner_id: uuid.UUID
    document_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
