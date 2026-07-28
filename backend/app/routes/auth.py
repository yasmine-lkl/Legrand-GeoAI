"""
Legrand GeoAI — Routes d'authentification.

Login, inscription, rafraîchissement de token, profil.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse
from app.schemas.user import UserRead
from app.security.jwt import create_access_token, create_refresh_token, decode_token
from app.security.passwords import verify_password
from app.services import audit_service, user_service

router = APIRouter(prefix="/api/auth", tags=["Authentification"])
logger = structlog.get_logger()


@router.post("/login", response_model=TokenResponse)
async def login(
    data: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Connexion utilisateur.

    Retourne un access_token et un refresh_token JWT.
    """
    user = await user_service.get_user_by_email(db, data.email)

    if not user or not verify_password(data.password, user.hashed_password):
        # Log tentative échouée
        await audit_service.log_action(
            db,
            action="user.login_failed",
            details={"email": data.email},
            ip_address=request.client.host if request.client else None,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compte désactivé. Contactez l'administrateur.",
        )

    # Générer les tokens
    access_token = create_access_token(user.id, user.role.value)
    refresh_token = create_refresh_token(user.id)

    # Mettre à jour la dernière connexion
    await user_service.update_last_login(db, user)

    # Audit
    await audit_service.log_action(
        db,
        user_id=user.id,
        action="user.login",
        ip_address=request.client.host if request.client else None,
    )

    logger.info("user_login", user_id=str(user.id), email=user.email)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(
    data: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Inscription d'un nouvel utilisateur.

    Le compte est créé avec le rôle 'viewer' par défaut.
    """
    existing = await user_service.get_user_by_email(db, data.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un compte avec cet email existe déjà",
        )

    from app.schemas.user import UserCreate
    from app.models.user import UserRole

    user = await user_service.create_user(
        db,
        UserCreate(
            email=data.email,
            password=data.password,
            full_name=data.full_name,
            role=UserRole.VIEWER,
        ),
    )

    # Audit
    await audit_service.log_action(
        db,
        user_id=user.id,
        action="user.register",
        resource_type="user",
        resource_id=user.id,
        ip_address=request.client.host if request.client else None,
    )

    logger.info("user_register", user_id=str(user.id), email=user.email)
    return UserRead.model_validate(user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    data: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Rafraîchit les tokens JWT.

    Requiert un refresh_token valide.
    """
    payload = decode_token(data.refresh_token)

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de type invalide. Utilisez un refresh_token.",
        )

    from uuid import UUID

    user = await user_service.get_user_by_id(db, UUID(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur invalide ou désactivé",
        )

    access_token = create_access_token(user.id, user.role.value)
    refresh_token_new = create_refresh_token(user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token_new,
    )


@router.get("/me", response_model=UserRead)
async def get_me(current_user: User = Depends(get_current_user)):
    """Retourne le profil de l'utilisateur connecté."""
    return UserRead.model_validate(current_user)
