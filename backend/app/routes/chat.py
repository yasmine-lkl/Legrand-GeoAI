"""
Legrand GeoAI — Routes de chat RAG.

Endpoint principal avec streaming SSE pour les réponses en temps réel.
"""

import asyncio
import json

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.chat import MessageRole
from app.models.collection import Collection
from app.models.user import User
from app.schemas.chat import (
    ChatMessageRead,
    ChatQueryRequest,
    ChatSessionDetailRead,
    ChatSessionRead,
    StreamChunk,
)
from app.schemas.common import MessageResponse, PaginatedResponse, PaginationParams
from app.services import chat_service
from app.services.audit_service import log_action
from app.services.rag_service import RAGService

logger = structlog.get_logger()
router = APIRouter(prefix="/api/chat", tags=["chat"])

# Service RAG partagé
_rag = RAGService()


# ------------------------------------------------------------------
# Sessions
# ------------------------------------------------------------------


@router.get("/sessions", response_model=PaginatedResponse[ChatSessionRead])
async def list_sessions(
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Liste les sessions de chat de l'utilisateur."""
    sessions, total = await chat_service.list_sessions(
        db=db,
        user_id=current_user.id,
        pagination=pagination,
    )

    items = [
        ChatSessionRead(
            id=s.id,
            title=s.title,
            collection_id=s.collection_id,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in sessions
    ]

    return PaginatedResponse.create(items=items, total=total, params=pagination)


@router.get("/sessions/{session_id}", response_model=ChatSessionDetailRead)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Récupère une session avec tous ses messages."""
    session = await chat_service.get_session(
        db=db,
        session_id=session_id,
        user_id=current_user.id,
    )

    if not session:
        raise HTTPException(status_code=404, detail="Session introuvable")

    messages = [
        ChatMessageRead(
            id=m.id,
            role=m.role.value,
            content=m.content,
            sources=m.sources,
            model_name=m.model_name,
            tokens_used=m.tokens_used,
            created_at=m.created_at,
        )
        for m in session.messages
    ]

    return ChatSessionDetailRead(
        id=session.id,
        title=session.title,
        collection_id=session.collection_id,
        created_at=session.created_at,
        updated_at=session.updated_at,
        messages=messages,
    )


@router.delete("/sessions/{session_id}", response_model=MessageResponse)
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Supprime une session de chat."""
    deleted = await chat_service.delete_session(
        db=db,
        session_id=session_id,
        user_id=current_user.id,
    )

    if not deleted:
        raise HTTPException(status_code=404, detail="Session introuvable")

    return MessageResponse(message="Session supprimée")


# ------------------------------------------------------------------
# Query (RAG)
# ------------------------------------------------------------------


@router.post("/query")
async def query_rag(
    data: ChatQueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Envoie une question au RAG et reçoit la réponse en streaming SSE.

    Le client reçoit des événements Server-Sent Events :
    - event: sources  → data: {"sources": [...]}
    - event: token    → data: {"content": "..."}
    - event: done     → data: {"tokens_used": N}
    - event: error    → data: {"detail": "..."}
    """
    # Vérifier la collection
    collection = await db.get(Collection, data.collection_id)
    if not collection:
        raise HTTPException(status_code=404, detail="Collection introuvable")

    # Créer ou récupérer la session
    if data.session_id:
        session = await chat_service.get_session(
            db=db,
            session_id=data.session_id,
            user_id=current_user.id,
        )
        if not session:
            raise HTTPException(status_code=404, detail="Session introuvable")
    else:
        # Créer une nouvelle session avec le début de la question comme titre
        title = data.message[:80].strip() + ("..." if len(data.message) > 80 else "")
        session = await chat_service.create_session(
            db=db,
            user_id=current_user.id,
            title=title,
            collection_id=data.collection_id,
        )

    # Sauvegarder le message utilisateur
    await chat_service.add_message(
        db=db,
        session_id=session.id,
        role=MessageRole.USER,
        content=data.message,
    )

    # Mettre à jour le timestamp pour que la session remonte en haut de la liste
    await chat_service.touch_session(db=db, session_id=str(session.id))

    async def sse_generator():
        """Générateur SSE."""
        full_answer = ""
        sources = []
        tokens_used = 0

        try:
            # On consomme le flux RAG en l'entrecoupant de battements (commentaires
            # SSE « : ... ») toutes les ~5 s : les étapes longues (reranking CPU,
            # chargement du modèle) peuvent retarder le 1er token de plusieurs
            # secondes, et un proxy/navigateur fermerait une connexion restée
            # inactive. Le battement garde la connexion vivante.
            agen = _rag.query_stream(
                question=data.message,
                collection_name=collection.chroma_collection_name,
            ).__aiter__()
            # asyncio.wait (et non wait_for) : sur expiration, la tâche n'est PAS
            # annulée — l'étape RAG continue, on émet juste un battement.
            pending = asyncio.ensure_future(agen.__anext__())
            while True:
                done, _ = await asyncio.wait({pending}, timeout=5.0)
                if not done:
                    yield ": keepalive\n\n"
                    continue
                try:
                    chunk = pending.result()
                except StopAsyncIteration:
                    break
                pending = asyncio.ensure_future(agen.__anext__())

                if chunk["type"] == "sources":
                    sources = chunk["sources"]
                    yield f"event: sources\ndata: {json.dumps({'sources': sources}, ensure_ascii=False)}\n\n"

                elif chunk["type"] == "token":
                    full_answer += chunk["content"]
                    yield f"event: token\ndata: {json.dumps({'content': chunk['content']}, ensure_ascii=False)}\n\n"

                elif chunk["type"] == "done":
                    tokens_used = chunk.get("tokens_used", 0)
                    yield f"event: done\ndata: {json.dumps({'tokens_used': tokens_used, 'session_id': str(session.id)}, ensure_ascii=False)}\n\n"

        except Exception as e:
            logger.error(
                "rag_stream_error",
                error=str(e),
                session_id=session.id,
                exc_info=True,
            )
            yield f"event: error\ndata: {json.dumps({'detail': 'Erreur lors de la génération'}, ensure_ascii=False)}\n\n"

        # Sauvegarder la réponse de l'assistant en BDD
        if full_answer:
            try:
                await chat_service.add_message(
                    db=db,
                    session_id=session.id,
                    role=MessageRole.ASSISTANT,
                    content=full_answer,
                    sources=sources,
                    model_name=_rag.llm.model,
                    tokens_used=tokens_used,
                )
            except Exception as e:
                logger.error(
                    "chat_message_save_failed",
                    error=str(e),
                    session_id=session.id,
                )

        # Audit log
        await log_action(
            db=db,
            user_id=current_user.id,
            action="chat_query",
            resource_type="chat_session",
            resource_id=session.id,
            details={
                "question_length": len(data.message),
                "answer_length": len(full_answer),
                "sources_count": len(sources),
                "collection": collection.name,
            },
        )

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
