"""
Legrand GeoAI — Schémas Chat.
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ChatQueryRequest(BaseModel):
    """Requête de chat RAG."""

    message: str = Field(min_length=1, max_length=5000)
    collection_id: uuid.UUID
    session_id: uuid.UUID | None = None


class SourceInfo(BaseModel):
    """Information sur une source citée."""

    document_id: str = ""
    filename: str = ""
    chunk_index: int = 0
    page_numbers: list[int] = []
    score: float = 0.0


class ChatMessageRead(BaseModel):
    """Message de chat en lecture."""

    id: uuid.UUID
    role: str
    content: str
    sources: list[SourceInfo] | None = None
    model_name: str | None = None
    tokens_used: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatSessionRead(BaseModel):
    """Session de chat en lecture."""

    id: uuid.UUID
    title: str | None = None
    collection_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChatSessionDetailRead(ChatSessionRead):
    """Session de chat détaillée avec messages."""

    messages: list[ChatMessageRead] = []


class StreamChunk(BaseModel):
    """Chunk SSE envoyé au client."""

    type: Literal["token", "sources", "done", "error"]
    data: str | list[SourceInfo] | None = None
