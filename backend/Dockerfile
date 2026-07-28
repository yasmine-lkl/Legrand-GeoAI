# ============================================================
# Legrand GeoAI — Backend Dockerfile
# ============================================================

# --- Stage 1: Build ---
FROM python:3.12-slim AS builder

RUN pip install --no-cache-dir uv

WORKDIR /build

COPY pyproject.toml .

# torch CPU d'abord (depuis l'index PyTorch CPU) : évite le téléchargement de
# ~5 Go de bibliothèques CUDA. Le gros calcul GPU (VLM) tourne dans Ollama ;
# Docling (layout/tables) + EasyOCR fonctionnent en CPU. Pour activer le GPU
# côté Docling/EasyOCR, réinstaller torch depuis l'index CUDA et rebâtir.
RUN uv venv /opt/venv && \
    . /opt/venv/bin/activate && \
    uv pip install --no-cache torch torchvision \
        --index-url https://download.pytorch.org/whl/cpu && \
    uv pip install --no-cache -r pyproject.toml

# --- Stage 2: Runtime ---
FROM python:3.12-slim AS runtime

# System deps for OCR + PDF processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    poppler-utils \
    libmagic1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

# Copy virtualenv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# --- Pré-téléchargement des modèles d'extraction (fonctionnement hors-ligne) ---
# Docling (layout/tables), EasyOCR (fr/en) et le tokenizer BGE-M3 du chunker
# sont bakés dans l'image : aucun accès réseau requis à l'exécution.
ENV DOCLING_ARTIFACTS_PATH=/opt/docling-models
ENV HF_HOME=/opt/hf-cache
ENV EASYOCR_MODULE_PATH=/opt/easyocr
# Étapes séparées → chaque téléchargement réussi est mis en cache de couche.
# On ne récupère que layout + TableFormer (pas code-formula/picture/rapidocr).
RUN python -c "from pathlib import Path; from docling.utils.model_downloader import download_models; \
download_models(output_dir=Path('/opt/docling-models'), with_code_formula=False, with_picture_classifier=False, with_rapidocr=False)"
RUN python -c "import easyocr; easyocr.Reader(['fr','en'], model_storage_directory='/opt/easyocr', download_enabled=True)"
RUN python -c "from transformers import AutoTokenizer; AutoTokenizer.from_pretrained('BAAI/bge-m3')"
# Reranker CrossEncoder (RAG) — baké pour un fonctionnement hors-ligne.
RUN python -c "from sentence_transformers import CrossEncoder; CrossEncoder('BAAI/bge-reranker-v2-m3')"
RUN chown -R appuser:appuser /opt/docling-models /opt/hf-cache /opt/easyocr

# Après le bake : forcer le mode hors-ligne à l'exécution (aucun accès réseau).
ENV HF_HUB_OFFLINE=1
ENV TRANSFORMERS_OFFLINE=1

WORKDIR /app

# Copy application code
COPY alembic.ini .
COPY alembic/ alembic/
COPY seed_admin.py .
COPY app/ app/

# Create data directories
RUN mkdir -p /data/uploads /data/chromadb && \
    chown -R appuser:appuser /app /data

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
