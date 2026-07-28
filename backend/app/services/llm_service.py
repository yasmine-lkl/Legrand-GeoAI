"""
Legrand GeoAI — Service LLM.

Interface avec Ollama pour la génération de texte (Qwen3 32B).
Supporte le streaming SSE token par token.
"""

import asyncio
from collections.abc import AsyncGenerator

import httpx
import structlog

from app.config import settings

logger = structlog.get_logger()


class LLMService:
    """Service de génération de texte via Ollama."""

    def __init__(
        self,
        ollama_url: str | None = None,
        model: str | None = None,
    ):
        self.ollama_url = ollama_url or settings.OLLAMA_BASE_URL
        self.model = model or settings.LLM_MODEL

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = settings.LLM_MAX_TOKENS,
    ) -> str:
        """
        Génération non-streaming (réponse complète).

        Args:
            prompt: Message utilisateur.
            system_prompt: Instructions système.
            temperature: Créativité (0.0 → déterministe, 1.0 → créatif).
            max_tokens: Nombre max de tokens générés.

        Returns:
            Texte généré.
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{self.ollama_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "think": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                        # Fenêtre de contexte : doit englober contexte RAG + réponse,
                        # sinon Ollama tronque silencieusement le prompt.
                        "num_ctx": settings.LLM_NUM_CTX,
                    },
                },
            )
            response.raise_for_status()
            data = response.json()

        content = data["message"]["content"]
        tokens_used = data.get("eval_count", 0)

        logger.info(
            "llm_generate",
            model=self.model,
            tokens=tokens_used,
            temperature=temperature,
            num_ctx=settings.LLM_NUM_CTX,
        )

        return content

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = settings.LLM_MAX_TOKENS,
    ) -> AsyncGenerator[dict, None]:
        """
        Génération en streaming (token par token).

        Yields des dictionnaires :
        - {"type": "token", "content": "..."} pour chaque token
        - {"type": "done", "tokens_used": N} à la fin

        Args:
            prompt: Message utilisateur.
            system_prompt: Instructions système.
            temperature: Créativité.
            max_tokens: Nombre max de tokens.
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        total_tokens = 0

        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream(
                "POST",
                f"{self.ollama_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": True,
                    "think": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                        # Fenêtre de contexte : doit englober contexte RAG + réponse,
                        # sinon Ollama tronque silencieusement le prompt.
                        "num_ctx": settings.LLM_NUM_CTX,
                    },
                },
            ) as response:
                response.raise_for_status()

                import json

                async for line in response.aiter_lines():
                    if not line.strip():
                        continue

                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if data.get("done"):
                        total_tokens = data.get("eval_count", total_tokens)
                        yield {"type": "done", "tokens_used": total_tokens}
                        break

                    token = data.get("message", {}).get("content", "")
                    if token:
                        total_tokens += 1
                        yield {"type": "token", "content": token}

        logger.info(
            "llm_stream_completed",
            model=self.model,
            tokens=total_tokens,
            num_ctx=settings.LLM_NUM_CTX,
        )

    async def is_available(self) -> bool:
        """Vérifie que Ollama et le modèle sont disponibles."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.ollama_url}/api/tags")
                response.raise_for_status()
                data = response.json()
                models = [m["name"] for m in data.get("models", [])]
                return self.model in models or any(
                    self.model in m for m in models
                )
        except Exception:
            return False
