"use client";

import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth-store";
import { Button } from "@/components/ui/button";
import { LogOut, Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";
import toast from "react-hot-toast";

export function Topbar() {
  const router = useRouter();
  const { user, logout } = useAuthStore();
  const [dark, setDark] = useState(false);

  useEffect(() => {
    const isDark = document.documentElement.classList.contains("dark");
    setDark(isDark);
  }, []);

  const toggleTheme = () => {
    document.documentElement.classList.toggle("dark");
    setDark(!dark);
  };

  const handleLogout = () => {
    logout();
    toast.success("Déconnexion réussie");
    router.push("/");
  };

  return (
    <header className="flex h-16 items-center justify-between border-b border-surface-200 bg-white px-6 dark:border-surface-700 dark:bg-surface-900">
      <div>
        <h2 className="text-lg font-semibold text-surface-900 dark:text-surface-50">
          Bonjour, {user?.full_name?.split(" ")[0] || ""}
        </h2>
        <p className="text-xs text-surface-500">
          Votre assistant documentaire est prêt
        </p>
      </div>

      <div className="flex items-center gap-2">
        <Button
          variant="ghost"
          size="icon"
          onClick={toggleTheme}
          title={dark ? "Mode clair" : "Mode sombre"}
        >
          {dark ? (
            <Sun className="h-5 w-5" />
          ) : (
            <Moon className="h-5 w-5" />
          )}
        </Button>

        <Button
          variant="ghost"
          size="icon"
          onClick={handleLogout}
          title="Déconnexion"
        >
          <LogOut className="h-5 w-5" />
        </Button>
      </div>
    </header>
  );
}
