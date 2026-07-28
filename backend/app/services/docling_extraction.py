"""
Legrand GeoAI — Extraction documentaire via Docling.

Docling unifie le traitement des PDF natifs, des PDF scannés et des images :
analyse de mise en page, ordre de lecture, tables (TableFormer) et OCR
(EasyOCR français). Le résultat est un `DoclingDocument` structuré, exporté en
Markdown puis découpé par le `HybridChunker` (voir `docling_chunking`).

Pour les pages mal océrisées (plans denses, texte incliné), un repli optionnel
escalade vers un VLM (Qwen3-VL via Ollama) qui retranscrit la page.

Les modèles sont pré-téléchargés dans l'image (DOCLING_ARTIFACTS_PATH) :
fonctionnement 100% hors-ligne.
"""

import base64
import os
from pathlib import Path

import httpx
import structlog

from app.config import settings

logger = structlog.get_logger()


class DoclingExtractionService:
    """Service d'extraction structurée basé sur Docling."""

    def __init__(self) -> None:
        self._converter = None  # construit paresseusement (modèles lourds)

    # ------------------------------------------------------------------
    # Converter Docling (lazy, réutilisé)
    # ------------------------------------------------------------------
    @property
    def converter(self):
        if self._converter is None:
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import (
                EasyOcrOptions,
                PdfPipelineOptions,
            )
            from docling.document_converter import (
                DocumentConverter,
                PdfFormatOption,
            )

            opts = PdfPipelineOptions(
                do_ocr=True,
                do_table_structure=True,
                artifacts_path=settings.DOCLING_ARTIFACTS_PATH or None,
            )
            # OCR EasyOCR en français (modèles bakés → pas de téléchargement).
            easyocr_dir = os.environ.get("EASYOCR_MODULE_PATH") or None
            opts.ocr_options = EasyOcrOptions(
                lang=settings.ocr_langs_list,
                download_enabled=False,
                model_storage_directory=easyocr_dir,
            )
            opts.table_structure_options.do_cell_matching = True

            self._converter = DocumentConverter(
                format_options={
                    InputFormat.PDF: PdfFormatOption(pipeline_options=opts),
                    InputFormat.IMAGE: PdfFormatOption(pipeline_options=opts),
                }
            )
            logger.info("docling_converter_ready", langs=settings.ocr_langs_list)
        return self._converter

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------
    def parse(self, file_path: Path, mime_type: str | None = None):
        """Convertit un fichier en DoclingDocument structuré.

        Returns:
            (dl_doc, ocr_method, page_count)
        """
        # Détecte si l'OCR sera nécessaire AVANT le parsing (couche texte native).
        method = self._detect_method(file_path, mime_type)

        result = self.converter.convert(str(file_path))
        dl_doc = result.document
        page_count = len(getattr(dl_doc, "pages", []) or []) or None
        return dl_doc, method, page_count

    @staticmethod
    def _detect_method(file_path: Path, mime_type: str | None) -> str:
        """Indique la méthode d'extraction (native vs OCR) de façon fiable."""
        if mime_type and mime_type.startswith("image/"):
            return "docling+easyocr"
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(str(file_path))
            try:
                pages = len(doc)
                chars = sum(len(doc[i].get_text("text").strip()) for i in range(pages))
            finally:
                doc.close()
            avg = chars / max(pages, 1)
            return "docling-native" if avg >= 100 else "docling+easyocr"
        except Exception:
            return "docling"

    # ------------------------------------------------------------------
    # Repli VLM (Qwen3-VL via Ollama) pour les pages difficiles
    # ------------------------------------------------------------------
    async def vlm_supplement(
        self, file_path: Path, dl_doc
    ) -> tuple[list[tuple[int, str]], bool]:
        """Retranscrit via le VLM les pages dont l'OCR a peu rendu.

        Returns:
            (pages, used_vlm) où `pages` est une liste (n° de page, texte),
            triée par page — un élément par page enrichie. Garder le découpage
            par page (plutôt qu'un seul bloc) permet des chunks alignés sur les
            pages, avec numéro de page exact pour les citations.
        """
        if not settings.VLM_FALLBACK_ENABLED or file_path.suffix.lower() == "":
            return [], False

        # Texte extrait par page (longueur) pour repérer les pages pauvres.
        per_page_chars = self._chars_per_page(dl_doc)
        weak_pages = [
            p for p, n in per_page_chars.items() if n < settings.VLM_MIN_CHARS_PER_PAGE
        ]
        if not weak_pages:
            return [], False

        try:
            import fitz  # PyMuPDF
        except Exception:
            return [], False

        import asyncio

        # 1. Rendu des images (PyMuPDF, synchrone et rapide) pour les pages faibles.
        #    150 DPI : suffisant pour l'OCR par VLM, ~4× moins de pixels qu'à 300 DPI
        #    → bien moins de tokens visuels, transcription plus rapide.
        doc = fitz.open(str(file_path))
        try:
            jobs: list[tuple[int, str]] = []  # (page_index, img_b64)
            for page_index in weak_pages:
                if page_index < 1 or page_index > len(doc):
                    continue
                pix = doc[page_index - 1].get_pixmap(dpi=150)
                jobs.append(
                    (page_index, base64.b64encode(pix.tobytes("png")).decode())
                )
        finally:
            doc.close()

        # 2. Transcription VLM en parallèle : le GPU traite plusieurs pages à la
        #    fois (le sémaphore borne la charge pour ne pas saturer la VRAM).
        sem = asyncio.Semaphore(max(1, settings.VLM_CONCURRENCY))

        async def _one(page_index: int, img_b64: str) -> tuple[int, str]:
            async with sem:
                return page_index, await self._vlm_transcribe(img_b64)

        results = await asyncio.gather(*[_one(p, b) for p, b in jobs])

        # 3. Conserver les pages réellement enrichies, dans l'ordre des pages,
        #    en gardant l'association (n° de page, texte) pour le chunking.
        pages: list[tuple[int, str]] = []
        for page_index, text in sorted(results, key=lambda r: r[0]):
            if text and len(text.strip()) > per_page_chars.get(page_index, 0):
                pages.append((page_index, text.strip()))
                logger.info("vlm_supplemented_page", page=page_index, chars=len(text))

        return pages, bool(pages)

    @staticmethod
    def _chars_per_page(dl_doc) -> dict[int, int]:
        counts: dict[int, int] = {}
        try:
            for item, _ in dl_doc.iterate_items():
                text = getattr(item, "text", "") or ""
                for prov in getattr(item, "prov", []) or []:
                    pno = getattr(prov, "page_no", None)
                    if pno is not None:
                        counts[pno] = counts.get(pno, 0) + len(text)
        except Exception:
            pass
        # S'assurer que toutes les pages sont représentées (0 si vide).
        for pno in range(1, (len(getattr(dl_doc, "pages", []) or []) or 0) + 1):
            counts.setdefault(pno, 0)
        return counts

    async def _vlm_transcribe(self, img_b64: str) -> str:
        """Appelle le VLM (Ollama) pour restituer le contenu d'une page image.

        Prompt orienté "procédure" : au-delà de l'OCR brut, le modèle explicite
        ce que montre la page et ce que désignent les annotations (flèches /
        encadrés rouges) — c'est généralement l'étape clé d'un mode d'emploi.
        Reste général pour tous types de pages (capture, photo, schéma,
        étiquette, tableau) et interdit toute invention.
        """
        prompt = (
            "Tu analyses une page d'un document technique (capture d'écran, photo "
            "d'appareil, schéma, étiquette ou page de manuel) et tu en restitues "
            "le contenu de façon fidèle et directement exploitable.\n"
            "- Retranscris TOUT le texte visible exactement : titres, libellés de "
            "menus, boutons, valeurs, codes, tableaux, légendes.\n"
            "- Décris les éléments d'interface et l'état affiché quand ils portent "
            "une information utile (onglet actif, case cochée, bouton, voyant).\n"
            "- Indique précisément ce que désignent les annotations ajoutées "
            "(flèches, encadrés ou textes rouges) : l'élément, l'action ou "
            "l'emplacement signalé — c'est souvent l'étape clé d'une procédure.\n"
            "- Conserve l'ordre de lecture logique et la structure (étapes, "
            "listes, tableaux).\n"
            "- N'invente RIEN : si une zone est illisible, écris [illisible]. "
            "Pas de préambule ni de commentaire, donne directement le contenu."
        )
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                resp = await client.post(
                    f"{settings.OLLAMA_BASE_URL}/api/generate",
                    json={
                        "model": settings.VLM_MODEL,
                        "prompt": prompt,
                        "images": [img_b64],
                        "stream": False,
                        "options": {"num_ctx": 4096},
                    },
                )
                resp.raise_for_status()
                return resp.json().get("response", "")
        except Exception as e:
            # repr(e) : str() est vide pour les timeouts httpx, on garde le type.
            logger.warning("vlm_transcribe_failed", error=repr(e))
            return ""
