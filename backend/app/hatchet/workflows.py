"""
Legrand GeoAI — Workflows Hatchet (pipeline documentaire 100% orchestré).

DAG d'ingestion (`document-ingestion`) :

    validate ─► parse ─► vectorize_store ─► finalize
                  │
                  └─ Docling (layout + tables + OCR EasyOCR-fr) → HybridChunker
                     + repli Qwen3-VL (Ollama) sur les pages mal océrisées

Chaque étape possède ses propres retries / timeouts et émet sa progression
(stream temps réel + persistance en base pour reprise / polling).

Fonctionnalités de performance / résilience :
- Extraction structurée Docling (ordre de lecture, tables, titres conservés).
- Limite de concurrence globale sur Ollama (embeddings) et sur le parsing (GPU).
- Rate limit sur les appels d'embedding.
- Idempotence : `vectorize_store` purge les anciens chunks avant ré-insertion,
  donc un retry (ou une ré-indexation) ne duplique rien.
- Crons de maintenance + workflow de ré-indexation de collection.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import structlog
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from hatchet_sdk import (
    ConcurrencyExpression,
    ConcurrencyLimitStrategy,
    Context,
    EmptyModel,
    RateLimit,
    RateLimitDuration,
)

from app.config import settings
from app.hatchet.client import get_hatchet
from app.models.collection import Collection
from app.models.document import Document, DocumentStatus
from app.services.docling_chunking import DoclingChunkingService
from app.services.docling_extraction import DoclingExtractionService
from app.services.embedding_service import EmbeddingService
from app.services.vector_store import VectorStoreService

logger = structlog.get_logger()

# Client Hatchet (construit ici → exige un jeton valide ; importer ce module
# depuis le backend doit donc se faire paresseusement, dans un handler).
hatchet = get_hatchet()

# Clé statique du rate limit d'embedding (créée au démarrage du worker).
EMBED_RATE_LIMIT_KEY = "ollama-embed"

# Délai au-delà duquel un document « processing » est considéré bloqué.
STUCK_AFTER = timedelta(minutes=20)
# Ancienneté au-delà de laquelle un document « failed » est purgé.
FAILED_RETENTION = timedelta(days=7)


# ======================================================================
# Limites de ressources (protection GPU / Ollama)
# ======================================================================

# Au plus N embeddings simultanés vers Ollama, tous documents confondus.
OLLAMA_CONCURRENCY = ConcurrencyExpression(
    expression="'ollama'",
    max_runs=2,
    limit_strategy=ConcurrencyLimitStrategy.GROUP_ROUND_ROBIN,
)

# Au plus N parsings Docling simultanés (layout+OCR+VLM, GPU lourd).
PARSE_CONCURRENCY = ConcurrencyExpression(
    expression="'parse'",
    max_runs=2,
    limit_strategy=ConcurrencyLimitStrategy.GROUP_ROUND_ROBIN,
)


# ======================================================================
# Dépendances partagées du worker (chargées une seule fois — lifespan)
# ======================================================================


@dataclass
class PipelineDeps:
    """Services lourds initialisés au démarrage du worker."""

    session_factory: async_sessionmaker[AsyncSession]
    docling_service: DoclingExtractionService
    docling_chunker: DoclingChunkingService
    embedding_service: EmbeddingService
    vector_store: VectorStoreService


async def lifespan() -> AsyncGenerator[PipelineDeps, None]:
    """Crée les services partagés (Docling/embeddings chargés une fois)."""
    engine = create_async_engine(
        settings.DATABASE_URL,
        pool_size=5,
        max_overflow=5,
        pool_pre_ping=True,
    )
    deps = PipelineDeps(
        session_factory=async_sessionmaker(engine, expire_on_commit=False),
        docling_service=DoclingExtractionService(),
        docling_chunker=DoclingChunkingService(),
        embedding_service=EmbeddingService(),
        vector_store=VectorStoreService(),
    )
    # Pré-charge le converter Docling (modèles) pour éviter le coût au 1er doc.
    try:
        _ = deps.docling_service.converter
    except Exception as e:
        logger.warning("docling_warmup_failed", error=str(e))
    logger.info("hatchet_worker_deps_ready")
    try:
        yield deps
    finally:
        await engine.dispose()


# ======================================================================
# Schémas d'entrée
# ======================================================================


class IngestionInput(BaseModel):
    document_id: str


class ReindexInput(BaseModel):
    collection_id: str


# ======================================================================
# Helpers
# ======================================================================


async def _update_document(
    session_factory: async_sessionmaker[AsyncSession],
    document_id: str,
    **fields: Any,
) -> None:
    """Met à jour quelques colonnes d'un document (statut/progression/...)."""
    async with session_factory() as db:
        doc = await db.get(Document, document_id)
        if doc is None:
            return
        for key, value in fields.items():
            setattr(doc, key, value)
        await db.commit()


