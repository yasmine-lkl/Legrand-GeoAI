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
import type { User, PaginatedResponse } from "@/lib/types";
import { Plus, Trash2, UserPlus, Shield, Eye, X, Pencil, Search } from "lucide-react";

const ROLE_CONFIG = {
  admin: { label: "Administrateur", variant: "danger" as const, icon: Shield },
  user: { label: "Utilisateur", variant: "info" as const, icon: UserPlus },
  viewer: { label: "Lecteur", variant: "default" as const, icon: Eye },
};

type EditState = {
  id: string;
  full_name: string;
  email: string;
  role: "admin" | "user" | "viewer";
  is_active: boolean;
  password: string;
};

export default function UsersPage() {
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [editUser, setEditUser] = useState<EditState | null>(null);
  const [search, setSearch] = useState("");
  const [newUser, setNewUser] = useState({
    email: "",
    password: "",
    full_name: "",
    role: "user" as "admin" | "user" | "viewer",
  });

  const { data, isLoading } = useQuery({
    queryKey: ["users"],
    queryFn: () => api.get<PaginatedResponse<User>>("/users?size=100"),
  });

  const createMutation = useMutation({
    mutationFn: (data: typeof newUser) => api.post<User>("/users", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      toast.success("Utilisateur créé");
      setShowCreate(false);
      setNewUser({ email: "", password: "", full_name: "", role: "user" });
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, ...payload }: EditState) => {
      // Only send password if filled
      const body: Record<string, unknown> = {
        full_name: payload.full_name,
        email: payload.email,
        role: payload.role,
        is_active: payload.is_active,
      };
      if (payload.password) body.password = payload.password;
      return api.patch<User>(`/users/${id}`, body);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      toast.success("Utilisateur mis à jour");
      setEditUser(null);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.delete(`/users/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      toast.success("Utilisateur désactivé");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const allUsers = data?.items || [];

  const users = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return allUsers;
    return allUsers.filter(
      (u) =>
        u.full_name.toLowerCase().includes(q) ||
        u.email.toLowerCase().includes(q)
    );
  }, [allUsers, search]);

  const openEdit = (user: User) =>
    setEditUser({
      id: user.id,
      full_name: user.full_name,
      email: user.email,
      role: user.role as "admin" | "user" | "viewer",
      is_active: user.is_active,
      password: "",
    });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-surface-900 dark:text-surface-50">
            Utilisateurs
          </h1>
          <p className="text-sm text-surface-500">
            Gérez les accès à la plateforme
          </p>
        </div>
        <Button onClick={() => setShowCreate(true)} className="gap-2">
          <Plus className="h-4 w-4" />
          Nouvel utilisateur
        </Button>
      </div>

      {/* Create modal */}
      {showCreate && (
        <Card className="animate-fade-in">
          <CardHeader>
            <CardTitle>Créer un utilisateur</CardTitle>
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
              createMutation.mutate(newUser);
            }}
            className="space-y-4 px-6 pb-6"
          >
            <Input
              label="Nom complet"
              value={newUser.full_name}
              onChange={(e) =>
                setNewUser({ ...newUser, full_name: e.target.value })
              }
              placeholder="Jean Dupont"
              required
            />
            <Input
              label="Adresse e-mail"
              type="email"
              value={newUser.email}
              onChange={(e) =>
                setNewUser({ ...newUser, email: e.target.value })
              }
              placeholder="jean.dupont@legrand-geoai.local"
              required
            />
            <Input
              label="Mot de passe"
              type="password"
              value={newUser.password}
              onChange={(e) =>
                setNewUser({ ...newUser, password: e.target.value })
              }
              placeholder="Minimum 8 caractères"
              required
            />
            <div className="space-y-1.5">
              <label className="block text-sm font-medium text-surface-700 dark:text-surface-300">
                Rôle
              </label>
              <select
                value={newUser.role}
                onChange={(e) =>
                  setNewUser({
                    ...newUser,
                    role: e.target.value as "admin" | "user" | "viewer",
                  })
                }
                className="flex h-10 w-full rounded-lg border border-surface-300 bg-white px-3 py-2 text-sm shadow-sm dark:border-surface-600 dark:bg-surface-800"
              >
                <option value="viewer">Lecteur</option>
                <option value="user">Utilisateur</option>
                <option value="admin">Administrateur</option>
              </select>
            </div>
            <div className="flex justify-end gap-2">
              <Button
                variant="outline"
                type="button"
                onClick={() => setShowCreate(false)}
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

      {/* Edit modal */}
      {editUser && (
        <Card className="animate-fade-in">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Pencil className="h-4 w-4" />
              Modifier l&apos;utilisateur
            </CardTitle>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setEditUser(null)}
            >
              <X className="h-4 w-4" />
            </Button>
          </CardHeader>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              updateMutation.mutate(editUser);
            }}
            className="space-y-4 px-6 pb-6"
          >
            <Input
              label="Nom complet"
              value={editUser.full_name}
              onChange={(e) =>
                setEditUser({ ...editUser, full_name: e.target.value })
              }
              required
            />
            <Input
              label="Adresse e-mail"
              type="email"
              value={editUser.email}
              onChange={(e) =>
                setEditUser({ ...editUser, email: e.target.value })
              }
              required
            />
            <Input
              label="Nouveau mot de passe (laisser vide pour ne pas changer)"
              type="password"
              value={editUser.password}
              onChange={(e) =>
                setEditUser({ ...editUser, password: e.target.value })
              }
              placeholder="Minimum 8 caractères"
            />
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="block text-sm font-medium text-surface-700 dark:text-surface-300">
                  Rôle
                </label>
                <select
                  value={editUser.role}
                  onChange={(e) =>
                    setEditUser({
                      ...editUser,
                      role: e.target.value as "admin" | "user" | "viewer",
                    })
                  }
                  className="flex h-10 w-full rounded-lg border border-surface-300 bg-white px-3 py-2 text-sm shadow-sm dark:border-surface-600 dark:bg-surface-800"
                >
                  <option value="viewer">Lecteur</option>
                  <option value="user">Utilisateur</option>
                  <option value="admin">Administrateur</option>
                </select>
              </div>
              <div className="space-y-1.5">
                <label className="block text-sm font-medium text-surface-700 dark:text-surface-300">
                  Statut
                </label>
                <select
                  value={editUser.is_active ? "active" : "inactive"}
                  onChange={(e) =>
                    setEditUser({
                      ...editUser,
                      is_active: e.target.value === "active",
                    })
                  }
                  className="flex h-10 w-full rounded-lg border border-surface-300 bg-white px-3 py-2 text-sm shadow-sm dark:border-surface-600 dark:bg-surface-800"
                >
                  <option value="active">Actif</option>
                  <option value="inactive">Désactivé</option>
                </select>
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <Button
                variant="outline"
                type="button"
                onClick={() => setEditUser(null)}
              >
                Annuler
              </Button>
              <Button type="submit" loading={updateMutation.isPending}>
                Enregistrer
              </Button>
            </div>
          </form>
        </Card>
      )}

      {/* Search bar */}
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-surface-400" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Rechercher par nom ou e-mail…"
          className="w-full rounded-lg border border-surface-300 bg-white py-2 pl-9 pr-4 text-sm shadow-sm placeholder:text-surface-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 dark:border-surface-600 dark:bg-surface-800 dark:text-surface-100"
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

      {/* Table */}
      {isLoading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-16 animate-pulse rounded-lg bg-surface-200 dark:bg-surface-800"
            />
          ))}
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-surface-200 bg-white dark:border-surface-700 dark:bg-surface-900">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-surface-200 bg-surface-50 dark:border-surface-700 dark:bg-surface-800/50">
                <th className="px-4 py-3 text-left font-medium text-surface-600 dark:text-surface-400">
                  Utilisateur
                </th>
                <th className="px-4 py-3 text-left font-medium text-surface-600 dark:text-surface-400">
                  Rôle
                </th>
                <th className="px-4 py-3 text-left font-medium text-surface-600 dark:text-surface-400">
                  Statut
                </th>
                <th className="px-4 py-3 text-left font-medium text-surface-600 dark:text-surface-400">
                  Créé le
                </th>
                <th className="px-4 py-3 text-right font-medium text-surface-600 dark:text-surface-400">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-200 dark:divide-surface-700">
              {users.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-sm text-surface-400">
                    Aucun utilisateur trouvé
                  </td>
                </tr>
              ) : (
                users.map((user) => {
                  const roleConfig = ROLE_CONFIG[user.role as keyof typeof ROLE_CONFIG] ?? ROLE_CONFIG.user;
                  const RoleIcon = roleConfig.icon;
                  return (
                    <tr
                      key={user.id}
                      className="transition-colors hover:bg-surface-50 dark:hover:bg-surface-800/50"
                    >
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-100 text-sm font-semibold text-brand-700 dark:bg-brand-900/30 dark:text-brand-400">
                            {user.full_name.charAt(0).toUpperCase()}
                          </div>
                          <div>
                            <p className="font-medium text-surface-900 dark:text-surface-100">
                              {user.full_name}
                            </p>
                            <p className="text-xs text-surface-500">
                              {user.email}
                            </p>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant={roleConfig.variant}>
                          <RoleIcon className="mr-1 h-3 w-3" />
                          {roleConfig.label}
                        </Badge>
                      </td>
                      <td className="px-4 py-3">
                        <Badge
                          variant={user.is_active ? "success" : "danger"}
                        >
                          {user.is_active ? "Actif" : "Désactivé"}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-xs text-surface-500">
                        {formatDate(user.created_at)}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => openEdit(user)}
                            title="Modifier"
                          >
                            <Pencil className="h-4 w-4 text-surface-500" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => {
                              if (confirm("Désactiver cet utilisateur ?")) {
                                deleteMutation.mutate(user.id);
                              }
                            }}
                            title="Désactiver"
                          >
                            <Trash2 className="h-4 w-4 text-red-500" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
          {search && (
            <p className="border-t border-surface-200 px-4 py-2 text-xs text-surface-400 dark:border-surface-700">
              {users.length} résultat{users.length !== 1 ? "s" : ""} pour &ldquo;{search}&rdquo;
            </p>
          )}
        </div>
      )}
    </div>
  );
}
