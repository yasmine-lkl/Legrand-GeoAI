"""Ajout des colonnes de progression d'ingestion (orchestration Hatchet).

Revision ID: 002_document_progress
Revises: 001_initial
Create Date: 2026-06-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision: str = "002_document_progress"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents", sa.Column("sub_status", sa.String(30), nullable=True)
    )
    op.add_column(
        "documents", sa.Column("progress", sa.Integer(), nullable=True)
    )
    op.add_column(
        "documents", sa.Column("workflow_run_id", sa.String(255), nullable=True)
    )
    op.create_index(
        "ix_documents_workflow_run_id",
        "documents",
        ["workflow_run_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_documents_workflow_run_id", table_name="documents")
    op.drop_column("documents", "workflow_run_id")
    op.drop_column("documents", "progress")
    op.drop_column("documents", "sub_status")
