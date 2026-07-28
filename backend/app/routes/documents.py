"""
Legrand GeoAI — Routes de gestion des documents.

Upload, liste, statut, suppression.
L'upload déclenche le workflow Hatchet « document-ingestion »
(validate → OCR → chunk → embed → ChromaDB → finalize) et expose
sa progression en temps réel via SSE.
"""

import json
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_current_user
from app.models.collection import Collection
from app.models.document import Document, DocumentStatus
from app.models.user import User, UserRole
from app.schemas.common import MessageResponse, PaginatedResponse, PaginationParams
from app.schemas.document import DocumentRead, DocumentUploadResponse
from app.security.rbac import require_user
from app.services.audit_service import log_action
from app.services.document_storage import DocumentStorageService

logger = structlog.get_logger()
router = APIRouter(prefix="/api/documents", tags=["documents"])

_storage = DocumentStorageService()


# ------------------------------------------------------------------
# UPLOAD
# ------------------------------------------------------------------


@router.post("", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    collection_id: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload un document et lance l'ingestion en arrière-plan.

    Accepte : PDF, PNG, JPEG, TIFF, BMP, WEBP.
    """
    require_user(current_user)
    # Vérifier que la collection existe
    collection = await db.get(Collection, collection_id)
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collection introuvable",
        )

    # Sauvegarder le fichier sur disque
    try:
        file_info = await _storage.save(
            file=file,
            collection_id=collection_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Créer l'entrée en BDD
    document = Document(
        filename=file_info["filename"],
        original_filename=file_info["original_filename"],
        mime_type=file_info["mime_type"],
        file_size=file_info["file_size"],
        file_path=file_info["file_path"],
        status=DocumentStatus.PENDING,
        collection_id=collection_id,
        uploaded_by=current_user.id,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    # Déclenche le workflow d'ingestion Hatchet (import paresseux : le backend
    # démarre même sans jeton, seule cette route échoue alors proprement).
    try:
        from app.hatchet.workflows import IngestionInput, ingestion

        ref = await ingestion.aio_run_no_wait(
            IngestionInput(document_id=str(document.id))
        )
        document.workflow_run_id = ref.workflow_run_id
        await db.commit()
        logger.info(
            "ingestion_workflow_triggered",
            document_id=document.id,
            workflow_run_id=ref.workflow_run_id,
        )
    except Exception as e:
        logger.error(
            "ingestion_trigger_failed",
            document_id=document.id,
            error=str(e),
        )

    await log_action(
        db=db,
        user_id=current_user.id,
        action="document_uploaded",
        resource_type="document",
        resource_id=document.id,
        details={
            "filename": document.original_filename,
            "mime_type": document.mime_type,
            "file_size": document.file_size,
            "collection_id": collection_id,
        },
    )

    return DocumentUploadResponse(
        id=document.id,
        filename=document.original_filename,
        status=document.status.value,
        message="Document uploadé — ingestion en cours",
    )


# ------------------------------------------------------------------
# LIST
# ------------------------------------------------------------------


@router.get("", response_model=PaginatedResponse[DocumentRead])
async def list_documents(
    pagination: PaginationParams = Depends(),
    collection_id: str | None = None,
    status_filter: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Liste les documents avec filtres optionnels."""
    base_q = select(Document).options(
        selectinload(Document.collection),
        selectinload(Document.uploader),
    )

    if collection_id:
        base_q = base_q.where(Document.collection_id == collection_id)

    if status_filter:
        try:
            doc_status = DocumentStatus(status_filter)
            base_q = base_q.where(Document.status == doc_status)
        except ValueError:
            pass

    # Total
    count_q = select(func.count()).select_from(base_q.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Paginated
    q = base_q.order_by(Document.created_at.desc()).offset(pagination.offset).limit(pagination.size)
    result = await db.execute(q)
    documents = result.scalars().all()

    items = [
        DocumentRead(
            id=doc.id,
            filename=doc.filename,
            original_filename=doc.original_filename,
            mime_type=doc.mime_type,
            file_size=doc.file_size,
            status=doc.status.value,
            page_count=doc.page_count,
            chunk_count=doc.chunk_count,
            ocr_method=doc.ocr_method,
            error_message=doc.error_message,
            collection_id=doc.collection_id,
            collection_name=doc.collection.name if doc.collection else None,
            uploaded_by=doc.uploaded_by,
            uploader_name=doc.uploader.full_name if doc.uploader else None,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )
        for doc in documents
    ]

    return PaginatedResponse.create(items=items, total=total, params=pagination)


# ------------------------------------------------------------------
# GET ONE
# ------------------------------------------------------------------


@router.get("/{document_id}", response_model=DocumentRead)
async def get_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Récupère les détails d'un document."""
    result = await db.execute(
        select(Document)
        .options(
            selectinload(Document.collection),
            selectinload(Document.uploader),
        )
        .where(Document.id == str(document_id))
    )
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=404, detail="Document introuvable")

    return DocumentRead(
        id=doc.id,
        filename=doc.filename,
        original_filename=doc.original_filename,
        mime_type=doc.mime_type,
        file_size=doc.file_size,
        status=doc.status.value,
        page_count=doc.page_count,
        chunk_count=doc.chunk_count,
        ocr_method=doc.ocr_method,
        error_message=doc.error_message,
        collection_id=doc.collection_id,
        collection_name=doc.collection.name if doc.collection else None,
        uploaded_by=doc.uploaded_by,
        uploader_name=doc.uploader.full_name if doc.uploader else None,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


# ------------------------------------------------------------------
# PROGRESS (SSE temps réel)
# ------------------------------------------------------------------


def _progress_snapshot(doc: Document) -> dict:
    """État courant d'ingestion d'un document (pour le stream)."""
    return {
        "status": doc.status.value,
        "sub_status": doc.sub_status,
        "progress": doc.progress,
        "page_count": doc.page_count,
        "chunk_count": doc.chunk_count,
        "ocr_method": doc.ocr_method,
        "error_message": doc.error_message,
    }


@router.get("/{document_id}/progress")
async def document_progress(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Progression d'ingestion en temps réel (Server-Sent Events).

    Événements :
    - event: snapshot → état courant en base
    - event: progress → étape live émise par le workflow Hatchet
    - event: done     → état final (à la fin du workflow)
    - event: error    → erreur de stream
    """
    doc = await db.get(Document, str(document_id))
    if not doc:
        raise HTTPException(status_code=404, detail="Document introuvable")

    run_id = doc.workflow_run_id
    initial = _progress_snapshot(doc)
    terminal = doc.status in (DocumentStatus.COMPLETED, DocumentStatus.FAILED)

    async def sse_generator():
        # 1. Snapshot initial
        yield f"event: snapshot\ndata: {json.dumps(initial, ensure_ascii=False)}\n\n"

        # 2. Si déjà terminé (ou aucun run rattaché), on clôt immédiatement.
        if terminal or not run_id:
            yield f"event: done\ndata: {json.dumps(initial, ensure_ascii=False)}\n\n"
            return

        # 3. Stream live depuis Hatchet
        try:
            from app.hatchet.client import get_hatchet

            hatchet = get_hatchet()
            async for chunk in hatchet.runs.subscribe_to_stream(run_id):
                yield f"event: progress\ndata: {chunk}\n\n"
        except Exception as e:
            logger.warning(
                "document_progress_stream_error",
                document_id=str(document_id),
                error=str(e),
            )
            yield f"event: error\ndata: {json.dumps({'detail': 'stream indisponible'}, ensure_ascii=False)}\n\n"

        # 4. Snapshot final (session fraîche : le stream a pu durer longtemps)
        from app.database import AsyncSessionLocal

        async with AsyncSessionLocal() as fresh_db:
            final_doc = await fresh_db.get(Document, str(document_id))
            final = _progress_snapshot(final_doc) if final_doc else initial
        yield f"event: done\ndata: {json.dumps(final, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ------------------------------------------------------------------
# DELETE
# ------------------------------------------------------------------


@router.delete("/{document_id}", response_model=MessageResponse)
async def delete_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Supprime un document.

    Supprime aussi :
    - Le fichier sur disque
    - Les chunks dans ChromaDB
    """
    require_user(current_user)
    result = await db.execute(
        select(Document)
        .options(selectinload(Document.collection))
        .where(Document.id == str(document_id))
    )
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=404, detail="Document introuvable")

    # Vérifier les permissions (propriétaire ou admin)
    if (
        current_user.role != UserRole.ADMIN
        and doc.uploaded_by != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé",
        )

    filename = doc.original_filename

    # Supprimer les chunks ChromaDB.
    # On purge TOUJOURS (suppression par doc_id, sans effet s'il n'y en a pas) :
    # se limiter au statut COMPLETED laissait des vecteurs orphelins lorsqu'un
    # document était supprimé en cours d'ingestion ou après un échec.
    if doc.collection:
        try:
            from app.services.vector_store import VectorStoreService

            vs = VectorStoreService()
            vs.delete_document_chunks(
                collection_name=doc.collection.chroma_collection_name,
                document_id=doc.id,
            )
        except Exception as e:
            logger.warning(
                "chromadb_chunk_delete_failed",
                document_id=doc.id,
                error=str(e),
            )

    # Supprimer le fichier sur disque
    try:
        await _storage.delete(doc.file_path)
    except Exception as e:
        logger.warning(
            "file_delete_failed",
            file_path=doc.file_path,
            error=str(e),
        )

    # Supprimer en BDD
    await db.delete(doc)
    await db.commit()

    await log_action(
        db=db,
        user_id=current_user.id,
        action="document_deleted",
        resource_type="document",
        resource_id=str(document_id),
        details={"filename": filename},
    )

    logger.info(
        "document_deleted",
        document_id=str(document_id),
        filename=filename,
    )

    return MessageResponse(message=f"Document '{filename}' supprimé avec succès")
