"""
Legrand GeoAI — Contrôle d'accès basé sur les rôles (RBAC).

Usage in routes (as Depends):
    current_user: User = Depends(require_user)

Usage inline:
    require_admin(current_user)
"""

from fastapi import Depends, HTTPException, status

from app.models.user import User, UserRole


class RoleChecker:
    """
    Vérificateur de rôle.

    Can be used both as a FastAPI dependency and called directly.
    When used as Depends(), FastAPI resolves get_current_user automatically.
    When called directly, pass the user object.
    """

    def __init__(self, allowed_roles: list[UserRole]):
        self.allowed_roles = allowed_roles

    def __call__(self, current_user: User) -> User:
        if current_user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Accès refusé. Rôle requis : {', '.join(r.value for r in self.allowed_roles)}",
            )
        return current_user


# Instances pré-configurées
require_admin = RoleChecker([UserRole.ADMIN])
require_user = RoleChecker([UserRole.ADMIN, UserRole.USER])
require_any = RoleChecker([UserRole.ADMIN, UserRole.USER, UserRole.VIEWER])
