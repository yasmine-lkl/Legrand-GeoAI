"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatDate } from "@/lib/utils";
import toast from "react-hot-toast";
import {
  Plus,
  Trash2,
  Copy,
  CheckCheck,
  Key,
  X,
  AlertTriangle,
  Terminal,
  ChevronDown,
  ChevronRight,
  Zap,
  MessageSquare,
  FolderOpen,
  FileText,
  Users,
} from "lucide-react";

interface ApiKey {
  id: string;
  name: string;
  description: string | null;
  key_prefix: string;
  is_active: boolean;
  last_used_at: string | null;
  expires_at: string | null;
  created_at: string;
}

interface ApiKeyCreated extends ApiKey {
  raw_key: string;
}

// ── Endpoint documentation data ────────────────────────
const ENDPOINT_GROUPS = [
  {
    label: "Authentification",
    icon: Key,
    color: "text-violet-600 bg-violet-50 dark:bg-violet-950/30",
    endpoints: [
      {
        method: "POST",
        path: "/api/auth/login",
        summary: "Obtenir un token JWT",
        description: "Retourne access_token + refresh_token.",
        auth: false,
        body: `{ "email": "user@example.com", "password": "Password123!" }`,
        example: `curl -X POST http://localhost:8000/api/auth/login \\
  -H "Content-Type: application/json" \\
  -d '{"email":"admin@legrand-geoai.fr","password":"Admin123!"}'`,
      },
    ],
  },
  {
    label: "Chat RAG (Agent IA)",
    icon: MessageSquare,
    color: "text-brand-600 bg-brand-50 dark:bg-brand-950/30",
    endpoints: [
      {
        method: "POST",
        path: "/api/chat/query",
        summary: "Interroger l'agent IA en streaming SSE",
        description:
          "Envoie une question à l'agent RAG. La réponse est streamée via Server-Sent Events. Appellez directement le port 8000 pour éviter la mise en buffer du proxy Next.js.",
        auth: true,
        body: `{
  "message": "Quelle est la hauteur du bâtiment sur la parcelle 12?",
  "collection_id": "<uuid-collection>",
  "session_id": "<uuid-session>"  // optionnel, pour continuer une conversation
}`,
        example: `curl -N \\
  -H "X-Api-Key: lgai_votreclé..." \\
  -H "Content-Type: application/json" \\
  -H "Accept: text/event-stream" \\
  -X POST http://localhost:8000/api/chat/query \\
  -d '{"message":"Décris le zonage","collection_id":"<uuid>"}'`,
        streaming: true,
      },
      {
        method: "GET",
        path: "/api/chat/sessions",
        summary: "Lister les sessions de chat",
        description: "Retourne les sessions de l'utilisateur paginées.",
        auth: true,
        example: `curl -H "X-Api-Key: lgai_votreclé..." \\
  http://localhost:8000/api/chat/sessions?size=20`,
      },
      {
        method: "GET",
        path: "/api/chat/sessions/{session_id}",
        summary: "Récupérer une session avec tous ses messages",
        auth: true,
        example: `curl -H "X-Api-Key: lgai_votreclé..." \\
  http://localhost:8000/api/chat/sessions/<uuid>`,
      },
      {
        method: "DELETE",
        path: "/api/chat/sessions/{session_id}",
        summary: "Supprimer une session",
        auth: true,
        example: `curl -X DELETE -H "X-Api-Key: lgai_votreclé..." \\
  http://localhost:8000/api/chat/sessions/<uuid>`,
      },
    ],
  },
  {
    label: "Collections",
    icon: FolderOpen,
    color: "text-emerald-600 bg-emerald-50 dark:bg-emerald-950/30",
    endpoints: [
      {
        method: "GET",
        path: "/api/collections",
        summary: "Lister toutes les collections",
        auth: true,
        example: `curl -H "X-Api-Key: lgai_votreclé..." \\
  http://localhost:8000/api/collections`,
      },
      {
        method: "POST",
        path: "/api/collections",
        summary: "Créer une collection",
        auth: true,
        body: `{ "name": "Projet PLU 2024", "description": "..." }`,
        example: `curl -X POST -H "X-Api-Key: lgai_votreclé..." \\
  -H "Content-Type: application/json" \\
  -d '{"name":"Projet PLU 2024"}' \\
  http://localhost:8000/api/collections`,
      },
      {
        method: "DELETE",
        path: "/api/collections/{id}",
        summary: "Supprimer une collection",
        auth: true,
        example: `curl -X DELETE -H "X-Api-Key: lgai_votreclé..." \\
  http://localhost:8000/api/collections/<uuid>`,
      },
    ],
  },
  {
    label: "Documents",
    icon: FileText,
    color: "text-blue-600 bg-blue-50 dark:bg-blue-950/30",
    endpoints: [
      {
        method: "GET",
        path: "/api/documents",
        summary: "Lister les documents",
        auth: true,
        example: `curl -H "X-Api-Key: lgai_votreclé..." \\
  "http://localhost:8000/api/documents?collection_id=<uuid>&page=1&size=20"`,
      },
      {
        method: "POST",
        path: "/api/documents",
        summary: "Uploader un document (PDF / image)",
        description: "Upload multipart. Déclenche l'ingestion et l'indexation en arrière-plan.",
        auth: true,
        example: `curl -X POST -H "X-Api-Key: lgai_votreclé..." \\
  -F "file=@/chemin/vers/fichier.pdf" \\
  -F "collection_id=<uuid>" \\
  http://localhost:8000/api/documents`,
      },
      {
        method: "DELETE",
        path: "/api/documents/{id}",
        summary: "Supprimer un document",
        auth: true,
        example: `curl -X DELETE -H "X-Api-Key: lgai_votreclé..." \\
  http://localhost:8000/api/documents/<uuid>`,
      },
    ],
  },
  {
    label: "Utilisateurs",
    icon: Users,
    color: "text-orange-600 bg-orange-50 dark:bg-orange-950/30",
    endpoints: [
      {
        method: "GET",
        path: "/api/users",
        summary: "Lister les utilisateurs (admin)",
        auth: true,
        example: `curl -H "X-Api-Key: lgai_votreclé..." \\
  http://localhost:8000/api/users`,
      },
      {
        method: "POST",
        path: "/api/users",
        summary: "Créer un utilisateur (admin)",
        auth: true,
        body: `{
  "email": "user@example.com",
  "password": "StrongPass123!",
  "full_name": "Jean Dupont",
  "role": "viewer"
}`,
        example: `curl -X POST -H "X-Api-Key: lgai_votreclé..." \\
  -H "Content-Type: application/json" \\
  -d '{"email":"...","password":"...","full_name":"...","role":"viewer"}' \\
  http://localhost:8000/api/users`,
      },
    ],
  },
];

