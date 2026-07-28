/**
 * Legrand GeoAI — Client API.
 *
 * Fetch wrapper avec gestion automatique du JWT et du refresh token.
 */

import { useAuthStore } from "@/stores/auth-store";
import type { TokenResponse } from "./types";

const API_BASE = "/api";

class ApiClient {
  private refreshPromise: Promise<string | null> | null = null;

  private getHeaders(): HeadersInit {
    const token = useAuthStore.getState().accessToken;
    const headers: HeadersInit = {};
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
    return headers;
  }

  private async refreshToken(): Promise<string | null> {
    const { refreshToken, setTokens, logout } = useAuthStore.getState();
    if (!refreshToken) {
      logout();
      return null;
    }

    try {
      const res = await fetch(`${API_BASE}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (!res.ok) {
        logout();
        return null;
      }

      const data: TokenResponse = await res.json();
      setTokens(data.access_token, data.refresh_token);
      return data.access_token;
    } catch {
      logout();
      return null;
    }
  }

  async fetch<T>(
    path: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${API_BASE}${path}`;
    const headers = { ...this.getHeaders(), ...options.headers };

    let res = await fetch(url, { ...options, headers });

    // Auto-refresh sur 401
    if (res.status === 401) {
      if (!this.refreshPromise) {
        this.refreshPromise = this.refreshToken();
      }

      const newToken = await this.refreshPromise;
      this.refreshPromise = null;

      if (newToken) {
        const retryHeaders = {
          ...options.headers,
          Authorization: `Bearer ${newToken}`,
        };
        res = await fetch(url, { ...options, headers: retryHeaders });
      } else {
        throw new Error("Session expirée");
      }
    }

    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: "Erreur réseau" }));
      throw new Error(error.detail || `Erreur ${res.status}`);
    }

    return res.json();
  }

  async get<T>(path: string): Promise<T> {
    return this.fetch<T>(path);
  }

  async post<T>(path: string, body?: unknown): Promise<T> {
    return this.fetch<T>(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  async patch<T>(path: string, body?: unknown): Promise<T> {
    return this.fetch<T>(path, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  async delete<T>(path: string): Promise<T> {
    return this.fetch<T>(path, { method: "DELETE" });
  }

  async upload<T>(path: string, formData: FormData): Promise<T> {
    const url = `${API_BASE}${path}`;
    const token = useAuthStore.getState().accessToken;

    const headers: HeadersInit = {};
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const res = await fetch(url, {
      method: "POST",
      headers,
      body: formData,
    });

    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: "Erreur upload" }));
      throw new Error(error.detail || `Erreur ${res.status}`);
    }

    return res.json();
  }

  /**
   * Stream SSE pour le chat RAG.
   * Utilise le chemin relatif `/api` : en production les requêtes passent par
   * Caddy (qui respecte `X-Accel-Buffering: no` et ne bufferise pas le SSE).
   */
  async *streamChat(
    body: { message: string; collection_id: string; session_id?: string }
  ): AsyncGenerator<{ event: string; data: unknown }> {
    const url = `${API_BASE}/chat/query`;
    const token = useAuthStore.getState().accessToken;

    const res = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: "Erreur chat" }));
      throw new Error(error.detail || `Erreur ${res.status}`);
    }

    const reader = res.body?.getReader();
    if (!reader) throw new Error("Pas de stream");

    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      let currentEvent = "message";

      for (const line of lines) {
        if (line.startsWith("event: ")) {
          currentEvent = line.slice(7).trim();
        } else if (line.startsWith("data: ")) {
          try {
            const data = JSON.parse(line.slice(6));
            yield { event: currentEvent, data };
          } catch {
            // ignore invalid JSON
          }
        }
      }
    }
  }

  /**
   * Stream SSE de progression d'ingestion d'un document (orchestré par Hatchet).
   * Connexion directe au backend (comme streamChat) pour éviter le buffering du
   * proxy Next.js qui casse les Server-Sent Events.
   */
  async *streamDocumentProgress(
    documentId: string
  ): AsyncGenerator<{ event: string; data: unknown }> {
    const url = `${API_BASE}/documents/${documentId}/progress`;
    const token = useAuthStore.getState().accessToken;

    const res = await fetch(url, {
      method: "GET",
      headers: {
        Accept: "text/event-stream",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });

    if (!res.ok) {
      throw new Error(`Erreur ${res.status}`);
    }

    const reader = res.body?.getReader();
    if (!reader) throw new Error("Pas de stream");

    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      let currentEvent = "message";

      for (const line of lines) {
        if (line.startsWith("event: ")) {
          currentEvent = line.slice(7).trim();
        } else if (line.startsWith("data: ")) {
          try {
            const data = JSON.parse(line.slice(6));
            yield { event: currentEvent, data };
          } catch {
            // ignore invalid JSON
          }
        }
      }
    }
  }
}

export const api = new ApiClient();
