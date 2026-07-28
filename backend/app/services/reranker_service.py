"""
Legrand GeoAI — Service de reranking.

Utilise bge-reranker-v2-m3 (CrossEncoder) pour réordonner les résultats
de recherche vectorielle par pertinence.
"""

import asyncio

import structlog

from app.config import settings

logger = structlog.get_logger()


class RerankerService:
    """
    Service de reranking via sentence-transformers CrossEncoder.

    Le modèle est chargé en lazy pour économiser la mémoire au démarrage.
    """

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or settings.RERANKER_MODEL_NAME
        self._model = None

    @property
    def model(self):
        """Chargement lazy du CrossEncoder."""
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder

                self._model = CrossEncoder(self.model_name)
                logger.info("reranker_loaded", model=self.model_name)
            except ImportError:
                logger.warning(
                    "reranker_unavailable",
                    reason="sentence-transformers not installed",
                )
                return None
        return self._model

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int = 5,
    ) -> list[dict]:
        """
        Réordonne les documents par pertinence par rapport à la requête.

        Args:
            query: Question de l'utilisateur.
            documents: Liste de textes candidats.
            top_k: Nombre de résultats à retourner.

        Returns:
            Liste triée de dicts : {"index": int, "text": str, "score": float}
        """
        if not documents:
            return []

        # If reranker model not available, return documents as-is with dummy scores
        if self.model is None:
            logger.warning("reranker_fallback", reason="model not loaded, returning top docs by order")
            return [
                {"index": i, "text": doc, "score": 1.0 - (i * 0.1)}
                for i, doc in enumerate(documents[:top_k])
            ]

        # Préparer les paires (query, document)
        pairs = [(query, doc) for doc in documents]

        # Le CrossEncoder est CPU-bound, on l'exécute dans un thread
        scores = await asyncio.to_thread(self._predict, pairs)

        # Construire la liste triée
        scored_docs = [
            {"index": i, "text": doc, "score": float(score)}
            for i, (doc, score) in enumerate(zip(documents, scores))
        ]

        # Trier par score décroissant
        scored_docs.sort(key=lambda x: x["score"], reverse=True)

        result = scored_docs[:top_k]

        logger.debug(
            "reranker_completed",
            query_len=len(query),
            candidates=len(documents),
            top_k=top_k,
            top_score=result[0]["score"] if result else 0,
        )

        return result

    def _predict(self, pairs: list[tuple[str, str]]) -> list[float]:
        """Calcul synchrone des scores de pertinence."""
        return self.model.predict(pairs).tolist()
