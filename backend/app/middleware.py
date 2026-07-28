"""
Legrand GeoAI — Middleware de sécurité.

Rate limiting en mémoire et headers de sécurité.
"""

import time
from collections import defaultdict

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
import structlog

logger = structlog.get_logger()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiter simple par IP en mémoire.

    En production, Caddy gère aussi le rate limiting.
    Cette couche est une protection de secours.
    """

    def __init__(
        self,
        app,
        requests_per_minute: int = 60,
        burst: int = 10,
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.burst = burst
        self.window = 60.0  # 1 minute
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Pas de rate limit sur les health checks
        if request.url.path.startswith("/api/health"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()

        # Nettoyer les anciennes entrées
        self._requests[client_ip] = [
            t for t in self._requests[client_ip] if now - t < self.window
        ]

        if len(self._requests[client_ip]) >= self.requests_per_minute:
            logger.warning(
                "rate_limited",
                ip=client_ip,
                path=request.url.path,
            )
            return Response(
                content='{"detail": "Trop de requêtes. Réessayez dans une minute."}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": "60"},
            )

        self._requests[client_ip].append(now)

        response = await call_next(request)
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Ajoute des headers de sécurité à toutes les réponses."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )

        return response
