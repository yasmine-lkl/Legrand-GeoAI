"""
Legrand GeoAI — Schémas communs (pagination, réponses génériques).
"""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams:
    """Paramètres de pagination (utilisable comme Depends)."""

    def __init__(self, page: int = 1, size: int = 20):
        self.page = max(1, page)
        self.size = max(1, min(100, size))

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


class PaginatedResponse(BaseModel, Generic[T]):
    """Réponse paginée générique."""

    items: list[T]
    total: int
    page: int
    size: int
    pages: int

    @classmethod
    def create(
        cls,
        items: list[T],
        total: int,
        page: int | None = None,
        size: int | None = None,
        params: "PaginationParams | None" = None,
    ) -> "PaginatedResponse[T]":
        if params is not None:
            page = params.page
            size = params.size
        page = page or 1
        size = size or 20
        pages = (total + size - 1) // size if size > 0 else 0
        return cls(items=items, total=total, page=page, size=size, pages=pages)


class MessageResponse(BaseModel):
    """Réponse simple avec message."""

    message: str


class ErrorResponse(BaseModel):
    """Réponse d'erreur."""

    detail: str
