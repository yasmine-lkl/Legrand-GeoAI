"""
Legrand GeoAI — Service d'audit.

Enregistre chaque action importante pour conformité RGPD.
"""

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog

logger = structlog.get_logger()


async def log_action(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None = None,
    action: str,
    resource_type: str | None = None,
    resource_id: uuid.UUID | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
) -> None:
    """
    Enregistre une action dans le journal d'audit.

    Args:
        db: Session de base de données
        user_id: ID de l'utilisateur ayant effectué l'action
        action: Type d'action (ex: "user.login", "document.upload")
        resource_type: Type de ressource affectée (ex: "document", "user")
        resource_id: ID de la ressource affectée
        details: Détails supplémentaires (JSON)
        ip_address: Adresse IP du client
    """
    try:
        audit_entry = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
        )
        db.add(audit_entry)
        await db.commit()

        logger.info(
            "audit_log",
            action=action,
            user_id=str(user_id) if user_id else None,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
        )
    except Exception as e:
        logger.error("audit_log_failed", action=action, error=str(e))
        # Ne pas propager l'erreur d'audit pour ne pas bloquer l'action principale
        await db.rollback()