async def _emit(ctx: Context, sub_status: str, progress: int) -> None:
    """Pousse un événement de progression sur le stream temps réel."""
    import json

    await ctx.aio_put_stream(
        json.dumps({"sub_status": sub_status, "progress": progress})
    )


# ======================================================================
# Workflow principal : ingestion documentaire (DAG)
# ======================================================================

ingestion = hatchet.workflow(
    name="document-ingestion",
    input_validator=IngestionInput,
    description="Pipeline OCR → chunk → embed → ChromaDB pour un document.",
)


@ingestion.task(retries=1, execution_timeout=timedelta(seconds=60))
async def validate(input: IngestionInput, ctx: Context) -> dict[str, Any]:
    """Charge le document, vérifie le fichier, passe en PROCESSING."""
    deps: PipelineDeps = ctx.lifespan

    async with deps.session_factory() as db:
        doc = await db.get(Document, input.document_id)
        if doc is None:
            raise ValueError(f"Document introuvable : {input.document_id}")
        file_path = settings.upload_path / doc.file_path
        mime_type = doc.mime_type
        doc.status = DocumentStatus.PROCESSING
        doc.sub_status = "validating"
        doc.progress = 5
        doc.error_message = None
        doc.workflow_run_id = ctx.workflow_run_id
        await db.commit()

    if not file_path.exists():
        raise ValueError(f"Fichier absent sur le disque : {file_path}")

    await _emit(ctx, "validating", 5)
    return {"file_path": str(file_path), "mime_type": mime_type}


@ingestion.task(
    parents=[validate],
    execution_timeout=timedelta(minutes=30),
    retries=2,
    concurrency=[PARSE_CONCURRENCY],
)
async def parse(input: IngestionInput, ctx: Context) -> dict[str, Any]:
    """Extraction structurée Docling (+ repli VLM) puis découpage HybridChunker."""
    import asyncio

    deps: PipelineDeps = ctx.lifespan
    parent = ctx.task_output(validate)
    file_path = Path(parent["file_path"])
    mime_type: str = parent.get("mime_type", "")

    await _emit(ctx, "extracting", 25)
    await _update_document(
        deps.session_factory, input.document_id, sub_status="extracting", progress=25
    )

    # 1. Parsing Docling (layout + tables + OCR EasyOCR) — bloquant → thread.
    dl_doc, ocr_method, page_count = await asyncio.to_thread(
        deps.docling_service.parse, file_path, mime_type
    )

    # 2. Repli Qwen3-VL pour les pages mal océrisées (plans denses).
    supplement, used_vlm = await deps.docling_service.vlm_supplement(file_path, dl_doc)
    if used_vlm:
        ocr_method = f"{ocr_method}+qwen3vl"

    # 3. Découpage structuré (HybridChunker), aligné sur le tokenizer BGE-M3.
    await _emit(ctx, "chunking", 60)
    async with deps.session_factory() as db:
        doc = await db.get(Document, input.document_id)
        filename = doc.original_filename if doc else input.document_id

    chunks = await asyncio.to_thread(
        deps.docling_chunker.chunk_document, dl_doc, input.document_id, filename
    )
    if supplement:
        chunks += deps.docling_chunker.chunk_supplement(
            supplement, input.document_id, filename, len(chunks)
        )

    if not chunks:
        raise ValueError("Aucun chunk généré — document vide ou illisible.")

    await _update_document(
        deps.session_factory,
        input.document_id,
        sub_status="chunking",
        progress=60,
        page_count=page_count,
        ocr_method=ocr_method,
        chunk_count=len(chunks),
    )
    return {"chunks": chunks, "chunk_count": len(chunks)}


