"""
Legrand GeoAI — Schémas d'authentification.
"""

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """Requête de connexion."""

    email: EmailStr
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    """Réponse contenant les tokens JWT."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """Requête de rafraîchissement de token."""

    refresh_token: str


class RegisterRequest(BaseModel):
    """Requête d'inscription."""

    email: EmailStr
    password: str = Field(min_length=8, description="Minimum 8 caractères")
    full_name: str = Field(min_length=2, max_length=255)
