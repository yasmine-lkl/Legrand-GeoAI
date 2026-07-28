"""
Legrand GeoAI — Routes de gestion des clés d'API.

Réservé aux administrateurs pour créer/révoquer les clés.
Les clés permettent l'accès programmatique externe via X-Api-Key.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.api_key import ApiKey, generate_api_key
from app.models.user import User
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreated, ApiKeyRead
from app.schemas.common import MessageResponse
from app.security.rbac import require_admin

router = APIRouter(prefix="/api/api-keys", tags=["API Keys"])
logger = structlog.get_logger()


@router.get("", response_model=list[ApiKeyRead])
async def list_api_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Liste toutes les clés d'API (admin seulement)."""
    require_admin(current_user)

    result = await db.execute(
        select(ApiKey).order_by(ApiKey.created_at.desc())
    )
    keys = result.scalars().all()
    return [ApiKeyRead.model_validate(k) for k in keys]


@router.post("", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    data: ApiKeyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Crée une nouvelle clé d'API.

    La clé brute est retournée UNE SEULE FOIS — copiez-la immédiatement.
    """
    require_admin(current_user)

    raw_key, key_hash = generate_api_key()
    # Stocker les 12 premiers caractères comme préfixe visible
    key_prefix = raw_key[:12] + "..."

    api_key = ApiKey(
        name=data.name,
        description=data.description,
        key_hash=key_hash,
        key_prefix=key_prefix,
        owner_id=current_user.id,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    logger.info(
        "api_key_created",
        key_id=str(api_key.id),
        name=data.name,
        by=str(current_user.id),
    )

    return ApiKeyCreated(
        **ApiKeyRead.model_validate(api_key).model_dump(),
        raw_key=raw_key,
    )


@router.delete("/{key_id}", response_model=MessageResponse)
async def revoke_api_key(
    key_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Révoque (désactive) une clé d'API."""
    require_admin(current_user)

    api_key = await db.get(ApiKey, key_id)
    if not api_key:
        raise HTTPException(status_code=404, detail="Clé introuvable")

    api_key.is_active = False
    await db.commit()

    logger.info("api_key_revoked", key_id=key_id, by=str(current_user.id))
    return MessageResponse(message="Clé révoquée")


@router.delete("/{key_id}/permanent", response_model=MessageResponse)
async def delete_api_key(
    key_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Supprime définitivement une clé d'API."""
    require_admin(current_user)

    api_key = await db.get(ApiKey, key_id)
    if not api_key:
        raise HTTPException(status_code=404, detail="Clé introuvable")

    await db.delete(api_key)
    await db.commit()

    logger.info("api_key_deleted", key_id=key_id, by=str(current_user.id))
    return MessageResponse(message="Clé supprimée")
