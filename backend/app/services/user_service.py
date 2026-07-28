"""
Legrand GeoAI — Service utilisateur.

Logique métier CRUD pour les utilisateurs.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserUpdate
from app.security.passwords import hash_password


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Récupère un utilisateur par email."""
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    """Récupère un utilisateur par ID."""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, data: UserCreate) -> User:
    """Crée un nouvel utilisateur."""
    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        role=data.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def list_users(
    db: AsyncSession,
    page: int = 1,
    size: int = 20,
    role: UserRole | None = None,
    is_active: bool | None = None,
) -> tuple[list[User], int]:
    """Liste les utilisateurs avec pagination et filtres."""
    query = select(User)
    count_query = select(func.count()).select_from(User)

    if role is not None:
        query = query.where(User.role == role)
        count_query = count_query.where(User.role == role)
    if is_active is not None:
        query = query.where(User.is_active == is_active)
        count_query = count_query.where(User.is_active == is_active)

    # Total
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Items paginés
    offset = (page - 1) * size
    query = query.order_by(User.created_at.desc()).offset(offset).limit(size)
    result = await db.execute(query)
    users = list(result.scalars().all())

    return users, total


async def update_user(
    db: AsyncSession, user_id: uuid.UUID, data: UserUpdate
) -> User | None:
    """Met à jour un utilisateur."""
    user = await get_user_by_id(db, user_id)
    if not user:
        return None

    update_data = data.model_dump(exclude_unset=True)

    # Hash du nouveau mot de passe si fourni
    if "password" in update_data:
        update_data["hashed_password"] = hash_password(update_data.pop("password"))

    if update_data:
        await db.execute(
            update(User).where(User.id == user_id).values(**update_data)
        )
        await db.commit()
        await db.refresh(user)

    return user


async def deactivate_user(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    """Désactive un utilisateur (soft delete)."""
    user = await get_user_by_id(db, user_id)
    if not user:
        return None

    user.is_active = False
    await db.commit()
    await db.refresh(user)
    return user


async def update_last_login(db: AsyncSession, user: User) -> None:
    """Met à jour la date de dernière connexion."""
    await db.execute(
        update(User).where(User.id == user.id).values(last_login=datetime.now(UTC))
    )
    await db.commit()
