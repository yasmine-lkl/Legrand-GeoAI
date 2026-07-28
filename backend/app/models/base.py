"""
Legrand GeoAI — Base SQLAlchemy + mixins.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Classe de base pour tous les modèles SQLAlchemy."""

    pass


class TimestampMixin:
    """Mixin ajoutant created_at et updated_at automatiques."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


def generate_uuid() -> uuid.UUID:
    """Génère un UUID v4."""
    return uuid.uuid4()
