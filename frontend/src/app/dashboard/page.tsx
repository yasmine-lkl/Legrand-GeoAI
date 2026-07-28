"use client";

import { useEffect, useRef, useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useChatStore } from "@/stores/chat-store";
import type { ChatMessage } from "@/stores/chat-store";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn, formatDate } from "@/lib/utils";
import toast from "react-hot-toast";
import type {
  Collection,
  PaginatedResponse,
  ChatSession,
} from "@/lib/types";
import {
  Send,
  Bot,
  User as UserIcon,
  Plus,
  FileText,
  ChevronDown,
  Sparkles,
  Trash2,
  Search,
  X,
} from "lucide-react";
import { GeoAILoader } from "@/components/ui/geo-ai-loader";

export default function ChatPage() {
  const queryClient = useQueryClient();

  // ── Chat store (global — survit à la navigation) ────
  const {
    messages,
    sessionId,
    selectedCollection,
    isStreaming,
    streamDoneCounter,
    sendMessage,
    newChat,
    setSelectedCollection,
    loadSession,
  } = useChatStore();

  // ── Local UI state (réinitialisé à chaque montage, c'est OK) ──
  const [input, setInput] = useState("");
  const [showCollectionPicker, setShowCollectionPicker] = useState(false);
  const [collectionSearch, setCollectionSearch] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const pickerRef = useRef<HTMLDivElement>(null);

  // ── Queries ──────────────────────────────────────────
  const { data: collectionsData } = useQuery({
    queryKey: ["collections"],
    queryFn: () =>
      api.get<PaginatedResponse<Collection>>("/collections?size=100"),
  });

  const { data: sessionsData } = useQuery({
    queryKey: ["chat-sessions"],
    queryFn: () =>
      api.get<PaginatedResponse<ChatSession>>("/chat/sessions?size=50"),
  });

  const deleteSessionMutation = useMutation({
    mutationFn: (sid: string) => api.delete(`/chat/sessions/${sid}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["chat-sessions"] });
      toast.success("Conversation supprimée");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const collections = collectionsData?.items || [];
  const sessions = sessionsData?.items || [];

  // ── Derived ──────────────────────────────────────────
  const filteredCollections = useMemo(() => {
    if (!collectionSearch.trim()) return collections;
    const q = collectionSearch.toLowerCase();
    return collections.filter((c) => c.name.toLowerCase().includes(q));
  }, [collections, collectionSearch]);

  const selectedCol = collections.find((c) => c.id === selectedCollection);

  // ── Refetch sessions when streaming finishes ─────────
  // (streamDoneCounter increments in the store on each completion)
  const lastCounter = useRef(streamDoneCounter);
  useEffect(() => {
    if (streamDoneCounter > lastCounter.current) {
      queryClient.invalidateQueries({ queryKey: ["chat-sessions"] });
    }
    lastCounter.current = streamDoneCounter;
  }, [streamDoneCounter, queryClient]);

  // ── Close collection picker on outside click ─────────
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (pickerRef.current && !pickerRef.current.contains(e.target as Node)) {
        setShowCollectionPicker(false);
      }
    };
    if (showCollectionPicker) {
      document.addEventListener("mousedown", handleClick);
    }
    return () => document.removeEventListener("mousedown", handleClick);
  }, [showCollectionPicker]);

  // ── Auto-scroll ──────────────────────────────────────
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // ── Handlers ─────────────────────────────────────────
  const handleSend = () => {
    if (!input.trim() || isStreaming) return;
    sendMessage(input);
    setInput("");
  };

  const handleSelectSession = (session: ChatSession) => {
    loadSession(session.id, session.collection_id);
  };

  const handleDeleteSession = (e: React.MouseEvent, sid: string) => {
    e.stopPropagation();
    if (confirm("Supprimer cette conversation ?")) {
      deleteSessionMutation.mutate(sid);
      if (sessionId === sid) {
        newChat();
      }
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // ── Render ───────────────────────────────────────────
  return (
    <div className="flex h-full gap-4">
      {/* ─── Sessions sidebar ─────────────────────────── */}
      <div className="hidden w-72 flex-col gap-2 lg:flex">
        <Button onClick={newChat} className="gap-2">
          <Plus className="h-4 w-4" />
          Nouvelle conversation
        </Button>

        <div className="flex-1 space-y-1 overflow-y-auto scrollbar-thin">
          {sessions.map((session) => (
            <div key={session.id} className="group relative">
              <button
                onClick={() => handleSelectSession(session)}
                className={cn(
                  "w-full rounded-lg px-3 py-2.5 text-left text-sm transition-colors pr-9",
                  sessionId === session.id
                    ? "bg-brand-50 text-brand-700 dark:bg-brand-950/50 dark:text-brand-400"
                    : "text-surface-600 hover:bg-surface-100 dark:text-surface-400 dark:hover:bg-surface-800"
                )}
              >
                <p className="truncate font-medium">{session.title}</p>
                <p className="mt-0.5 text-xs text-surface-400">
                  {formatDate(session.updated_at)}
                </p>
              </button>
              <button
                onClick={(e) => handleDeleteSession(e, session.id)}
                className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded p-1 text-surface-400 opacity-0 transition-opacity hover:bg-red-50 hover:text-red-500 group-hover:opacity-100 dark:hover:bg-red-950/30"
                title="Supprimer"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* ─── Chat area ────────────────────────────────── */}
      <div className="flex flex-1 flex-col">
        {/* Collection picker with search */}
        <div className="mb-4 flex items-center gap-3">
          <div className="relative" ref={pickerRef}>
            <button
              onClick={() => {
                setShowCollectionPicker(!showCollectionPicker);
                setCollectionSearch("");
              }}
              className="flex items-center gap-2 rounded-lg border border-surface-300 bg-white px-4 py-2 text-sm shadow-sm transition-colors hover:bg-surface-50 dark:border-surface-600 dark:bg-surface-800 dark:hover:bg-surface-700"
            >
              <FileText className="h-4 w-4 text-surface-400" />
              {selectedCol ? selectedCol.name : "Choisir une collection"}
              <ChevronDown className="h-4 w-4 text-surface-400" />
            </button>

            {showCollectionPicker && (
              <div className="absolute left-0 top-full z-50 mt-1 w-72 rounded-lg border border-surface-200 bg-white shadow-lg dark:border-surface-700 dark:bg-surface-800">
                <div className="flex items-center gap-2 border-b border-surface-200 px-3 py-2 dark:border-surface-700">
                  <Search className="h-4 w-4 text-surface-400" />
                  <input
                    type="text"
                    value={collectionSearch}
                    onChange={(e) => setCollectionSearch(e.target.value)}
                    placeholder="Rechercher une collection..."
                    className="flex-1 bg-transparent text-sm outline-none placeholder:text-surface-400 dark:text-surface-100"
                    autoFocus
                  />
                  {collectionSearch && (
                    <button
                      onClick={() => setCollectionSearch("")}
                      className="text-surface-400 hover:text-surface-600"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
                <div className="max-h-60 overflow-y-auto p-1">
                  {filteredCollections.map((col) => (
                    <button
                      key={col.id}
                      onClick={() => {
                        setSelectedCollection(col.id);
                        setShowCollectionPicker(false);
                        setCollectionSearch("");
                      }}
                      className={cn(
                        "flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm hover:bg-surface-100 dark:hover:bg-surface-700",
                        col.id === selectedCollection &&
                          "bg-brand-50 text-brand-700 dark:bg-brand-950/50 dark:text-brand-400"
                      )}
                    >
                      <span className="flex-1 text-left">{col.name}</span>
                      <Badge variant="info">{col.document_count} docs</Badge>
                    </button>
                  ))}
                  {filteredCollections.length === 0 && (
                    <p className="px-3 py-4 text-center text-sm text-surface-400">
                      {collectionSearch
                        ? "Aucun résultat"
                        : "Aucune collection"}
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Streaming indicator — visible even if the user just navigated back */}
          {isStreaming && (
            <span className="flex items-center gap-2 text-xs text-brand-600 dark:text-brand-400">
              <span className="h-2 w-2 animate-pulse rounded-full bg-brand-500" />
              Génération en cours…
            </span>
          )}
        </div>

        {/* ─── Messages ───────────────────────────────── */}
        <div className="flex-1 overflow-y-auto rounded-xl border border-surface-200 bg-white p-4 dark:border-surface-700 dark:bg-surface-900 scrollbar-thin">
          {messages.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center text-center">
              <div className="mb-4 rounded-2xl bg-brand-50 p-4 dark:bg-brand-950/30">
                <Sparkles className="h-10 w-10 text-brand-600 dark:text-brand-400" />
              </div>
              <h3 className="text-xl font-semibold text-surface-900 dark:text-surface-50">
                Assistant Géomatique
              </h3>
              <p className="mt-2 max-w-md text-sm text-surface-500">
                Posez une question sur vos documents. L&apos;IA cherchera dans
                la collection sélectionnée et vous répondra avec les sources.
              </p>
            </div>
          ) : (
            <div className="space-y-6">
              {messages.map((msg: ChatMessage, i: number) => (
                <div
                  key={i}
                  className={cn(
                    "flex gap-3",
                    msg.role === "user" ? "justify-end" : "justify-start"
                  )}
                >
                  {msg.role === "assistant" && (
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand-100 dark:bg-brand-900/30">
                      <Bot className="h-4 w-4 text-brand-600 dark:text-brand-400" />
                    </div>
                  )}

                  <div
                    className={cn(
                      "max-w-[75%] rounded-2xl px-4 py-3 text-sm",
                      msg.role === "user"
                        ? "bg-brand-600 text-white"
                        : "bg-surface-100 text-surface-900 dark:bg-surface-800 dark:text-surface-100"
                    )}
                  >
                    {msg.isStreaming && !msg.content ? (
                      <GeoAILoader />
                    ) : (
                      <>
                        <div className="whitespace-pre-wrap">{msg.content}</div>
                        {msg.isStreaming && (
                          <span className="mt-1 inline-block h-4 w-1 animate-pulse rounded bg-brand-500" />
                        )}
                      </>
                    )}

                    {/* ── Sources groupées ──────────── */}
                    {msg.sources &&
                      msg.sources.length > 0 &&
                      (() => {
                        const grouped = new Map<
                          string,
                          {
                            pages: Set<number>;
                            score: number;
                            count: number;
                          }
                        >();
                        for (const src of msg.sources) {
                          const key = src.filename;
                          const entry = grouped.get(key) || {
                            pages: new Set<number>(),
                            score: 0,
                            count: 0,
                          };
                          src.page_numbers?.forEach((p: number) =>
                            entry.pages.add(p)
                          );
                          entry.score = Math.max(
                            entry.score,
                            src.score || 0
                          );
                          entry.count += 1;
                          grouped.set(key, entry);
                        }
                        return (
                          <div className="mt-3 space-y-1.5 border-t border-surface-200 pt-2 dark:border-surface-700">
                            <p className="text-xs font-semibold text-surface-500">
                              📄 Sources ({msg.sources!.length} extraits)
                            </p>
                            {[...grouped.entries()].map(
                              ([filename, info], j) => {
                                const pages = [...info.pages].sort(
                                  (a, b) => a - b
                                );
                                const pct = Math.round(info.score * 100);
                                return (
                                  <div
                                    key={j}
                                    className="flex items-center gap-2 rounded-md bg-surface-50 px-2.5 py-1.5 text-xs dark:bg-surface-800/60"
                                  >
                                    <FileText className="h-3.5 w-3.5 shrink-0 text-brand-500" />
                                    <span className="font-medium text-surface-700 dark:text-surface-200">
                                      {filename}
                                    </span>
                                    {pages.length > 0 && (
                                      <span className="text-surface-400">
                                        p. {pages.join(", ")}
                                      </span>
                                    )}
                                    {info.count > 1 && (
                                      <span className="rounded bg-brand-100 px-1.5 py-0.5 text-[10px] font-medium text-brand-700 dark:bg-brand-900/40 dark:text-brand-300">
                                        {info.count} extraits
                                      </span>
                                    )}
                                    {pct > 0 && (
                                      <span className="ml-auto rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300">
                                        {pct}%
                                      </span>
                                    )}
                                  </div>
                                );
                              }
                            )}
                          </div>
                        );
                      })()}
                  </div>

                  {msg.role === "user" && (
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-surface-200 dark:bg-surface-700">
                      <UserIcon className="h-4 w-4 text-surface-600 dark:text-surface-300" />
                    </div>
                  )}
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* ─── Input ──────────────────────────────────── */}
        <div className="mt-4 flex items-end gap-3">
          <div className="flex-1">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Posez votre question sur les documents..."
              rows={1}
              className="w-full resize-none rounded-xl border border-surface-300 bg-white px-4 py-3 text-sm shadow-sm transition-colors placeholder:text-surface-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 dark:border-surface-600 dark:bg-surface-800 dark:text-surface-100"
              style={{ minHeight: "48px", maxHeight: "120px" }}
              onInput={(e) => {
                const target = e.target as HTMLTextAreaElement;
                target.style.height = "48px";
                target.style.height = target.scrollHeight + "px";
              }}
            />
          </div>
          <Button
            onClick={handleSend}
            disabled={!input.trim() || isStreaming}
            size="icon"
            className="h-12 w-12 shrink-0 rounded-xl"
          >
            <Send className="h-5 w-5" />
          </Button>
        </div>
      </div>
    </div>
  );
}
