"""
Legrand GeoAI — Modèle ApiKey.

Clés d'API persistantes pour l'accès programmatique externe.
La clé brute n'est stockée qu'à la création (préfixe + hash SHA-256).
"""

import hashlib
import secrets
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, generate_uuid

# Préfixe visuel pour identifier les clés GeoAI
KEY_PREFIX = "lgai_"


def _hash_key(raw: str) -> str:
    """SHA-256 de la clé brute (jamais stockée en clair)."""
    return hashlib.sha256(raw.encode()).hexdigest()


def generate_api_key() -> tuple[str, str]:
    """
    Génère une nouvelle clé API.

    Returns:
        (raw_key, hashed_key) — stocker seulement le hash.
    """
    raw = KEY_PREFIX + secrets.token_urlsafe(32)
    return raw, _hash_key(raw)


class ApiKey(TimestampMixin, Base):
    """Clé d'API pour accès externe."""

    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_hash: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    key_prefix: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # ex: "lgai_AbCd123456..." — juste pour affichage
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relations
    owner = relationship("User", lazy="selectin")

    def __repr__(self) -> str:
        return f"<ApiKey {self.name} owner={self.owner_id}>"
