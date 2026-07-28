"""
Legrand GeoAI — Service RAG (Retrieval-Augmented Generation).

Pipeline : embed query → retrieve → rerank → gating de pertinence → sélection
de document → expansion « parent-document » → build context → generate.

Deux problèmes généraux résolus par cette stratégie (aucune logique propre à un
document) :
- Contamination inter-documents : le gating de pertinence + la sélection de
  document écartent les passages d'autres fichiers peu pertinents.
- Procédures incomplètes : l'expansion parent-document réinjecte TOUT le
  document sélectionné dans l'ordre de lecture → aucune étape sautée.
"""

from collections.abc import AsyncGenerator

import structlog

from app.config import settings
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import LLMService
from app.services.reranker_service import RerankerService
from app.services.vector_store import VectorStoreService
from app.services.prompts import (
    CONTEXT_CHUNK_TEMPLATE,
    CONTEXT_TEMPLATE,
    SYSTEM_PROMPT_RAG,
)

logger = structlog.get_logger()

_NOT_FOUND = (
    "Je n'ai pas trouvé d'information pertinente dans les documents disponibles "
    "pour répondre à votre question."
)


class RAGService:
    """Service RAG complet."""

    def __init__(
        self,
        embedding_service: EmbeddingService | None = None,
        vector_store: VectorStoreService | None = None,
        reranker: RerankerService | None = None,
        llm_service: LLMService | None = None,
    ):
        self.embedding = embedding_service or EmbeddingService()
        self.vector_store = vector_store or VectorStoreService()
        self.reranker = reranker or RerankerService()
        self.llm = llm_service or LLMService()

    # ------------------------------------------------------------------
    # Helpers (gating / sélection / expansion) — partagés stream + non-stream
    # ------------------------------------------------------------------

    @staticmethod
    def _doc_id_of(md: dict) -> str:
        return md.get("document_id") or md.get("doc_id") or ""

    @staticmethod
    def _build_sources(items: list[dict], metadatas: list[dict]) -> list[dict]:
        """Sources affichées (UI) à partir des passages retenus, ordre fourni."""
        sources = []
        for item in items:
            md = metadatas[item["index"]]
            raw_pages = md.get("page_numbers", "")
            page_list = (
                [int(p) for p in raw_pages.split(",") if p.strip()] if raw_pages else []
            )
            sources.append(
                {
                    "filename": md.get("filename", "Document inconnu"),
                    "chunk_index": md.get("chunk_index", 0),
                    "page_numbers": page_list,
                    "document_id": md.get("doc_id", ""),
                    "score": item["score"],
                }
            )
        return sources

    @staticmethod
    def _gate(reranked: list[dict]) -> list[dict]:
        """Garde les passages proches du meilleur score ET au-dessus du plancher."""
        if not reranked:
            return []
        top = reranked[0]["score"]
        return [
            it
            for it in reranked
            if it["score"] >= top - settings.RERANK_SCORE_GAP
            and it["score"] >= settings.RERANK_SCORE_FLOOR
        ]

    def _select_documents(
        self, gated: list[dict], metadatas: list[dict]
    ) -> tuple[list[str], dict[str, float]]:
        """Sélectionne le(s) document(s) dominant(s) parmi les passages retenus."""
        doc_scores: dict[str, float] = {}
        for it in gated:
            did = self._doc_id_of(metadatas[it["index"]])
            doc_scores[did] = max(doc_scores.get(did, float("-inf")), it["score"])
        if not doc_scores:
            return [], {}
        best = max(doc_scores.values())
        selected = [d for d, s in doc_scores.items() if s >= best - settings.DOC_SELECT_MARGIN]
        selected.sort(key=lambda d: doc_scores[d], reverse=True)
        return selected[: settings.MAX_SELECTED_DOCS], doc_scores

    def _expand_documents(
        self,
        collection_name: str,
        selected_ids: list[str],
        gated: list[dict],
        metadatas: list[dict],
    ) -> list[dict]:
        """Expansion parent-document : tout le document (ordre de lecture).

        Si un document dépasse MAX_DOC_CHUNKS, on se rabat sur les passages
        retenus + leurs voisins (NEIGHBOR_WINDOW) pour ce document.
        """
        context_chunks: list[dict] = []
        for did in selected_ids:
            full = self.vector_store.get_document_chunks(collection_name, did)
            if not full:
                # Repli : le document n'a pas pu être relu, on garde ses passages gated.
                full = [
                    {"text": g["text"], "metadata": metadatas[g["index"]]}
                    for g in gated
                    if self._doc_id_of(metadatas[g["index"]]) == did
                ]

            if len(full) <= settings.MAX_DOC_CHUNKS:
                chosen = full
            else:
                keep: set[int] = set()
                for g in gated:
                    md = metadatas[g["index"]]
                    if self._doc_id_of(md) == did:
                        ci = md.get("chunk_index", 0)
                        keep.update(
                            range(
                                ci - settings.NEIGHBOR_WINDOW,
                                ci + settings.NEIGHBOR_WINDOW + 1,
                            )
                        )
                chosen = [
                    c for c in full if c["metadata"].get("chunk_index", 0) in keep
                ]

            for c in chosen:
                md = c["metadata"]
                context_chunks.append(
                    {
                        "filename": md.get("filename", "Document inconnu"),
                        "chunk_index": md.get("chunk_index", 0),
                        "document_id": self._doc_id_of(md),
                        "text": c["text"],
                    }
                )
        return context_chunks

    def _cap_context(
        self, context_chunks: list[dict], gated: list[dict], metadatas: list[dict]
    ) -> list[dict]:
        """Borne le nombre total de passages, en gardant les plus proches des gated."""
        if len(context_chunks) <= settings.MAX_CONTEXT_CHUNKS:
            return context_chunks
        gated_idx: dict[str, set[int]] = {}
        for g in gated:
            md = metadatas[g["index"]]
            gated_idx.setdefault(self._doc_id_of(md), set()).add(md.get("chunk_index", 0))

        def distance(c: dict) -> int:
            idxs = gated_idx.get(c["document_id"])
            if not idxs:
                return 10**9
            return min(abs(c["chunk_index"] - gi) for gi in idxs)

        return sorted(context_chunks, key=distance)[: settings.MAX_CONTEXT_CHUNKS]

    def _retrieve_context(
        self, collection_name: str, reranked: list[dict], metadatas: list[dict]
    ) -> tuple[list[dict], list[str], list[dict], dict]:
        """Gate → sélection → expansion → cap → tri.

        Returns: (context_chunks_ordonnés, selected_ids, sources_items, doc_scores)
        """
        gated = self._gate(reranked)
        if not gated:
            return [], [], [], {}
        selected_ids, doc_scores = self._select_documents(gated, metadatas)
        sources_items = [
            it for it in gated if self._doc_id_of(metadatas[it["index"]]) in selected_ids
        ]
        context_chunks = self._expand_documents(
            collection_name, selected_ids, gated, metadatas
        )
        context_chunks = self._cap_context(context_chunks, gated, metadatas)
        context_chunks.sort(key=lambda c: (c["filename"], c["chunk_index"]))
        return context_chunks, selected_ids, sources_items, doc_scores

    @staticmethod
    def _build_prompt(context_chunks: list[dict], question: str) -> str:
        context_parts = [
            CONTEXT_CHUNK_TEMPLATE.format(
                filename=c["filename"], rank=rank, text=c["text"]
            )
            for rank, c in enumerate(context_chunks, 1)
        ]
        return CONTEXT_TEMPLATE.format(context="\n".join(context_parts), query=question)

    # ------------------------------------------------------------------
    # Pipelines
    # ------------------------------------------------------------------

    async def query(
        self,
        question: str,
        collection_name: str,
        n_retrieve: int = settings.RAG_N_RETRIEVE,
        n_rerank: int = settings.RAG_N_RERANK,
        temperature: float = 0.15,
    ) -> dict:
        """Pipeline RAG non-streaming.

        Returns:
            {"answer": str, "sources": list[dict], "tokens_used": int}
        """
        query_embedding = await self.embedding.embed_query(question)

        results = self.vector_store.query(
            collection_name=collection_name,
            query_embedding=query_embedding,
            n_results=n_retrieve,
        )

        if not results["ids"] or not results["ids"][0]:
            return {"answer": _NOT_FOUND, "sources": [], "tokens_used": 0}

        documents = results["documents"][0]
        metadatas = results["metadatas"][0]

        reranked = await self.reranker.rerank(
            query=question, documents=documents, top_k=n_rerank
        )

        context_chunks, selected_ids, sources_items, doc_scores = self._retrieve_context(
            collection_name, reranked, metadatas
        )
        if not context_chunks:
            return {"answer": _NOT_FOUND, "sources": [], "tokens_used": 0}

        sources = self._build_sources(sources_items, metadatas)
        prompt = self._build_prompt(context_chunks, question)

        logger.info(
            "rag_doc_selection",
            top_score=round(reranked[0]["score"], 4) if reranked else 0,
            gated=len(sources_items),
            selected=selected_ids,
            context_chunks=len(context_chunks),
        )

        answer = await self.llm.generate(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT_RAG,
            temperature=temperature,
        )

        return {"answer": answer, "sources": sources, "tokens_used": 0}

    async def query_stream(
        self,
        question: str,
        collection_name: str,
        n_retrieve: int = settings.RAG_N_RETRIEVE,
        n_rerank: int = settings.RAG_N_RERANK,
        temperature: float = 0.15,
    ) -> AsyncGenerator[dict, None]:
        """Pipeline RAG en streaming.

        Yields :
        - {"type": "sources", "sources": [...]}
        - {"type": "token", "content": "..."}
        - {"type": "done", "tokens_used": N}
        """
        query_embedding = await self.embedding.embed_query(question)

        results = self.vector_store.query(
            collection_name=collection_name,
            query_embedding=query_embedding,
            n_results=n_retrieve,
        )

        if not results["ids"] or not results["ids"][0]:
            yield {"type": "token", "content": _NOT_FOUND}
            yield {"type": "done", "tokens_used": 0}
            return

        documents = results["documents"][0]
        metadatas = results["metadatas"][0]

        logger.debug(
            "rag_retrieval", question_len=len(question), chunks_retrieved=len(documents)
        )

        reranked = await self.reranker.rerank(
            query=question, documents=documents, top_k=n_rerank
        )

        context_chunks, selected_ids, sources_items, doc_scores = self._retrieve_context(
            collection_name, reranked, metadatas
        )

        if not context_chunks:
            yield {"type": "token", "content": _NOT_FOUND}
            yield {"type": "done", "tokens_used": 0}
            return

        # Sources (UI) : passages retenus des documents sélectionnés, par pertinence.
        yield {"type": "sources", "sources": self._build_sources(sources_items, metadatas)}

        prompt = self._build_prompt(context_chunks, question)

        logger.info(
            "rag_doc_selection",
            top_score=round(reranked[0]["score"], 4) if reranked else 0,
            gated=len(sources_items),
            selected=selected_ids,
            doc_scores={k: round(v, 4) for k, v in doc_scores.items()},
        )
        logger.info(
            "rag_parent_expansion",
            context_chunks=len(context_chunks),
            context_length=len(prompt),
        )

        async for chunk in self.llm.generate_stream(
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT_RAG,
            temperature=temperature,
        ):
            yield chunk
