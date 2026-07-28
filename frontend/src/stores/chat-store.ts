/**
 * Legrand GeoAI — Store de chat (Zustand).
 *
 * Gère l'état du chat et le streaming SSE de manière globale,
 * ce qui permet à la génération de continuer même quand
 * l'utilisateur navigue vers une autre page.
 */

import { create } from "zustand";
import { api } from "@/lib/api";
import type { SourceInfo } from "@/lib/types";
import toast from "react-hot-toast";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  sources?: SourceInfo[];
  isStreaming?: boolean;
}

interface ChatStore {
  messages: ChatMessage[];
  sessionId: string | null;
  selectedCollection: string;
  isStreaming: boolean;

  /**
   * Incrémenté chaque fois qu'un streaming se termine (succès ou erreur).
   * Les composants peuvent surveiller cette valeur pour déclencher
   * un refetch des sessions (pour faire remonter le chat actif).
   */
  streamDoneCounter: number;

  // ── Actions ──────────────────────────────────────────
  setSelectedCollection: (id: string) => void;
  setSessionId: (id: string | null) => void;
  setMessages: (messages: ChatMessage[]) => void;
  newChat: () => void;

  /**
   * Lance la requête RAG en streaming.
   * Le streaming tourne dans une promesse "fire-and-forget"
   * qui ne dépend pas du cycle de vie du composant React.
   */
  sendMessage: (input: string) => void;

  /**
   * Charge une session existante depuis l'API et restaure la collection.
   */
  loadSession: (sessionId: string, collectionId: string | null) => Promise<void>;
}

export const useChatStore = create<ChatStore>()((set, get) => ({
  messages: [],
  sessionId: null,
  selectedCollection: "",
  isStreaming: false,
  streamDoneCounter: 0,

  setSelectedCollection: (id) => set({ selectedCollection: id }),
  setSessionId: (id) => set({ sessionId: id }),
  setMessages: (messages) => set({ messages }),

  newChat: () => set({ messages: [], sessionId: null }),

  // ── Streaming ────────────────────────────────────────
  sendMessage: (input: string) => {
    const { selectedCollection, sessionId, isStreaming } = get();
    if (!input.trim() || isStreaming) return;

    if (!selectedCollection) {
      toast.error("Sélectionnez une collection");
      return;
    }

    const trimmed = input.trim();

    // Ajouter les messages dans le store immédiatement
    set((state) => ({
      messages: [
        ...state.messages,
        { role: "user" as const, content: trimmed },
        { role: "assistant" as const, content: "", isStreaming: true },
      ],
      isStreaming: true,
    }));

    // ── Fire-and-forget async — survit au démontage du composant ──
    (async () => {
      let fullContent = "";
      let sources: SourceInfo[] = [];

      try {
        const stream = api.streamChat({
          message: trimmed,
          collection_id: selectedCollection,
          session_id: sessionId || undefined,
        });

        for await (const { event, data } of stream) {
          if (event === "sources") {
            sources = (data as { sources: SourceInfo[] }).sources;
          } else if (event === "token") {
            fullContent += (data as { content: string }).content;
            const captured = fullContent; // capture for closure
            set((state) => {
              const updated = [...state.messages];
              const last = updated[updated.length - 1];
              if (last?.role === "assistant") {
                last.content = captured;
              }
              return { messages: updated };
            });
          } else if (event === "done") {
            const doneData = data as {
              tokens_used: number;
              session_id: string;
            };
            if (doneData.session_id) {
              set({ sessionId: doneData.session_id });
            }
          } else if (event === "error") {
            toast.error("Erreur lors de la génération");
          }
        }

        // ── Finaliser ──
        set((state) => {
          const updated = [...state.messages];
          const last = updated[updated.length - 1];
          if (last?.role === "assistant") {
            last.isStreaming = false;
            last.sources = sources;
          }
          return {
            messages: updated,
            isStreaming: false,
            streamDoneCounter: state.streamDoneCounter + 1,
          };
        });
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : "Erreur de connexion";
        toast.error(message);

        set((state) => {
          const updated = [...state.messages];
          const last = updated[updated.length - 1];
          if (last?.role === "assistant") {
            last.content = "Désolé, une erreur est survenue.";
            last.isStreaming = false;
          }
          return {
            messages: updated,
            isStreaming: false,
            streamDoneCounter: state.streamDoneCounter + 1,
          };
        });
      }
    })();
  },

  // ── Charger une session existante ────────────────────
  loadSession: async (sessionId, collectionId) => {
    set({ sessionId });

    if (collectionId) {
      set({ selectedCollection: collectionId });
    }

    try {
      const detail = await api.get<{
        id: string;
        title: string;
        collection_id: string | null;
        messages: {
          role: string;
          content: string;
          sources?: SourceInfo[];
        }[];
      }>(`/chat/sessions/${sessionId}`);

      set({
        messages: detail.messages.map((m) => ({
          role: m.role as "user" | "assistant",
          content: m.content,
          sources: m.sources,
        })),
      });

      if (detail.collection_id) {
        set({ selectedCollection: detail.collection_id });
      }
    } catch {
      toast.error("Impossible de charger la conversation");
    }
  },
}));
