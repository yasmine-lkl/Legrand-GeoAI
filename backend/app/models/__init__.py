"""
Legrand GeoAI — Export de tous les modèles.

Importer depuis app.models donne accès à tous les modèles et à Base
(nécessaire pour Alembic).
"""

from app.models.api_key import ApiKey
from app.models.audit import AuditLog
from app.models.base import Base
from app.models.chat import ChatMessage, ChatSession, MessageRole
from app.models.collection import Collection
from app.models.document import Document, DocumentStatus
from app.models.user import User, UserRole

__all__ = [
    "Base",
    "User",
    "UserRole",
    "Collection",
    "Document",
    "DocumentStatus",
    "ChatSession",
    "ChatMessage",
    "MessageRole",
    "AuditLog",
]
