"""
Legrand GeoAI — Modèles Chat.

Session de conversation et messages individuels avec sources RAG.
"""

import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, generate_uuid


class MessageRole(str, enum.Enum):
    """Rôle de l'auteur du message."""

    USER = "user"
    ASSISTANT = "assistant"


class ChatSession(TimestampMixin, Base):
    """Session de conversation."""

    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    collection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("collections.id"), nullable=True
    )

    # Relations
    user = relationship("User", back_populates="chat_sessions", lazy="selectin")
    collection = relationship("Collection", lazy="selectin")
    messages = relationship(
        "ChatMessage",
        back_populates="session",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )

    def __repr__(self) -> str:
        return f"<ChatSession {self.title or 'Sans titre'}>"


class ChatMessage(TimestampMixin, Base):
    """Message individuel dans une session de chat."""

    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chat_sessions.id"), nullable=False, index=True
    )
    role: Mapped[MessageRole] = mapped_column(
        Enum(MessageRole, native_enum=False, length=20), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relations
    session = relationship("ChatSession", back_populates="messages", lazy="selectin")

    def __repr__(self) -> str:
        return f"<ChatMessage {self.role.value}: {self.content[:50]}...>"
