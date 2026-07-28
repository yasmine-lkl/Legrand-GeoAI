"""
Legrand GeoAI — Configuration centralisée.

Toutes les variables d'environnement sont typées et validées via Pydantic Settings.
"""

from pathlib import Path

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

# .env is in the project root (one level above backend/)
_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    """Configuration de l'application chargée depuis les variables d'environnement."""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- PostgreSQL ---
    POSTGRES_USER: str = "geoai"
    POSTGRES_PASSWORD: str = "changez_moi_en_production"
    POSTGRES_DB: str = "legrand_geoai"
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432

    # --- Hatchet (orchestration du pipeline documentaire) ---
    # Le SDK lit aussi directement les variables HATCHET_CLIENT_* de l'env ;
    # on les expose ici pour la lisibilité et la validation.
    HATCHET_CLIENT_TOKEN: str = ""
    HATCHET_CLIENT_HOST_PORT: str = "hatchet:7077"
    HATCHET_CLIENT_TLS_STRATEGY: str = "none"

    # --- JWT ---
    JWT_SECRET_KEY: str = "changez_cette_cle_secrete_en_production_minimum_32_chars"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # --- Ollama ---
    OLLAMA_BASE_URL: str = "http://ollama:11434"
    LLM_MODEL: str = "qwen3:32b"
    EMBED_MODEL: str = "bge-m3"
    # Fenêtre de contexte LLM (tokens) : englobe system prompt + contexte RAG +
    # question + réponse. 12288 tient sur GPU 8 Go avec qwen3:8b (KV q8_0).
    LLM_NUM_CTX: int = 12288
    # Budget de génération (tokens de SORTIE), distinct de num_ctx.
    LLM_MAX_TOKENS: int = 1536

    # --- Reranker ---
    RERANKER_MODEL_NAME: str = "BAAI/bge-reranker-v2-m3"

    # --- RAG (récupération : gating + sélection de document + parent-document) ---
    # Profondeur de recherche vectorielle puis de reranking.
    # Le reranker (CrossEncoder) tourne sur CPU : ~0,75 s/passage. On limite donc
    # n_retrieve pour garder un 1er token rapide. L'expansion parent-document
    # réinjecte ensuite TOUT le document sélectionné, donc une faible profondeur
    # suffit (il faut juste qu'un passage du bon doc ressorte au reranking).
    RAG_N_RETRIEVE: int = 16
    RAG_N_RERANK: int = 10
    # Gating de pertinence après reranking : on garde un passage si son score
    # est proche du meilleur (écart relatif) ET au-dessus d'un plancher absolu.
    # → élimine le bruit inter-documents (passages d'autres fichiers peu pertinents).
    RERANK_SCORE_GAP: float = 0.15
    RERANK_SCORE_FLOOR: float = 0.02
    # Sélection de document(s) : on garde les documents dont le score est à
    # moins de MARGIN du meilleur (les vraies questions multi-docs marchent encore).
    DOC_SELECT_MARGIN: float = 0.10
    MAX_SELECTED_DOCS: int = 3
    # Expansion « parent-document » : on injecte TOUT le document sélectionné, dans
    # l'ordre de lecture, pour ne sauter aucune étape. Bornes pour tenir le budget.
    MAX_DOC_CHUNKS: int = 16
    MAX_CONTEXT_CHUNKS: int = 16
    # Fenêtre de voisinage (repli si un document dépasse MAX_DOC_CHUNKS).
    NEIGHBOR_WINDOW: int = 2

    # --- Extraction documentaire (Docling) ---
    # Modèles Docling pré-téléchargés dans l'image (fonctionnement hors-ligne).
    DOCLING_ARTIFACTS_PATH: str = "/opt/docling-models"
    # Langues OCR (EasyOCR) — CSV.
    OCR_LANGS: str = "fr,en"
    # Repli VLM (Qwen3-VL via Ollama) pour les pages mal océrisées.
    VLM_FALLBACK_ENABLED: bool = True
    VLM_MODEL: str = "qwen2.5vl:7b"
    # En dessous de N caractères extraits sur une page, on escalade vers le VLM.
    VLM_MIN_CHARS_PER_PAGE: int = 40
    # Pages transcrites en parallèle par le VLM. 1 = séquentiel et fiable :
    # sur GPU 8 Go le VLM est limité par le calcul, le parallélisme cause des timeouts.
    VLM_CONCURRENCY: int = 1

    @property
    def ocr_langs_list(self) -> list[str]:
        """Langues OCR sous forme de liste (depuis OCR_LANGS)."""
        return [s.strip() for s in self.OCR_LANGS.split(",") if s.strip()]

    # --- ChromaDB ---
    CHROMA_PERSIST_DIR: str = "/data/chromadb"

    # --- Fichiers ---
    UPLOAD_DIR: str = "/data/uploads"
    MAX_UPLOAD_SIZE_MB: int = 50

    # --- Admin initial ---
    ADMIN_EMAIL: str = "admin@legrand-geoai.local"
    ADMIN_PASSWORD: str = "changez_moi_en_production"
    ADMIN_FULL_NAME: str = "Administrateur"

    # --- Logging ---
    LOG_LEVEL: str = "info"

    # --- Caddy ---
    CADDY_DOMAIN: str = "localhost"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def DATABASE_URL(self) -> str:
        """URL de connexion PostgreSQL async."""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def DATABASE_URL_SYNC(self) -> str:
        """URL de connexion PostgreSQL sync (pour Alembic)."""
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def upload_path(self) -> Path:
        """Chemin du répertoire d'upload."""
        path = Path(self.UPLOAD_DIR)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def max_upload_bytes(self) -> int:
        """Taille maximale d'upload en octets."""
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024


settings = Settings()
