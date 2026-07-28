"""
Legrand GeoAI — Hachage et vérification de mots de passe.
"""

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """Hache un mot de passe en clair avec bcrypt."""
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Vérifie un mot de passe en clair contre son hash."""
    return pwd_context.verify(plain_password, hashed_password)
