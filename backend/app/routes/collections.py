"""
Legrand GeoAI — Routes de gestion des collections.

CRUD pour les collections de documents (une collection = un projet / thématique).
Chaque collection possède sa propre collection ChromaDB.
"""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_current_user
from app.models.collection import Collection
from app.models.document import Document
from app.models.user import User, UserRole
from app.schemas.collection import CollectionCreate, CollectionRead, CollectionUpdate
from app.schemas.common import MessageResponse, PaginatedResponse, PaginationParams
from app.security.rbac import require_admin, require_user
from app.services.audit_service import log_action
from app.services.vector_store import VectorStoreService

logger = structlog.get_logger()
router = APIRouter(prefix="/api/collections", tags=["collections"])

# Service ChromaDB partagé
_vector_store = VectorStoreService()


def _sanitize_collection_name(name: str) -> str:
    """Génère un nom ChromaDB valide à partir du nom utilisateur."""
    import re
    import unicodedata

    # Supprimer les accents
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_name = nfkd.encode("ascii", "ignore").decode("ascii")
    # Garder uniquement alphanum et underscore
    sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", ascii_name).strip("_").lower()
    # ChromaDB exige entre 3 et 63 caractères
    sanitized = sanitized[:60] or "collection"
    if len(sanitized) < 3:
        sanitized = sanitized + "_col"
    return f"col_{sanitized}"


# ------------------------------------------------------------------
# LIST
# ------------------------------------------------------------------


