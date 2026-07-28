"""
Legrand GeoAI — Routes de gestion des utilisateurs.

Réservé aux administrateurs.
"""

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User, UserRole
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.security.rbac import require_admin
from app.services import audit_service, user_service

router = APIRouter(prefix="/api/users", tags=["Utilisateurs"])
logger = structlog.get_logger()


@router.get("", response_model=PaginatedResponse[UserRead])
async def list_users(
    page: int = 1,
    size: int = 20,
    role: UserRole | None = None,
    is_active: bool | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Liste tous les utilisateurs (admin seulement)."""
    require_admin(current_user)

    users, total = await user_service.list_users(db, page, size, role, is_active)
    items = [UserRead.model_validate(u) for u in users]
    return PaginatedResponse.create(items=items, total=total, page=page, size=size)


@router.get("/{user_id}", response_model=UserRead)
async def get_user(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Récupère un utilisateur par ID (admin seulement)."""
    require_admin(current_user)

    user = await user_service.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable",
        )
    return UserRead.model_validate(user)


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
    data: UserCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Crée un nouvel utilisateur (admin seulement)."""
    require_admin(current_user)

    existing = await user_service.get_user_by_email(db, data.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un compte avec cet email existe déjà",
        )

    user = await user_service.create_user(db, data)

    await audit_service.log_action(
        db,
        user_id=current_user.id,
        action="user.create",
        resource_type="user",
        resource_id=user.id,
        details={"email": user.email, "role": user.role.value},
        ip_address=request.client.host if request.client else None,
    )

    logger.info("user_created", user_id=str(user.id), by=str(current_user.id))
    return UserRead.model_validate(user)


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: uuid.UUID,
    data: UserUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Met à jour un utilisateur (admin seulement)."""
    require_admin(current_user)

    # Empêcher un admin de se retirer son propre rôle admin
    if user_id == current_user.id and data.role and data.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vous ne pouvez pas modifier votre propre rôle d'administrateur",
        )

    user = await user_service.update_user(db, user_id, data)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable",
        )

    await audit_service.log_action(
        db,
        user_id=current_user.id,
        action="user.update",
        resource_type="user",
        resource_id=user_id,
        details=data.model_dump(exclude_unset=True, exclude={"password"}),
        ip_address=request.client.host if request.client else None,
    )

    logger.info("user_updated", user_id=str(user_id), by=str(current_user.id))
    return UserRead.model_validate(user)


@router.delete("/{user_id}", response_model=MessageResponse)
async def delete_user(
    user_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Désactive un utilisateur (soft delete, admin seulement)."""
    require_admin(current_user)

    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vous ne pouvez pas désactiver votre propre compte",
        )

    user = await user_service.deactivate_user(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable",
        )

    await audit_service.log_action(
        db,
        user_id=current_user.id,
        action="user.deactivate",
        resource_type="user",
        resource_id=user_id,
        ip_address=request.client.host if request.client else None,
    )

    logger.info("user_deactivated", user_id=str(user_id), by=str(current_user.id))
    return MessageResponse(message=f"Utilisateur {user.email} désactivé")
