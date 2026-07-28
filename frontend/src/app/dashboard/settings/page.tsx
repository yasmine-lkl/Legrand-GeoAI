"use client";

import { useState } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import toast from "react-hot-toast";
import { User, Lock, Palette } from "lucide-react";

export default function SettingsPage() {
  const { user } = useAuthStore();
  const [fullName, setFullName] = useState(user?.full_name || "");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const handleUpdateProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.patch(`/users/${user?.id}`, { full_name: fullName });
      toast.success("Profil mis à jour");
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Erreur");
    } finally {
      setLoading(false);
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword.length < 8) {
      toast.error("Le mot de passe doit faire au moins 8 caractères");
      return;
    }
    setLoading(true);
    try {
      await api.patch(`/users/${user?.id}`, { password: newPassword });
      toast.success("Mot de passe modifié");
      setCurrentPassword("");
      setNewPassword("");
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Erreur");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-surface-900 dark:text-surface-50">
          Paramètres
        </h1>
        <p className="text-sm text-surface-500">
          Gérez votre profil et vos préférences
        </p>
      </div>

      {/* Profile */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <User className="h-5 w-5 text-surface-400" />
            <CardTitle>Profil</CardTitle>
          </div>
        </CardHeader>
        <form onSubmit={handleUpdateProfile} className="space-y-4">
          <Input
            label="Nom complet"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
          />
          <Input label="E-mail" value={user?.email || ""} disabled />
          <Input
            label="Rôle"
            value={
              user?.role === "admin"
                ? "Administrateur"
                : user?.role === "user"
                ? "Utilisateur"
                : "Lecteur"
            }
            disabled
          />
          <Button type="submit" loading={loading}>
            Enregistrer
          </Button>
        </form>
      </Card>

      {/* Password */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Lock className="h-5 w-5 text-surface-400" />
            <CardTitle>Changer le mot de passe</CardTitle>
          </div>
        </CardHeader>
        <form onSubmit={handleChangePassword} className="space-y-4">
          <Input
            label="Nouveau mot de passe"
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            placeholder="Minimum 8 caractères"
            required
          />
          <Button type="submit" loading={loading}>
            Modifier le mot de passe
          </Button>
        </form>
      </Card>

      {/* Theme */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Palette className="h-5 w-5 text-surface-400" />
            <CardTitle>Apparence</CardTitle>
          </div>
        </CardHeader>
        <div className="flex gap-3">
          <Button
            variant="outline"
            onClick={() =>
              document.documentElement.classList.remove("dark")
            }
          >
            ☀️ Mode clair
          </Button>
          <Button
            variant="outline"
            onClick={() =>
              document.documentElement.classList.add("dark")
            }
          >
            🌙 Mode sombre
          </Button>
        </div>
      </Card>
    </div>
  );
}