@router.get("", response_model=PaginatedResponse[CollectionRead])
async def list_collections(
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Liste toutes les collections avec le nombre de documents."""
    # Total
    count_q = select(func.count(Collection.id))
    total = (await db.execute(count_q)).scalar() or 0

    # Collections avec jointure owner + count documents
    q = (
        select(Collection)
        .options(selectinload(Collection.owner))
        .order_by(Collection.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.size)
    )
    result = await db.execute(q)
    collections = result.scalars().all()

    # Comptage documents par collection
    items = []
    for col in collections:
        doc_count_q = select(func.count(Document.id)).where(
            Document.collection_id == col.id
        )
        doc_count = (await db.execute(doc_count_q)).scalar() or 0

        items.append(
            CollectionRead(
                id=col.id,
                name=col.name,
                description=col.description,
                chroma_collection_name=col.chroma_collection_name,
                owner_id=col.owner_id,
                created_at=col.created_at,
                updated_at=col.updated_at,
                document_count=doc_count,
            )
        )

    return PaginatedResponse.create(items=items, total=total, params=pagination)


# ------------------------------------------------------------------
# GET ONE
# ------------------------------------------------------------------


@router.get("/{collection_id}", response_model=CollectionRead)
async def get_collection(
    collection_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Récupère une collection par son ID."""
    collection = await db.get(Collection, str(collection_id))
    if not collection:
        raise HTTPException(status_code=404, detail="Collection introuvable")

    doc_count_q = select(func.count(Document.id)).where(
        Document.collection_id == collection.id
    )
    doc_count = (await db.execute(doc_count_q)).scalar() or 0

    return CollectionRead(
        id=collection.id,
        name=collection.name,
        description=collection.description,
        chroma_collection_name=collection.chroma_collection_name,
        owner_id=collection.owner_id,
        created_at=collection.created_at,
        updated_at=collection.updated_at,
        document_count=doc_count,
    )


# ------------------------------------------------------------------
# CREATE
# ------------------------------------------------------------------


@router.post("", response_model=CollectionRead, status_code=status.HTTP_201_CREATED)
async def create_collection(
    data: CollectionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Crée une nouvelle collection (+ collection ChromaDB associée)."""
    require_user(current_user)
    # Vérifier unicité du nom
    existing = await db.execute(
        select(Collection).where(Collection.name == data.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Une collection avec ce nom existe déjà",
        )

    # Générer le nom ChromaDB
    chroma_name = _sanitize_collection_name(data.name)

    # Vérifier unicité chroma_name
    existing_chroma = await db.execute(
        select(Collection).where(Collection.chroma_collection_name == chroma_name)
    )
    if existing_chroma.scalar_one_or_none():
        import uuid as uuid_mod
        chroma_name = f"{chroma_name}_{uuid_mod.uuid4().hex[:6]}"

    collection = Collection(
        name=data.name,
        description=data.description,
        chroma_collection_name=chroma_name,
        owner_id=current_user.id,
    )
    db.add(collection)
    await db.commit()
    await db.refresh(collection)

    # Créer la collection dans ChromaDB
    _vector_store.get_or_create_collection(chroma_name)

    await log_action(
        db=db,
        user_id=current_user.id,
        action="collection_created",
        resource_type="collection",
        resource_id=collection.id,
        details={"name": data.name, "chroma_name": chroma_name},
    )

    logger.info(
        "collection_created",
        collection_id=collection.id,
        name=data.name,
        chroma_name=chroma_name,
    )

    return CollectionRead(
        id=collection.id,
        name=collection.name,
        description=collection.description,
        chroma_collection_name=collection.chroma_collection_name,
        owner_id=collection.owner_id,
        created_at=collection.created_at,
        updated_at=collection.updated_at,
        document_count=0,
    )


# ------------------------------------------------------------------
# UPDATE
# ------------------------------------------------------------------


@router.patch("/{collection_id}", response_model=CollectionRead)
async def update_collection(
    collection_id: UUID,
    data: CollectionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Met à jour une collection (nom, description)."""
    require_user(current_user)
    collection = await db.get(Collection, str(collection_id))
    if not collection:
        raise HTTPException(status_code=404, detail="Collection introuvable")

    # Seul le propriétaire ou un admin peut modifier
    if (
        current_user.role != UserRole.ADMIN
        and collection.owner_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé",
        )

    # Mise à jour des champs
    if data.name is not None:
        # Vérifier unicité
        existing = await db.execute(
            select(Collection).where(
                Collection.name == data.name, Collection.id != str(collection_id)
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Une collection avec ce nom existe déjà",
            )
        collection.name = data.name

    if data.description is not None:
        collection.description = data.description

    await db.commit()
    await db.refresh(collection)

    doc_count_q = select(func.count(Document.id)).where(
        Document.collection_id == collection.id
    )
    doc_count = (await db.execute(doc_count_q)).scalar() or 0

    await log_action(
        db=db,
        user_id=current_user.id,
        action="collection_updated",
        resource_type="collection",
        resource_id=collection.id,
    )

    return CollectionRead(
        id=collection.id,
        name=collection.name,
        description=collection.description,
        chroma_collection_name=collection.chroma_collection_name,
        owner_id=collection.owner_id,
        created_at=collection.created_at,
        updated_at=collection.updated_at,
        document_count=doc_count,
    )


# ------------------------------------------------------------------
# DELETE
# ------------------------------------------------------------------


@router.delete("/{collection_id}", response_model=MessageResponse)
async def delete_collection(
    collection_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Supprime une collection (admin uniquement).

    Supprime aussi :
    - Tous les documents associés en BDD
    - La collection ChromaDB
    """
    require_admin(current_user)
    collection = await db.get(Collection, str(collection_id))
    if not collection:
        raise HTTPException(status_code=404, detail="Collection introuvable")

    chroma_name = collection.chroma_collection_name
    col_name = collection.name

    # Supprimer la collection ChromaDB
    try:
        _vector_store.delete_collection(chroma_name)
    except Exception as e:
        logger.warning(
            "chromadb_delete_failed",
            collection=chroma_name,
            error=str(e),
        )

    # Supprimer en BDD (cascade supprime les documents)
    await db.delete(collection)
    await db.commit()

    await log_action(
        db=db,
        user_id=current_user.id,
        action="collection_deleted",
        resource_type="collection",
        resource_id=str(collection_id),
        details={"name": col_name},
    )

    logger.info(
        "collection_deleted",
        collection_id=str(collection_id),
        name=col_name,
    )

    return MessageResponse(message=f"Collection '{col_name}' supprimée avec succès")


# ------------------------------------------------------------------
# REINDEX (ré-indexation complète — admin)
# ------------------------------------------------------------------


@router.post("/{collection_id}/reindex", response_model=MessageResponse)
async def reindex_collection_endpoint(
    collection_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Relance l'ingestion de TOUS les documents de la collection (admin).

    Utile après un changement de modèle d'embeddings ou de stratégie de
    chunking. Le workflow Hatchet « reindex-collection » remet les documents
    en attente puis ré-déclenche l'ingestion en parallèle.
    """
    require_admin(current_user)
    collection = await db.get(Collection, str(collection_id))
    if not collection:
        raise HTTPException(status_code=404, detail="Collection introuvable")

    try:
        from app.hatchet.workflows import ReindexInput
        from app.hatchet.workflows import reindex_collection as reindex_wf

        await reindex_wf.aio_run_no_wait(
            ReindexInput(collection_id=str(collection_id))
        )
    except Exception as e:
        logger.error(
            "reindex_trigger_failed",
            collection_id=str(collection_id),
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service de ré-indexation indisponible",
        )

    await log_action(
        db=db,
        user_id=current_user.id,
        action="collection_reindexed",
        resource_type="collection",
        resource_id=str(collection_id),
        details={"name": collection.name},
    )

    return MessageResponse(
        message=f"Ré-indexation de '{collection.name}' lancée"
    )
