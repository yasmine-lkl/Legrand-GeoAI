"""
Legrand GeoAI — Dépendances FastAPI partagées.
"""

import hashlib
from datetime import datetime, timezone
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.security.jwt import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


async def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    x_api_key: str | None = Header(default=None, alias="X-Api-Key"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Dépendance FastAPI : extrait et valide l'utilisateur courant.
    Accepte soit un JWT Bearer token, soit un header X-Api-Key.

    Raises:
        HTTPException(401) si le token est invalide ou l'utilisateur n'existe pas.
        HTTPException(403) si le compte est désactivé.
    """
    # ── X-Api-Key path ───────────────────────────────────
    if x_api_key:
        from app.models.api_key import ApiKey

        key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
        result = await db.execute(
            select(ApiKey).where(ApiKey.key_hash == key_hash)
        )
        api_key = result.scalar_one_or_none()

        if api_key is None or not api_key.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Clé API invalide ou révoquée",
                headers={"WWW-Authenticate": "ApiKey"},
            )

        if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Clé API expirée",
            )

        # Mettre à jour last_used_at
        api_key.last_used_at = datetime.now(timezone.utc)
        await db.commit()

        user = api_key.owner
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Compte propriétaire désactivé",
            )
        return user

    # ── JWT Bearer path ──────────────────────────────────
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Non authentifié",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(token)

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        uid = UUID(user_id)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(
        select(User).where(User.id == uid)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilisateur introuvable",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compte désactivé. Contactez l'administrateur.",
        )

    return user