@ingestion.task(
    parents=[parse],
    execution_timeout=timedelta(minutes=10),
    retries=3,
    backoff_factor=2.0,
    backoff_max_seconds=60,
    concurrency=[OLLAMA_CONCURRENCY],
    rate_limits=[RateLimit(static_key=EMBED_RATE_LIMIT_KEY, units=1)],
)
async def vectorize_store(input: IngestionInput, ctx: Context) -> dict[str, Any]:
    """Génère les embeddings (Ollama) et stocke dans ChromaDB (idempotent)."""
    deps: PipelineDeps = ctx.lifespan
    chunks: list[dict[str, Any]] = ctx.task_output(parse)["chunks"]

    await _emit(ctx, "embedding", 70)
    await _update_document(
        deps.session_factory, input.document_id, sub_status="embedding", progress=70
    )

    # Nom de la collection ChromaDB
    async with deps.session_factory() as db:
        doc = await db.get(Document, input.document_id)
        if doc is None:
            raise ValueError("Document introuvable au stockage vectoriel.")
        collection = await db.get(Collection, doc.collection_id)
        if collection is None:
            raise ValueError("Collection introuvable pour ce document.")
        chroma_collection_name = collection.chroma_collection_name

    chunk_texts = [c["text"] for c in chunks]
    embeddings = await deps.embedding_service.embed_texts(chunk_texts)

    await _emit(ctx, "storing", 90)
    await _update_document(
        deps.session_factory, input.document_id, sub_status="storing", progress=90
    )

    # Métadonnées : ajouter document_id pour des suppressions/ré-index fiables.
    chunk_ids = [c["chunk_id"] for c in chunks]
    metadatas = []
    for c in chunks:
        md = dict(c["metadata"])
        md["document_id"] = input.document_id
        metadatas.append(md)

    # Idempotence : purger d'éventuels chunks existants avant ré-insertion.
    try:
        deps.vector_store.delete_document_chunks(
            collection_name=chroma_collection_name,
            document_id=input.document_id,
        )
    except Exception as exc:  # pragma: no cover - best effort
        logger.warning("vectorize_predelete_failed", error=str(exc))

    stored = deps.vector_store.add_chunks(
        collection_name=chroma_collection_name,
        ids=chunk_ids,
        embeddings=embeddings,
        documents=chunk_texts,
        metadatas=metadatas,
    )
    return {"chunks_stored": stored}


@ingestion.task(parents=[vectorize_store], execution_timeout=timedelta(seconds=30))
async def finalize(input: IngestionInput, ctx: Context) -> dict[str, Any]:
    """Marque le document comme terminé."""
    deps: PipelineDeps = ctx.lifespan
    stored = ctx.task_output(vectorize_store)["chunks_stored"]

    await _update_document(
        deps.session_factory,
        input.document_id,
        status=DocumentStatus.COMPLETED,
        sub_status="completed",
        progress=100,
        error_message=None,
    )
    await _emit(ctx, "completed", 100)
    logger.info(
        "ingestion_completed",
        document_id=input.document_id,
        chunks_stored=stored,
    )
    return {"status": "completed", "chunks_stored": stored}


@ingestion.on_failure_task()
async def on_failure(input: IngestionInput, ctx: Context) -> None:
    """Marque le document en échec avec le message d'erreur."""
    deps: PipelineDeps = ctx.lifespan

    errors = ctx.task_run_errors or {}
    message = " | ".join(str(v) for v in errors.values()) or "Échec de l'ingestion"

    await _update_document(
        deps.session_factory,
        input.document_id,
        status=DocumentStatus.FAILED,
        sub_status="failed",
        error_message=message[:1000],
    )
    logger.error(
        "ingestion_failed",
        document_id=input.document_id,
        error=message[:500],
    )


