"use client";

import { useState, useCallback, useMemo, useRef, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useDropzone } from "react-dropzone";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  cn,
  formatDate,
  formatFileSize,
  statusColor,
  statusLabel,
} from "@/lib/utils";
import toast from "react-hot-toast";
import type {
  Document,
  Collection,
  PaginatedResponse,
} from "@/lib/types";
import {
  Upload,
  Trash2,
  FileText,
  FileImage,
  RefreshCw,
  Search,
  Filter,
  ChevronDown,
  X,
} from "lucide-react";

const MIME_ICONS: Record<string, typeof FileText> = {
  "application/pdf": FileText,
  "image/png": FileImage,
  "image/jpeg": FileImage,
  "image/tiff": FileImage,
};

const SUB_STATUS_LABELS: Record<string, string> = {
  validating: "Validation",
  extracting: "Extraction / OCR",
  chunking: "Découpage",
  embedding: "Embeddings",
  storing: "Indexation",
  completed: "Terminé",
  failed: "Échec",
};

/**
 * Affiche la progression d'ingestion en temps réel pour un document en cours.
 * Ouvre un stream SSE Hatchet et met à jour une barre de progression ;
 * à la fin, rafraîchit la liste des documents.
 */
function IngestionProgress({ doc }: { doc: Document }) {
  const queryClient = useQueryClient();
  const [live, setLive] = useState<{
    sub_status?: string | null;
    progress?: number | null;
  } | null>(null);

  useEffect(() => {
    if (doc.status !== "pending" && doc.status !== "processing") return;
    let cancelled = false;

    (async () => {
      try {
        for await (const { event, data } of api.streamDocumentProgress(doc.id)) {
          if (cancelled) break;
          const d = data as {
            sub_status?: string | null;
            progress?: number | null;
          };
          if (event === "progress" || event === "snapshot") {
            setLive({ sub_status: d.sub_status, progress: d.progress });
          } else if (event === "done") {
            setLive({ sub_status: d.sub_status, progress: d.progress });
            if (!cancelled) {
              queryClient.invalidateQueries({ queryKey: ["documents"] });
            }
          }
        }
      } catch {
        // Stream indisponible — le bouton « Actualiser » prend le relais.
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [doc.id, doc.status, queryClient]);

  const progress = live?.progress ?? doc.progress ?? 0;
  const subKey = live?.sub_status ?? doc.sub_status ?? "";
  const label = SUB_STATUS_LABELS[subKey] ?? statusLabel(doc.status);

  return (
    <div className="min-w-[150px]">
      <div className="mb-1 flex items-center justify-between gap-2">
        <span
          className={cn(
            "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
            statusColor(doc.status)
          )}
        >
          {label}
        </span>
        <span className="text-xs tabular-nums text-surface-400">
          {progress}%
        </span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-200 dark:bg-surface-700">
        <div
          className="h-full rounded-full bg-brand-500 transition-all duration-500"
          style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
        />
      </div>
    </div>
  );
}

export default function DocumentsPage() {
  const queryClient = useQueryClient();
  const [selectedCollection, setSelectedCollection] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const [collectionSearch, setCollectionSearch] = useState("");
  const [showCollectionPicker, setShowCollectionPicker] = useState(false);
  const pickerRef = useRef<HTMLDivElement>(null);

  // Fetch collections
  const { data: collectionsData } = useQuery({
    queryKey: ["collections"],
    queryFn: () =>
      api.get<PaginatedResponse<Collection>>("/collections?size=100"),
  });

  // Fetch documents
  const queryParams = new URLSearchParams();
  queryParams.set("page", String(page));
  queryParams.set("size", "20");
  if (selectedCollection)
    queryParams.set("collection_id", selectedCollection);
  if (statusFilter) queryParams.set("status_filter", statusFilter);

  const { data: docsData, isLoading, refetch } = useQuery({
    queryKey: ["documents", page, selectedCollection, statusFilter],
    queryFn: () =>
      api.get<PaginatedResponse<Document>>(
        `/documents?${queryParams.toString()}`
      ),
  });

  // Upload mutation
  const uploadMutation = useMutation({
    mutationFn: async ({
      file,
      collectionId,
    }: {
      file: File;
      collectionId: string;
    }) => {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("collection_id", collectionId);
      return api.upload("/documents", formData);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      queryClient.invalidateQueries({ queryKey: ["collections"] });
      toast.success("Document uploadé — ingestion en cours");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/documents/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents"] });
      queryClient.invalidateQueries({ queryKey: ["collections"] });
      toast.success("Document supprimé");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  // Dropzone
  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      if (!selectedCollection) {
        toast.error("Sélectionnez une collection d'abord");
        return;
      }
      for (const file of acceptedFiles) {
        uploadMutation.mutate({ file, collectionId: selectedCollection });
      }
    },
    [selectedCollection, uploadMutation]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "image/png": [".png"],
      "image/jpeg": [".jpg", ".jpeg"],
      "image/tiff": [".tif", ".tiff"],
      "image/bmp": [".bmp"],
      "image/webp": [".webp"],
    },
    maxSize: 50 * 1024 * 1024,
  });

  const collections = collectionsData?.items || [];
  const documents = docsData?.items || [];
  const totalPages = docsData?.pages || 1;

  const filteredCollections = useMemo(() => {
    if (!collectionSearch.trim()) return collections;
    const q = collectionSearch.toLowerCase();
    return collections.filter((c) => c.name.toLowerCase().includes(q));
  }, [collections, collectionSearch]);

  // Close collection picker on outside click
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

  const selectedCol = collections.find((c) => c.id === selectedCollection);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-surface-900 dark:text-surface-50">
            Documents
          </h1>
          <p className="text-sm text-surface-500">
            Uploadez et gérez vos documents géomatiques
          </p>
        </div>
        <Button
          variant="secondary"
          onClick={() => refetch()}
          className="gap-2"
        >
          <RefreshCw className="h-4 w-4" />
          Actualiser
        </Button>
      </div>

      {/* Drop zone */}
      <div
        {...getRootProps()}
        className={cn(
          "cursor-pointer rounded-xl border-2 border-dashed p-8 text-center transition-colors",
          isDragActive
            ? "border-brand-500 bg-brand-50 dark:bg-brand-950/20"
            : "border-surface-300 bg-white hover:border-brand-400 hover:bg-surface-50 dark:border-surface-600 dark:bg-surface-900 dark:hover:bg-surface-800"
        )}
      >
        <input {...getInputProps()} />
        <Upload
          className={cn(
            "mx-auto mb-3 h-10 w-10",
            isDragActive ? "text-brand-500" : "text-surface-400"
          )}
        />
        <p className="text-sm font-medium text-surface-700 dark:text-surface-300">
          {isDragActive
            ? "Déposez les fichiers ici..."
            : "Glissez-déposez vos fichiers ici, ou cliquez pour sélectionner"}
        </p>
        <p className="mt-1 text-xs text-surface-400">
          PDF, PNG, JPEG, TIFF, BMP, WEBP — Max 50 Mo
        </p>
        {!selectedCollection && (
          <p className="mt-2 text-xs text-yellow-600 dark:text-yellow-400">
            ⚠ Sélectionnez une collection ci-dessous avant d&apos;uploader
          </p>
        )}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-surface-400" />
          <div className="relative" ref={pickerRef}>
            <button
              onClick={() => {
                setShowCollectionPicker(!showCollectionPicker);
                setCollectionSearch("");
              }}
              className="flex items-center gap-2 rounded-lg border border-surface-300 bg-white px-3 py-2 text-sm shadow-sm hover:bg-surface-50 dark:border-surface-600 dark:bg-surface-800 dark:hover:bg-surface-700"
            >
              <FileText className="h-4 w-4 text-surface-400" />
              {selectedCol ? selectedCol.name : "Toutes les collections"}
              <ChevronDown className="h-4 w-4 text-surface-400" />
            </button>

            {showCollectionPicker && (
              <div className="absolute left-0 top-full z-50 mt-1 w-72 rounded-lg border border-surface-200 bg-white shadow-lg dark:border-surface-700 dark:bg-surface-800">
                {/* Search input */}
                <div className="flex items-center gap-2 border-b border-surface-200 px-3 py-2 dark:border-surface-700">
                  <Search className="h-4 w-4 text-surface-400" />
                  <input
                    type="text"
                    value={collectionSearch}
                    onChange={(e) => setCollectionSearch(e.target.value)}
                    placeholder="Rechercher..."
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
                  {/* "All collections" option */}
                  <button
                    onClick={() => {
                      setSelectedCollection("");
                      setShowCollectionPicker(false);
                      setPage(1);
                    }}
                    className={cn(
                      "flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm hover:bg-surface-100 dark:hover:bg-surface-700",
                      !selectedCollection &&
                        "bg-brand-50 text-brand-700 dark:bg-brand-950/50 dark:text-brand-400"
                    )}
                  >
                    Toutes les collections
                  </button>
                  {filteredCollections.map((col) => (
                    <button
                      key={col.id}
                      onClick={() => {
                        setSelectedCollection(col.id);
                        setShowCollectionPicker(false);
                        setPage(1);
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
                      Aucun résultat
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setPage(1);
          }}
          className="rounded-lg border border-surface-300 bg-white px-3 py-2 text-sm dark:border-surface-600 dark:bg-surface-800"
        >
          <option value="">Tous les statuts</option>
          <option value="pending">En attente</option>
          <option value="processing">Traitement</option>
          <option value="completed">Terminé</option>
          <option value="failed">Échec</option>
        </select>

        <Badge>{docsData?.total || 0} documents</Badge>
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="space-y-3">
          {[1, 2, 3, 4, 5].map((i) => (
            <div
              key={i}
              className="h-16 animate-pulse rounded-lg bg-surface-200 dark:bg-surface-800"
            />
          ))}
        </div>
      ) : documents.length === 0 ? (
        <Card className="flex flex-col items-center justify-center py-16">
          <FileText className="mb-3 h-12 w-12 text-surface-300" />
          <p className="text-lg font-medium text-surface-600">
            Aucun document
          </p>
          <p className="text-sm text-surface-400">
            Uploadez votre premier document pour commencer
          </p>
        </Card>
      ) : (
        <div className="overflow-hidden rounded-xl border border-surface-200 bg-white dark:border-surface-700 dark:bg-surface-900">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-surface-200 bg-surface-50 dark:border-surface-700 dark:bg-surface-800/50">
                <th className="px-4 py-3 text-left font-medium text-surface-600 dark:text-surface-400">
                  Document
                </th>
                <th className="px-4 py-3 text-left font-medium text-surface-600 dark:text-surface-400">
                  Collection
                </th>
                <th className="px-4 py-3 text-left font-medium text-surface-600 dark:text-surface-400">
                  Taille
                </th>
                <th className="px-4 py-3 text-left font-medium text-surface-600 dark:text-surface-400">
                  Statut
                </th>
                <th className="px-4 py-3 text-left font-medium text-surface-600 dark:text-surface-400">
                  Chunks
                </th>
                <th className="px-4 py-3 text-left font-medium text-surface-600 dark:text-surface-400">
                  Date
                </th>
                <th className="px-4 py-3 text-right font-medium text-surface-600 dark:text-surface-400">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-200 dark:divide-surface-700">
              {documents.map((doc) => {
                const Icon = MIME_ICONS[doc.mime_type] || FileText;
                return (
                  <tr
                    key={doc.id}
                    className="transition-colors hover:bg-surface-50 dark:hover:bg-surface-800/50"
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <Icon className="h-5 w-5 text-surface-400" />
                        <div>
                          <p className="font-medium text-surface-900 dark:text-surface-100">
                            {doc.original_filename}
                          </p>
                          {doc.ocr_method && (
                            <p className="text-xs text-surface-400">
                              OCR: {doc.ocr_method}
                            </p>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-surface-600 dark:text-surface-400">
                      {doc.collection_name || "—"}
                    </td>
                    <td className="px-4 py-3 text-surface-600 dark:text-surface-400">
                      {formatFileSize(doc.file_size)}
                    </td>
                    <td className="px-4 py-3">
                      {doc.status === "pending" ||
                      doc.status === "processing" ? (
                        <IngestionProgress doc={doc} />
                      ) : (
                        <span
                          className={cn(
                            "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
                            statusColor(doc.status)
                          )}
                        >
                          {statusLabel(doc.status)}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-surface-600 dark:text-surface-400">
                      {doc.chunk_count ?? "—"}
                    </td>
                    <td className="px-4 py-3 text-xs text-surface-500">
                      {formatDate(doc.created_at)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => {
                          if (confirm("Supprimer ce document ?")) {
                            deleteMutation.mutate(doc.id);
                          }
                        }}
                      >
                        <Trash2 className="h-4 w-4 text-red-500" />
                      </Button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between border-t border-surface-200 px-4 py-3 dark:border-surface-700">
              <p className="text-xs text-surface-500">
                Page {page} sur {totalPages}
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                >
                  Précédent
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Suivant
                </Button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
