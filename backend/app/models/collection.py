"""
Legrand GeoAI — Modèle Collection.

Organise les documents en groupes logiques, chaque collection
correspond à une collection ChromaDB pour les vecteurs.
"""

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, generate_uuid


class Collection(TimestampMixin, Base):
    """Collection de documents."""

    __tablename__ = "collections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    chroma_collection_name: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # Relations
    owner = relationship("User", backref="collections", lazy="selectin")
    documents = relationship(
        "Document", back_populates="collection", lazy="selectin", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Collection {self.name}>"
