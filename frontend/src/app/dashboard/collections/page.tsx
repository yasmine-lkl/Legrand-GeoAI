"use client";

import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatDate } from "@/lib/utils";
import toast from "react-hot-toast";
import type { Collection, PaginatedResponse, CollectionCreate } from "@/lib/types";
import { Plus, Trash2, FolderOpen, X, Search } from "lucide-react";

export default function CollectionsPage() {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [search, setSearch] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["collections"],
    queryFn: () =>
      api.get<PaginatedResponse<Collection>>("/collections?size=100"),
  });

  const createMutation = useMutation({
    mutationFn: (data: CollectionCreate) =>
      api.post<Collection>("/collections", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["collections"] });
      toast.success("Collection créée");
      setShowCreate(false);
      setNewName("");
      setNewDesc("");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/collections/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["collections"] });
      toast.success("Collection supprimée");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const collections = data?.items || [];

  const filteredCollections = useMemo(() => {
    if (!search.trim()) return collections;
    const q = search.toLowerCase();
    return collections.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        (c.description && c.description.toLowerCase().includes(q))
    );
  }, [collections, search]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-surface-900 dark:text-surface-50">
            Collections
          </h1>
          <p className="text-sm text-surface-500">
            Organisez vos documents par projet ou thématique
          </p>
        </div>
        <Button onClick={() => setShowCreate(true)} className="gap-2">
          <Plus className="h-4 w-4" />
          Nouvelle collection
        </Button>
      </div>

      {/* Modal create */}
      {showCreate && (
        <Card className="animate-fade-in">
          <CardHeader>
            <CardTitle>Créer une collection</CardTitle>
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
                name: newName,
                description: newDesc || undefined,
              });
            }}
            className="space-y-4"
          >
            <Input
              label="Nom de la collection"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Ex: Projet Grand Lyon 2024"
              required
            />
            <Input
              label="Description (optionnelle)"
              value={newDesc}
              onChange={(e) => setNewDesc(e.target.value)}
              placeholder="Description du projet..."
            />
            <div className="flex justify-end gap-2">
              <Button
                variant="outline"
                onClick={() => setShowCreate(false)}
                type="button"
              >
                Annuler
              </Button>
              <Button type="submit" loading={createMutation.isPending}>
                Créer
              </Button>
            </div>
          </form>
        </Card>
      )}

      {/* Search bar */}
      {collections.length > 0 && (
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-surface-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Rechercher une collection..."
            className="w-full rounded-lg border border-surface-300 bg-white py-2.5 pl-10 pr-10 text-sm shadow-sm transition-colors placeholder:text-surface-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 dark:border-surface-600 dark:bg-surface-800 dark:text-surface-100"
          />
          {search && (
            <button
              onClick={() => setSearch("")}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-surface-400 hover:text-surface-600"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
      )}

      {/* Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-40 animate-pulse rounded-xl bg-surface-200 dark:bg-surface-800"
            />
          ))}
        </div>
      ) : filteredCollections.length === 0 ? (
        <Card className="flex flex-col items-center justify-center py-16">
          <FolderOpen className="mb-3 h-12 w-12 text-surface-300" />
          <p className="text-lg font-medium text-surface-600">
            {search ? "Aucun résultat" : "Aucune collection"}
          </p>
          <p className="text-sm text-surface-400">
            {search
              ? "Essayez avec d'autres termes"
              : "Créez votre première collection pour commencer"}
          </p>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredCollections.map((col) => (
            <Card
              key={col.id}
              className="group transition-shadow hover:shadow-md"
            >
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="rounded-lg bg-brand-50 p-2 dark:bg-brand-950/30">
                    <FolderOpen className="h-5 w-5 text-brand-600 dark:text-brand-400" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-surface-900 dark:text-surface-50">
                      {col.name}
                    </h3>
                    {col.description && (
                      <p className="mt-0.5 text-xs text-surface-500 line-clamp-2">
                        {col.description}
                      </p>
                    )}
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="opacity-0 group-hover:opacity-100"
                  onClick={() => {
                    if (confirm("Supprimer cette collection ?")) {
                      deleteMutation.mutate(col.id);
                    }
                  }}
                >
                  <Trash2 className="h-4 w-4 text-red-500" />
                </Button>
              </div>

              <div className="mt-4 flex items-center justify-between">
                <Badge variant="info">
                  {col.document_count} document{col.document_count !== 1 ? "s" : ""}
                </Badge>
                <span className="text-xs text-surface-400">
                  {formatDate(col.created_at)}
                </span>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
