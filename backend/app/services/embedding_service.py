"""
Legrand GeoAI — Service d'embedding.

Génère les vecteurs d'embedding via Ollama (modèle BGE-M3).
"""

import asyncio

import httpx
import structlog

from app.config import settings

logger = structlog.get_logger()


class EmbeddingService:
    """Service d'embedding via l'API Ollama."""

    def __init__(
        self,
        ollama_url: str | None = None,
        model: str | None = None,
        batch_size: int = 32,
    ):
        self.ollama_url = ollama_url or settings.OLLAMA_BASE_URL
        self.model = model or settings.EMBED_MODEL
        self.batch_size = batch_size

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Génère les embeddings pour une liste de textes.

        Traite par batch pour éviter les timeouts Ollama.
        Retry automatique avec backoff exponentiel.

        Args:
            texts: Liste de textes à vectoriser.

        Returns:
            Liste de vecteurs (un par texte).
        """
        if not texts:
            return []

        all_embeddings = []

        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            embeddings = await self._embed_batch(batch)
            all_embeddings.extend(embeddings)

            if i + self.batch_size < len(texts):
                logger.debug(
                    "embedding_progress",
                    completed=min(i + self.batch_size, len(texts)),
                    total=len(texts),
                )

        logger.info(
            "embedding_completed",
            texts_count=len(texts),
            vectors_count=len(all_embeddings),
            dimensions=len(all_embeddings[0]) if all_embeddings else 0,
        )

        return all_embeddings

    async def _embed_batch(
        self, texts: list[str], max_retries: int = 3
    ) -> list[list[float]]:
        """Embed un batch de textes avec retry."""
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    response = await client.post(
                        f"{self.ollama_url}/api/embed",
                        json={
                            "model": self.model,
                            "input": texts,
                        },
                    )
                    response.raise_for_status()
                    data = response.json()
                    return data["embeddings"]

            except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
                wait_time = 2**attempt
                logger.warning(
                    "embedding_retry",
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    wait_seconds=wait_time,
                    error=str(e),
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(wait_time)
                else:
                    logger.error("embedding_failed", error=str(e))
                    raise

        return []  # Ne devrait jamais arriver

    async def embed_query(self, query: str) -> list[float]:
        """
        Génère l'embedding pour une requête utilisateur.

        Args:
            query: Texte de la question.

        Returns:
            Vecteur d'embedding.
        """
        embeddings = await self.embed_texts([query])
        return embeddings[0]
