"""
Legrand GeoAI — Service de stockage vectoriel.

Opérations ChromaDB : création de collections, ajout/recherche/suppression
de chunks vectorisés.
"""

import chromadb
import structlog

from app.config import settings

logger = structlog.get_logger()


class VectorStoreService:
    """Wrapper ChromaDB PersistentClient."""

    def __init__(self, persist_dir: str | None = None):
        self.persist_dir = persist_dir or settings.CHROMA_PERSIST_DIR
        self._client: chromadb.PersistentClient | None = None

    @property
    def client(self) -> chromadb.PersistentClient:
        """Lazy-init du client ChromaDB."""
        if self._client is None:
            self._client = chromadb.PersistentClient(path=self.persist_dir)
            logger.info(
                "chromadb_initialized",
                persist_dir=self.persist_dir,
            )
        return self._client

    # ------------------------------------------------------------------
    # Collections
    # ------------------------------------------------------------------

    def get_or_create_collection(self, name: str) -> chromadb.Collection:
        """
        Récupère ou crée une collection ChromaDB.

        Utilise la distance cosinus (meilleur match pour BGE-M3).
        """
        collection = self.client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.debug("chromadb_collection_ready", collection=name)
        return collection

    def delete_collection(self, name: str) -> None:
        """Supprime une collection ChromaDB."""
        try:
            self.client.delete_collection(name=name)
            logger.info("chromadb_collection_deleted", collection=name)
        except ValueError:
            logger.warning(
                "chromadb_collection_not_found",
                collection=name,
            )

    def list_collections(self) -> list[str]:
        """Liste toutes les collections."""
        collections = self.client.list_collections()
        return [c.name for c in collections]

    # ------------------------------------------------------------------
    # Chunks
    # ------------------------------------------------------------------

    def add_chunks(
        self,
        collection_name: str,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict] | None = None,
        batch_size: int = 500,
    ) -> int:
        """
        Ajoute des chunks vectorisés dans une collection.

        Traite par batch pour éviter les problèmes de mémoire.

        Args:
            collection_name: Nom de la collection ChromaDB.
            ids: Identifiants uniques des chunks.
            embeddings: Vecteurs BGE-M3.
            documents: Textes bruts des chunks.
            metadatas: Métadonnées associées.
            batch_size: Taille des batchs (défaut 500).

        Returns:
            Nombre total de chunks ajoutés.
        """
        collection = self.get_or_create_collection(collection_name)
        total_added = 0

        for i in range(0, len(ids), batch_size):
            end = min(i + batch_size, len(ids))

            batch_kwargs = {
                "ids": ids[i:end],
                "embeddings": embeddings[i:end],
                "documents": documents[i:end],
            }
            if metadatas:
                batch_kwargs["metadatas"] = metadatas[i:end]

            collection.add(**batch_kwargs)
            total_added += end - i

            logger.debug(
                "chromadb_chunks_added",
                collection=collection_name,
                batch_added=end - i,
                total_added=total_added,
                total=len(ids),
            )

        logger.info(
            "chromadb_add_completed",
            collection=collection_name,
            chunks_count=total_added,
        )

        return total_added

    def query(
        self,
        collection_name: str,
        query_embedding: list[float],
        n_results: int = 10,
        where: dict | None = None,
    ) -> dict:
        """
        Recherche les chunks les plus proches.

        Args:
            collection_name: Nom de la collection.
            query_embedding: Vecteur de la requête.
            n_results: Nombre de résultats souhaités.
            where: Filtre optionnel sur les métadonnées.

        Returns:
            Résultats ChromaDB (ids, documents, distances, metadatas).
        """
        collection = self.get_or_create_collection(collection_name)

        query_kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            query_kwargs["where"] = where

        results = collection.query(**query_kwargs)

        logger.debug(
            "chromadb_query",
            collection=collection_name,
            n_results=n_results,
            found=len(results["ids"][0]) if results["ids"] else 0,
        )

        return results

    def delete_document_chunks(
        self,
        collection_name: str,
        document_id: str,
    ) -> None:
        """
        Supprime tous les chunks d'un document donné.

        Args:
            collection_name: Nom de la collection.
            document_id: UUID du document.
        """
        collection = self.get_or_create_collection(collection_name)

        collection.delete(
            where={"document_id": document_id},
        )

        logger.info(
            "chromadb_document_deleted",
            collection=collection_name,
            document_id=document_id,
        )

    def get_document_chunks(
        self,
        collection_name: str,
        document_id: str,
    ) -> list[dict]:
        """Récupère TOUS les chunks d'un document, triés par chunk_index.

        Utilisé pour la récupération « parent-document » : une fois le document
        pertinent identifié, on réinjecte l'intégralité de ses passages dans
        l'ordre de lecture (aucune étape sautée).

        `collection.get` renvoie un dict plat et NON trié → on trie en Python.

        Returns:
            Liste de {"text": str, "metadata": dict}, ordonnée par chunk_index.
        """
        collection = self.get_or_create_collection(collection_name)
        res = collection.get(
            where={"document_id": document_id},
            include=["documents", "metadatas"],
        )
        docs = res.get("documents") or []
        metas = res.get("metadatas") or []
        chunks = [{"text": d, "metadata": m} for d, m in zip(docs, metas)]
        chunks.sort(key=lambda c: c["metadata"].get("chunk_index", 0))

        logger.debug(
            "chromadb_document_chunks_fetched",
            collection=collection_name,
            document_id=document_id,
            chunks=len(chunks),
        )
        return chunks

    def collection_count(self, collection_name: str) -> int:
        """Nombre de chunks dans une collection."""
        collection = self.get_or_create_collection(collection_name)
        return collection.count()

    def heartbeat(self) -> bool:
        """Vérifie que ChromaDB répond."""
        try:
            self.client.heartbeat()
            return True
        except Exception:
            return False
