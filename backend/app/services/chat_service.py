"""
Legrand GeoAI — Service de chat.

Gestion des sessions de chat et des messages en BDD.
"""

import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.chat import ChatMessage, ChatSession, MessageRole
from app.schemas.common import PaginationParams

logger = structlog.get_logger()


async def create_session(
    db: AsyncSession,
    user_id: str,
    title: str = "Nouvelle conversation",
    collection_id: str | None = None,
) -> ChatSession:
    """Crée une nouvelle session de chat."""
    session = ChatSession(
        title=title,
        user_id=user_id,
        collection_id=collection_id,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    logger.info(
        "chat_session_created",
        session_id=session.id,
        user_id=user_id,
        collection_id=collection_id,
    )

    return session


async def get_session(
    db: AsyncSession,
    session_id: str,
    user_id: str | None = None,
) -> ChatSession | None:
    """Récupère une session avec ses messages."""
    q = (
        select(ChatSession)
        .options(selectinload(ChatSession.messages))
        .where(ChatSession.id == session_id)
    )

    if user_id:
        q = q.where(ChatSession.user_id == user_id)

    result = await db.execute(q)
    return result.scalar_one_or_none()


async def list_sessions(
    db: AsyncSession,
    user_id: str,
    pagination: PaginationParams,
) -> tuple[list[ChatSession], int]:
    """Liste les sessions d'un utilisateur."""
    # Total
    count_q = select(func.count(ChatSession.id)).where(
        ChatSession.user_id == user_id
    )
    total = (await db.execute(count_q)).scalar() or 0

    # Sessions
    q = (
        select(ChatSession)
        .where(ChatSession.user_id == user_id)
        .order_by(ChatSession.updated_at.desc())
        .offset(pagination.offset)
        .limit(pagination.size)
    )
    result = await db.execute(q)
    sessions = list(result.scalars().all())

    return sessions, total


async def touch_session(
    db: AsyncSession,
    session_id: str,
) -> None:
    """Met à jour updated_at de la session pour la faire remonter en haut."""
    from datetime import datetime, timezone

    session = await db.get(ChatSession, session_id)
    if session:
        session.updated_at = datetime.now(timezone.utc)
        await db.commit()


async def add_message(
    db: AsyncSession,
    session_id: str,
    role: MessageRole,
    content: str,
    sources: list[dict] | None = None,
    model_name: str | None = None,
    tokens_used: int | None = None,
) -> ChatMessage:
    """Ajoute un message à une session et met à jour le timestamp."""
    message = ChatMessage(
        session_id=session_id,
        role=role,
        content=content,
        sources=sources,
        model_name=model_name,
        tokens_used=tokens_used,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)

    # Update session timestamp so it moves to top
    await touch_session(db, session_id)

    return message


async def update_session_title(
    db: AsyncSession,
    session_id: str,
    title: str,
) -> ChatSession | None:
    """Met à jour le titre d'une session."""
    session = await db.get(ChatSession, session_id)
    if session:
        session.title = title
        await db.commit()
        await db.refresh(session)
    return session


async def delete_session(
    db: AsyncSession,
    session_id: str,
    user_id: str,
) -> bool:
    """Supprime une session et ses messages."""
    session = await db.get(ChatSession, session_id)
    if not session or session.user_id != user_id:
        return False

    await db.delete(session)
    await db.commit()

    logger.info(
        "chat_session_deleted",
        session_id=session_id,
        user_id=user_id,
    )

    return True
