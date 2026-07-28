"""
Legrand GeoAI — Service de stockage de documents.

Gère l'écriture/lecture/suppression des fichiers sur le filesystem.
Validation MIME, taille, et nommage sécurisé.
"""

import os
import re
import uuid
from pathlib import Path

import aiofiles
import structlog
from fastapi import HTTPException, UploadFile, status

from app.config import settings

logger = structlog.get_logger()

# Types MIME autorisés
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/tiff",
    "image/bmp",
    "image/webp",
}


def sanitize_filename(filename: str) -> str:
    """Nettoie un nom de fichier pour le stockage."""
    # Garder seulement les caractères alphanumériques, tirets, underscores, points
    name = re.sub(r"[^\w\-.]", "_", filename)
    # Limiter la longueur
    if len(name) > 200:
        ext = Path(name).suffix
        name = name[: 200 - len(ext)] + ext
    return name


class DocumentStorageService:
    """Service de stockage de fichiers sur le filesystem local."""

    def __init__(self, upload_dir: str | None = None):
        self.upload_dir = Path(upload_dir or settings.UPLOAD_DIR)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def save(
        self, file: UploadFile, collection_id: str
    ) -> dict:
        """
        Sauvegarde un fichier uploadé.

        Args:
            file: Fichier uploadé via FastAPI
            collection_id: ID de la collection cible

        Returns:
            (chemin_relatif, taille_en_octets, mime_type)

        Raises:
            HTTPException: Si le type ou la taille est invalide.
        """
        # Valider le type MIME
        content_type = file.content_type or "application/octet-stream"
        if content_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Type de fichier non autorisé : {content_type}. "
                    f"Types acceptés : PDF, PNG, JPEG, TIFF"
                ),
            )

        # Générer un nom de fichier sécurisé
        original_name = file.filename or "document"
        safe_name = sanitize_filename(original_name)
        unique_name = f"{uuid.uuid4().hex[:12]}_{safe_name}"

        # Chemin de stockage
        relative_path = f"{collection_id}/{unique_name}"
        full_path = self.upload_dir / relative_path
        full_path.parent.mkdir(parents=True, exist_ok=True)

        # Écriture en chunks pour limiter la mémoire
        total_size = 0
        max_size = settings.max_upload_bytes

        async with aiofiles.open(full_path, "wb") as f:
            while True:
                chunk = await file.read(65536)  # 64 KB chunks
                if not chunk:
                    break
                total_size += len(chunk)
                if total_size > max_size:
                    # Nettoyer le fichier partiel
                    await f.close()
                    os.unlink(full_path)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"Fichier trop volumineux. Maximum : {settings.MAX_UPLOAD_SIZE_MB} Mo",
                    )
                await f.write(chunk)

        logger.info(
            "document_saved",
            path=relative_path,
            size=total_size,
            mime=content_type,
        )

        return {
            "filename": unique_name,
            "original_filename": original_name,
            "mime_type": content_type,
            "file_size": total_size,
            "file_path": str(relative_path),
        }

    def get_full_path(self, relative_path: str) -> Path:
        """Retourne le chemin absolu d'un fichier stocké."""
        return self.upload_dir / relative_path

    async def delete(self, relative_path: str) -> bool:
        """
        Supprime un fichier du stockage.

        Returns:
            True si supprimé, False si fichier introuvable.
        """
        full_path = self.get_full_path(relative_path)
        if full_path.exists():
            os.unlink(full_path)
            logger.info("document_deleted", path=relative_path)
            # Nettoyer le répertoire parent si vide
            try:
                full_path.parent.rmdir()
            except OSError:
                pass  # Répertoire non vide, c'est ok
            return True
        return False
