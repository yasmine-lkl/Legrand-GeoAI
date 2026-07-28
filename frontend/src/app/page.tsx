"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth-store";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import type { TokenResponse, User } from "@/lib/types";
import toast from "react-hot-toast";
import {
  MapPin,
  Layers,
  Globe2,
} from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const { setTokens, setUser } = useAuthStore();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      // Login
      const tokens = await api.post<TokenResponse>("/auth/login", {
        email,
        password,
      });

      setTokens(tokens.access_token, tokens.refresh_token);

      // Fetch user
      const user = await api.get<User>("/auth/me");
      setUser(user);

      toast.success(`Bienvenue, ${user.full_name} !`);
      router.push("/dashboard");
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Erreur de connexion";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen">
      {/* Left panel — Branding */}
      <div className="hidden w-1/2 bg-gradient-to-br from-brand-700 via-brand-600 to-brand-800 lg:flex lg:flex-col lg:items-center lg:justify-center">
        <div className="max-w-md space-y-8 px-8 text-center">
          <div className="flex items-center justify-center gap-3">
            <div className="rounded-xl bg-white/10 p-3 backdrop-blur-sm">
              <Globe2 className="h-10 w-10 text-white" />
            </div>
          </div>
          <div>
            <h1 className="text-4xl font-bold text-white">Legrand GeoAI</h1>
            <p className="mt-3 text-lg text-brand-100">
              Agent IA interne - Cabinet Daniel Legrand
            </p>
          </div>
          <div className="grid grid-cols-2 gap-4 pt-4">
            <div className="rounded-xl bg-white/10 p-4 backdrop-blur-sm">
              <MapPin className="mb-2 h-6 w-6 text-brand-200" />
              <p className="text-sm font-medium text-white">Topographie</p>
              <p className="text-xs text-brand-200">
                Plans, levés, MNT
              </p>
            </div>
            <div className="rounded-xl bg-white/10 p-4 backdrop-blur-sm">
              <Layers className="mb-2 h-6 w-6 text-brand-200" />
              <p className="text-sm font-medium text-white">SIG</p>
              <p className="text-xs text-brand-200">
                Cartographie, données
              </p>
            </div>
          </div>
          <p className="text-sm text-brand-200">
            100% local · 100% sécurisé · 100% français
          </p>
        </div>
      </div>

      {/* Right panel — Login form */}
      <div className="flex w-full items-center justify-center px-6 lg:w-1/2">
        <Card className="w-full max-w-md space-y-8 p-8">
          <div className="text-center lg:hidden">
            <div className="mb-3 inline-flex rounded-xl bg-brand-600 p-3">
              <Globe2 className="h-8 w-8 text-white" />
            </div>
            <h1 className="text-2xl font-bold text-surface-900 dark:text-surface-50">
              Legrand GeoAI
            </h1>
          </div>

          <div className="space-y-2">
            <h2 className="text-2xl font-bold text-surface-900 dark:text-surface-50">
              Connexion
            </h2>
            <p className="text-sm text-surface-500">
              Accédez à votre espace documentaire intelligent
            </p>
          </div>

          <form onSubmit={handleLogin} className="space-y-5">
            <Input
              id="email"
              label="Adresse e-mail"
              type="email"
              placeholder="vous@legrand-geoai.local"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoFocus
            />

            <Input
              id="password"
              label="Mot de passe"
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />

            {error && (
              <div className="rounded-lg bg-red-50 p-3 text-sm text-red-600 dark:bg-red-900/20 dark:text-red-400">
                {error}
              </div>
            )}

            <Button type="submit" className="w-full" loading={loading}>
              Se connecter
            </Button>
          </form>
        </Card>
      </div>
    </div>
  );
}
