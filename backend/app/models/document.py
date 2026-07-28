"""
Legrand GeoAI — Modèle Document.

Représente un fichier uploadé (PDF, image) avec son statut
de traitement OCR/indexation.
"""

import enum
import uuid

from sqlalchemy import BigInteger, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, generate_uuid


class DocumentStatus(str, enum.Enum):
    """Statut du pipeline d'ingestion."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Document(TimestampMixin, Base):
    """Document uploadé et indexé."""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)

    # Statut pipeline
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, native_enum=False, length=20),
        default=DocumentStatus.PENDING,
        nullable=False,
        index=True,
    )
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ocr_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Suivi fin de l'ingestion (orchestration Hatchet)
    sub_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    progress: Mapped[int | None] = mapped_column(Integer, nullable=True)
    workflow_run_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )

    # Relations
    collection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("collections.id"), nullable=False, index=True
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    collection = relationship("Collection", back_populates="documents", lazy="selectin")
    uploader = relationship("User", back_populates="documents", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Document {self.original_filename} ({self.status.value})>"