# ======================================================================
# Workflow : ré-indexation d'une collection (fan-out par document)
# ======================================================================

reindex_collection = hatchet.workflow(
    name="reindex-collection",
    input_validator=ReindexInput,
    description="Relance l'ingestion de tous les documents d'une collection.",
)


@reindex_collection.task(execution_timeout=timedelta(minutes=5))
async def reindex(input: ReindexInput, ctx: Context) -> dict[str, Any]:
    """Réinitialise et relance l'ingestion de chaque document de la collection."""
    deps: PipelineDeps = ctx.lifespan

    async with deps.session_factory() as db:
        rows = await db.execute(
            select(Document.id).where(Document.collection_id == input.collection_id)
        )
        document_ids = [str(r) for r in rows.scalars().all()]

        for doc_id in document_ids:
            doc = await db.get(Document, doc_id)
            if doc:
                doc.status = DocumentStatus.PENDING
                doc.sub_status = None
                doc.progress = 0
                doc.error_message = None
        await db.commit()

    for doc_id in document_ids:
        await ingestion.aio_run_no_wait(IngestionInput(document_id=doc_id))

    await ctx.aio_log(f"Ré-indexation lancée pour {len(document_ids)} documents")
    return {"reindexed": len(document_ids), "document_ids": document_ids}


# ======================================================================
# Crons de maintenance
# ======================================================================


@hatchet.task(name="maintenance-retry-stuck", on_crons=["*/15 * * * *"])
async def retry_stuck(input: EmptyModel, ctx: Context) -> dict[str, Any]:
    """Relance les documents bloqués en PROCESSING depuis trop longtemps."""
    deps: PipelineDeps = ctx.lifespan
    cutoff = datetime.now(timezone.utc) - STUCK_AFTER

    async with deps.session_factory() as db:
        rows = await db.execute(
            select(Document.id).where(
                Document.status == DocumentStatus.PROCESSING,
                Document.updated_at < cutoff,
            )
        )
        stuck_ids = [str(r) for r in rows.scalars().all()]

    for doc_id in stuck_ids:
        await ingestion.aio_run_no_wait(IngestionInput(document_id=doc_id))

    if stuck_ids:
        logger.info("maintenance_retry_stuck", count=len(stuck_ids))
    return {"requeued": len(stuck_ids)}


@hatchet.task(name="maintenance-cleanup-orphans", on_crons=["0 3 * * *"])
async def cleanup_orphans(input: EmptyModel, ctx: Context) -> dict[str, Any]:
    """Purge les documents en échec trop anciens (fichier + chunks + BDD)."""
    from app.services.document_storage import DocumentStorageService

    deps: PipelineDeps = ctx.lifespan
    storage = DocumentStorageService()
    cutoff = datetime.now(timezone.utc) - FAILED_RETENTION
    purged = 0

    async with deps.session_factory() as db:
        rows = await db.execute(
            select(Document)
            .where(
                Document.status == DocumentStatus.FAILED,
                Document.updated_at < cutoff,
            )
        )
        docs = rows.scalars().all()

        for doc in docs:
            collection = await db.get(Collection, doc.collection_id)
            if collection:
                try:
                    deps.vector_store.delete_document_chunks(
                        collection_name=collection.chroma_collection_name,
                        document_id=str(doc.id),
                    )
                except Exception as exc:  # pragma: no cover
                    logger.warning("cleanup_chunks_failed", error=str(exc))
            try:
                await storage.delete(doc.file_path)
            except Exception as exc:  # pragma: no cover
                logger.warning("cleanup_file_failed", error=str(exc))
            await db.delete(doc)
            purged += 1
        await db.commit()

    if purged:
        logger.info("maintenance_cleanup_orphans", purged=purged)
    return {"purged": purged}


# Liste des workflows enregistrés par le worker.
ALL_WORKFLOWS = [
    ingestion,
    reindex_collection,
    retry_stuck,
    cleanup_orphans,
]
