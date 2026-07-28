"""
Legrand GeoAI — Modèle User.

Rôles : admin (gestion totale), user (upload + chat), viewer (chat seul).
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, generate_uuid


class UserRole(str, enum.Enum):
    """Rôles utilisateur."""

    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"


class User(TimestampMixin, Base):
    """Utilisateur de l'application."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, native_enum=False, length=20),
        default=UserRole.USER,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relations
    documents = relationship("Document", back_populates="uploader", lazy="selectin")
    chat_sessions = relationship("ChatSession", back_populates="user", lazy="selectin")
    audit_logs = relationship("AuditLog", back_populates="user", lazy="noload")

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role.value})>"
