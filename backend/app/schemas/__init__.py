"""
Legrand GeoAI — Export de tous les schémas.
"""

from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse
from app.schemas.chat import (
    ChatMessageRead,
    ChatQueryRequest,
    ChatSessionDetailRead,
    ChatSessionRead,
    SourceInfo,
    StreamChunk,
)
from app.schemas.collection import CollectionCreate, CollectionRead, CollectionUpdate
from app.schemas.common import ErrorResponse, MessageResponse, PaginatedResponse, PaginationParams
from app.schemas.document import DocumentRead, DocumentUploadResponse
from app.schemas.user import UserCreate, UserRead, UserUpdate

__all__ = [
    "LoginRequest",
    "RefreshRequest",
    "RegisterRequest",
    "TokenResponse",
    "UserCreate",
    "UserRead",
    "UserUpdate",
    "DocumentRead",
    "DocumentUploadResponse",
    "CollectionCreate",
    "CollectionRead",
    "CollectionUpdate",
    "ChatQueryRequest",
    "ChatMessageRead",
    "ChatSessionRead",
    "ChatSessionDetailRead",
    "SourceInfo",
    "StreamChunk",
    "PaginationParams",
    "PaginatedResponse",
    "MessageResponse",
    "ErrorResponse",
]
