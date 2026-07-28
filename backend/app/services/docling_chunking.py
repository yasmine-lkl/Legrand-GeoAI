"""
Legrand GeoAI — Découpage (chunking) structuré via Docling HybridChunker.

Le HybridChunker découpe un `DoclingDocument` en respectant la structure
(titres, sections, tables) et la limite de tokens du modèle d'embedding
(BGE-M3). `contextualize()` préfixe chaque chunk de ses titres de section,
ce qui améliore nettement la pertinence du RAG.

Sortie : la même forme de dict que l'ancien chunker, pour que `vectorize_store`
et ChromaDB restent inchangés :
    {chunk_id, text, metadata{doc_id, document_id, filename, chunk_index,
                              page_numbers, headings}}
"""

import structlog

from app.config import settings

logger = structlog.get_logger()

# Cible ~512 tokens/chunk : bon compromis granularité/contexte pour BGE-M3.
MAX_TOKENS = 512


class DoclingChunkingService:
    """Wrapper autour du HybridChunker de Docling."""

    def __init__(self, embed_model: str | None = None) -> None:
        self._chunker = None
        self._embed_model = embed_model or settings.EMBED_MODEL

    @property
    def chunker(self):
        if self._chunker is None:
            from docling.chunking import HybridChunker

            # Tokenizer = modèle d'embedding (BGE-M3) → les chunks tiennent dans
            # sa fenêtre. La forme « string + max_tokens » est gérée nativement
            # (HybridChunker construit le HuggingFaceTokenizer en interne).
            tokenizer_id = "BAAI/bge-m3"
            self._chunker = HybridChunker(
                tokenizer=tokenizer_id, max_tokens=MAX_TOKENS, merge_peers=True
            )
            logger.info("docling_chunker_ready", tokenizer=tokenizer_id, max_tokens=MAX_TOKENS)
        return self._chunker

    def chunk_document(self, dl_doc, doc_id: str, filename: str = "") -> list[dict]:
        """Découpe un DoclingDocument en chunks prêts pour l'embedding."""
        chunks: list[dict] = []
        for i, ch in enumerate(self.chunker.chunk(dl_doc=dl_doc)):
            text = self.chunker.contextualize(chunk=ch)
            if not text or not text.strip():
                continue
            chunks.append(
                {
                    "chunk_id": f"{doc_id}_chunk_{i}",
                    "text": text.strip(),
                    "metadata": {
                        "doc_id": doc_id,
                        "document_id": doc_id,
                        "filename": filename,
                        "chunk_index": i,
                        "page_numbers": _page_numbers(ch),
                        "headings": _headings(ch),
                    },
                }
            )

        logger.info("docling_chunking_completed", doc_id=doc_id, chunks_count=len(chunks))
        return chunks

    def chunk_supplement(
        self, pages: list[tuple[int, str]], doc_id: str, filename: str, start_index: int
    ) -> list[dict]:
        """Transforme la transcription VLM en chunks ALIGNÉS SUR LES PAGES.

        `pages` = liste (n° de page, texte). Un chunk par page (redécoupé si la
        page est très longue), avec le numéro de page exact → citations précises,
        chunks plus fins (meilleure pertinence) et ordre de lecture préservé.
        """
        out: list[dict] = []
        idx = start_index
        # Redécoupe une page trop longue pour rester dans la fenêtre BGE-M3
        # (~512 tokens ≈ 1500 caractères) ; la plupart des pages tiennent en un seul.
        step = 1500
        for page_no, raw in pages:
            text = (raw or "").strip()
            if not text:
                continue
            parts = (
                [text]
                if len(text) <= step
                else [text[i : i + step] for i in range(0, len(text), step)]
            )
            for part in parts:
                part = part.strip()
                if not part:
                    continue
                out.append(
                    {
                        "chunk_id": f"{doc_id}_vlm_{idx}",
                        "text": part,
                        "metadata": {
                            "doc_id": doc_id,
                            "document_id": doc_id,
                            "filename": filename,
                            "chunk_index": idx,
                            "page_numbers": str(page_no),
                            "headings": f"Page {page_no} (OCR image)",
                        },
                    }
                )
                idx += 1
        return out


def _page_numbers(ch) -> str:
    pages = set()
    try:
        for item in ch.meta.doc_items:
            for prov in getattr(item, "prov", []) or []:
                pno = getattr(prov, "page_no", None)
                if pno is not None:
                    pages.add(pno)
    except Exception:
        pass
    return ",".join(str(p) for p in sorted(pages))


def _headings(ch) -> str:
    try:
        hs = ch.meta.headings or []
        return " > ".join(hs)
    except Exception:
        return ""
