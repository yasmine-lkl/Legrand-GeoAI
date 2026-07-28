"""
Legrand GeoAI — Schémas Document.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel


class DocumentRead(BaseModel):
    """Document en lecture."""

    id: uuid.UUID
    filename: str
    original_filename: str
    mime_type: str
    file_size: int
    status: str
    page_count: int | None = None
    chunk_count: int | None = None
    ocr_method: str | None = None
    error_message: str | None = None
    sub_status: str | None = None
    progress: int | None = None
    workflow_run_id: str | None = None
    collection_id: uuid.UUID
    collection_name: str | None = None
    uploaded_by: uuid.UUID
    uploader_name: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentUploadResponse(BaseModel):
    """Réponse après upload d'un document."""

    id: uuid.UUID
    filename: str
    status: str
    message: str = "Document mis en file d'attente pour traitement"