const METHOD_COLOR: Record<string, string> = {
  GET: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
  POST: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  DELETE: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
  PATCH: "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400",
};

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => {
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }}
      className="rounded p-1 text-surface-400 hover:text-surface-700 dark:hover:text-surface-200"
      title="Copier"
    >
      {copied ? (
        <CheckCheck className="h-4 w-4 text-emerald-500" />
      ) : (
        <Copy className="h-4 w-4" />
      )}
    </button>
  );
}

function EndpointCard({
  endpoint,
}: {
  endpoint: (typeof ENDPOINT_GROUPS)[0]["endpoints"][0];
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-lg border border-surface-200 dark:border-surface-700">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-surface-50 dark:hover:bg-surface-800/50"
      >
        <span
          className={`rounded px-2 py-0.5 text-xs font-bold ${METHOD_COLOR[endpoint.method] || ""}`}
        >
          {endpoint.method}
        </span>
        <code className="flex-1 font-mono text-sm text-surface-700 dark:text-surface-300">
          {endpoint.path}
        </code>
        <span className="text-xs text-surface-500">{endpoint.summary}</span>
        {endpoint.auth && (
          <span title="Authentification requise" className="inline-flex">
            <Key className="h-3.5 w-3.5 text-surface-400" />
          </span>
        )}
        {open ? (
          <ChevronDown className="h-4 w-4 text-surface-400" />
        ) : (
          <ChevronRight className="h-4 w-4 text-surface-400" />
        )}
      </button>

      {open && (
        <div className="border-t border-surface-200 px-4 py-4 space-y-3 dark:border-surface-700">
          {endpoint.description && (
            <p className="text-sm text-surface-600 dark:text-surface-400">
              {endpoint.description}
            </p>
          )}
          {endpoint.streaming && (
            <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
              <Zap className="h-3 w-3" /> Server-Sent Events — réponse streamée
            </span>
          )}
          {endpoint.auth && (
            <p className="text-xs text-surface-500">
              🔐 Nécessite{" "}
              <code className="rounded bg-surface-100 px-1 dark:bg-surface-800">
                X-Api-Key: lgai_...
              </code>{" "}
              ou{" "}
              <code className="rounded bg-surface-100 px-1 dark:bg-surface-800">
                Authorization: Bearer &lt;jwt&gt;
              </code>
            </p>
          )}
          {endpoint.body && (
            <div>
              <p className="mb-1 text-xs font-semibold text-surface-500">Corps (JSON)</p>
              <div className="relative">
                <pre className="overflow-x-auto rounded-lg bg-surface-900 p-3 text-xs text-surface-100 dark:bg-surface-950">
                  {endpoint.body}
                </pre>
                <div className="absolute right-2 top-2">
                  <CopyButton text={endpoint.body} />
                </div>
              </div>
            </div>
          )}
          {endpoint.example && (
            <div>
              <p className="mb-1 flex items-center gap-1 text-xs font-semibold text-surface-500">
                <Terminal className="h-3.5 w-3.5" /> Exemple curl
              </p>
              <div className="relative">
                <pre className="overflow-x-auto rounded-lg bg-surface-900 p-3 text-xs text-surface-100 dark:bg-surface-950">
                  {endpoint.example}
                </pre>
                <div className="absolute right-2 top-2">
                  <CopyButton text={endpoint.example} />
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function ApiPage() {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [newKeyName, setNewKeyName] = useState("");
  const [newKeyDesc, setNewKeyDesc] = useState("");
  const [createdKey, setCreatedKey] = useState<string | null>(null);
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({
    "Chat RAG (Agent IA)": true,
  });

  const { data: keys = [], isLoading } = useQuery({
    queryKey: ["api-keys"],
    queryFn: () => api.get<ApiKey[]>("/api-keys"),
  });

  const createMutation = useMutation({
    mutationFn: (data: { name: string; description?: string }) =>
      api.post<ApiKeyCreated>("/api-keys", data),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["api-keys"] });
      setCreatedKey(data.raw_key);
      setShowCreate(false);
      setNewKeyName("");
      setNewKeyDesc("");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/api-keys/${id}/permanent`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["api-keys"] });
      toast.success("Clé supprimée");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const revokeMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/api-keys/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["api-keys"] });
      toast.success("Clé révoquée");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const toggleGroup = (label: string) =>
    setOpenGroups((prev) => ({ ...prev, [label]: !prev[label] }));

  return (
    <div className="space-y-8">
      {/* ── Header ── */}
      <div>
        <h1 className="text-2xl font-bold text-surface-900 dark:text-surface-50">
          Accès API
        </h1>
        <p className="mt-1 text-sm text-surface-500">
          Gérez vos clés d&apos;API et consultez la documentation des endpoints disponibles.
        </p>
      </div>

      {/* ── Revealed key banner ── */}
      {createdKey && (
        <div className="rounded-xl border border-emerald-300 bg-emerald-50 p-4 dark:border-emerald-700 dark:bg-emerald-950/30">
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1">
              <p className="flex items-center gap-2 text-sm font-semibold text-emerald-700 dark:text-emerald-400">
                <CheckCheck className="h-4 w-4" />
                Clé créée — copiez-la maintenant, elle ne sera plus affichée
              </p>
              <div className="mt-2 flex items-center gap-2">
                <code className="flex-1 break-all rounded-lg bg-white px-3 py-2 font-mono text-sm text-surface-900 dark:bg-surface-900 dark:text-surface-100">
                  {createdKey}
                </code>
                <Button
                  size="icon"
                  variant="outline"
                  onClick={() => {
                    navigator.clipboard.writeText(createdKey);
                    toast.success("Clé copiée !");
                  }}
                >
                  <Copy className="h-4 w-4" />
                </Button>
              </div>
              <p className="mt-2 text-xs text-emerald-600 dark:text-emerald-500">
                Utilisez-la avec le header{" "}
                <code className="rounded bg-emerald-100 px-1 dark:bg-emerald-900/50">
                  X-Api-Key: {createdKey}
                </code>
              </p>
            </div>
            <button
              onClick={() => setCreatedKey(null)}
              className="text-emerald-500 hover:text-emerald-700"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>
      )}

      {/* ── API Keys section ── */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-surface-900 dark:text-surface-50">
            Clés d&apos;API
          </h2>
          <Button onClick={() => setShowCreate(true)} className="gap-2">
            <Plus className="h-4 w-4" />
            Nouvelle clé
          </Button>
        </div>

        {/* Create form */}
        {showCreate && (
          <Card className="animate-fade-in">
            <CardHeader>
              <CardTitle>Créer une clé d&apos;API</CardTitle>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setShowCreate(false)}
              >
                <X className="h-4 w-4" />
              </Button>
            </CardHeader>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                createMutation.mutate({
                  name: newKeyName,
                  description: newKeyDesc || undefined,
                });
              }}
              className="space-y-4 px-6 pb-6"
            >
              <Input
                label="Nom de la clé"
                value={newKeyName}
                onChange={(e) => setNewKeyName(e.target.value)}
                placeholder="ex: Intégration QGIS"
                required
              />
              <Input
                label="Description (optionnelle)"
                value={newKeyDesc}
                onChange={(e) => setNewKeyDesc(e.target.value)}
                placeholder="Usage prévu..."
              />
              <div className="flex justify-end gap-2">
                <Button variant="outline" type="button" onClick={() => setShowCreate(false)}>
                  Annuler
                </Button>
                <Button type="submit" loading={createMutation.isPending}>
                  Créer
                </Button>
              </div>
            </form>
          </Card>
        )}

        {/* Keys list */}
        {isLoading ? (
          <div className="space-y-2">
            {[1, 2].map((i) => (
              <div key={i} className="h-16 animate-pulse rounded-lg bg-surface-200 dark:bg-surface-800" />
            ))}
          </div>
        ) : keys.length === 0 ? (
          <Card className="flex flex-col items-center justify-center py-12">
            <Key className="mb-3 h-10 w-10 text-surface-300" />
            <p className="font-medium text-surface-600">Aucune clé d&apos;API</p>
            <p className="text-sm text-surface-400">
              Créez une clé pour accéder à l&apos;API depuis des outils externes
            </p>
          </Card>
        ) : (
          <div className="overflow-hidden rounded-xl border border-surface-200 bg-white dark:border-surface-700 dark:bg-surface-900">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-surface-200 bg-surface-50 dark:border-surface-700 dark:bg-surface-800/50">
                  <th className="px-4 py-3 text-left font-medium text-surface-600 dark:text-surface-400">Nom</th>
                  <th className="px-4 py-3 text-left font-medium text-surface-600 dark:text-surface-400">Préfixe</th>
                  <th className="px-4 py-3 text-left font-medium text-surface-600 dark:text-surface-400">Statut</th>
                  <th className="px-4 py-3 text-left font-medium text-surface-600 dark:text-surface-400">Dernière utilisation</th>
                  <th className="px-4 py-3 text-left font-medium text-surface-600 dark:text-surface-400">Créée le</th>
                  <th className="px-4 py-3 text-right font-medium text-surface-600 dark:text-surface-400">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-200 dark:divide-surface-700">
                {keys.map((k) => (
                  <tr key={k.id} className="hover:bg-surface-50 dark:hover:bg-surface-800/50">
                    <td className="px-4 py-3">
                      <p className="font-medium text-surface-900 dark:text-surface-100">{k.name}</p>
                      {k.description && (
                        <p className="text-xs text-surface-400">{k.description}</p>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <code className="rounded bg-surface-100 px-2 py-0.5 font-mono text-xs dark:bg-surface-800">
                        {k.key_prefix}
                      </code>
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={k.is_active ? "success" : "danger"}>
                        {k.is_active ? "Active" : "Révoquée"}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-xs text-surface-500">
                      {k.last_used_at ? formatDate(k.last_used_at) : "Jamais"}
                    </td>
                    <td className="px-4 py-3 text-xs text-surface-500">
                      {formatDate(k.created_at)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1">
                        {k.is_active && (
                          <Button
                            variant="ghost"
                            size="icon"
                            title="Révoquer"
                            onClick={() => {
                              if (confirm("Révoquer cette clé ?")) revokeMutation.mutate(k.id);
                            }}
                          >
                            <AlertTriangle className="h-4 w-4 text-amber-500" />
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="icon"
                          title="Supprimer définitivement"
                          onClick={() => {
                            if (confirm("Supprimer définitivement cette clé ?")) {
                              deleteMutation.mutate(k.id);
                            }
                          }}
                        >
                          <Trash2 className="h-4 w-4 text-red-500" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── API Documentation ── */}
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold text-surface-900 dark:text-surface-50">
            Documentation des endpoints
          </h2>
          <Badge variant="info">Base URL : http://localhost:8000</Badge>
        </div>
        <p className="text-sm text-surface-500">
          Tous les endpoints sécurisés acceptent{" "}
          <code className="rounded bg-surface-100 px-1.5 py-0.5 dark:bg-surface-800">
            X-Api-Key: lgai_...
          </code>{" "}
          ou{" "}
          <code className="rounded bg-surface-100 px-1.5 py-0.5 dark:bg-surface-800">
            Authorization: Bearer &lt;jwt&gt;
          </code>
          . Pour le streaming SSE, utilisez toujours le port 8000 directement.
        </p>

        <div className="space-y-4">
          {ENDPOINT_GROUPS.map((group) => (
            <div key={group.label} className="rounded-xl border border-surface-200 dark:border-surface-700">
              <button
                onClick={() => toggleGroup(group.label)}
                className="flex w-full items-center gap-3 px-4 py-3 hover:bg-surface-50 dark:hover:bg-surface-800/50 rounded-xl"
              >
                <div className={`rounded-lg p-2 ${group.color}`}>
                  <group.icon className="h-4 w-4" />
                </div>
                <span className="flex-1 text-left font-semibold text-surface-900 dark:text-surface-100">
                  {group.label}
                </span>
                <span className="rounded-full bg-surface-100 px-2 py-0.5 text-xs text-surface-500 dark:bg-surface-800">
                  {group.endpoints.length} endpoint{group.endpoints.length > 1 ? "s" : ""}
                </span>
                {openGroups[group.label] ? (
                  <ChevronDown className="h-4 w-4 text-surface-400" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-surface-400" />
                )}
              </button>

              {openGroups[group.label] && (
                <div className="space-y-2 border-t border-surface-200 px-4 py-4 dark:border-surface-700">
                  {group.endpoints.map((ep) => (
                    <EndpointCard key={ep.path + ep.method} endpoint={ep} />
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
