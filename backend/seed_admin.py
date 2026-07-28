"""
Legrand GeoAI — Script de création de l'administrateur initial.

Usage : python seed_admin.py
Idempotent : ne crée pas de doublon si l'admin existe déjà.
"""

import asyncio
import sys

from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.user import User, UserRole
from app.security.passwords import hash_password


async def seed_admin() -> None:
    """Crée le compte administrateur initial."""
    async with AsyncSessionLocal() as db:
        # Vérifier si l'admin existe déjà
        result = await db.execute(
            select(User).where(User.email == settings.ADMIN_EMAIL)
        )
        existing = result.scalar_one_or_none()

        if existing:
            print(f"✅ L'administrateur {settings.ADMIN_EMAIL} existe déjà.")
            return

        # Créer l'admin
        admin = User(
            email=settings.ADMIN_EMAIL,
            hashed_password=hash_password(settings.ADMIN_PASSWORD),
            full_name=settings.ADMIN_FULL_NAME,
            role=UserRole.ADMIN,
            is_active=True,
        )
        db.add(admin)
        await db.commit()

        print(f"✅ Administrateur créé : {settings.ADMIN_EMAIL}")
        print(f"   Nom    : {settings.ADMIN_FULL_NAME}")
        print(f"   Rôle   : admin")
        print(f"   ⚠️  Changez le mot de passe en production !")


if __name__ == "__main__":
    try:
        asyncio.run(seed_admin())
    except Exception as e:
        print(f"❌ Erreur lors de la création de l'admin : {e}", file=sys.stderr)
        sys.exit(1)
