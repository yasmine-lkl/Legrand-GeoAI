"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth-store";
import {
  MessageSquare,
  FolderOpen,
  FileText,
  Users,
  BarChart3,
  Settings,
  Globe2,
  KeyRound,
} from "lucide-react";

const navItems = [
  {
    label: "Chat",
    href: "/dashboard",
    icon: MessageSquare,
  },
  {
    label: "Collections",
    href: "/dashboard/collections",
    icon: FolderOpen,
    adminOnly: true,
  },
  {
    label: "Documents",
    href: "/dashboard/documents",
    icon: FileText,
    adminOnly: true,
  },
  {
    label: "Utilisateurs",
    href: "/dashboard/users",
    icon: Users,
    adminOnly: true,
  },
  {
    label: "API",
    href: "/dashboard/api",
    icon: KeyRound,
    adminOnly: true,
  },
  {
    label: "Statistiques",
    href: "/dashboard/stats",
    icon: BarChart3,
    adminOnly: true,
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const { user } = useAuthStore();

  return (
    <aside className="flex w-64 flex-col border-r border-surface-200 bg-white dark:border-surface-700 dark:bg-surface-900">
      {/* Logo */}
      <div className="flex h-16 items-center gap-3 border-b border-surface-200 px-6 dark:border-surface-700">
        <div className="rounded-lg bg-brand-600 p-1.5">
          <Globe2 className="h-5 w-5 text-white" />
        </div>
        <div>
          <h1 className="text-sm font-bold text-surface-900 dark:text-surface-50">
            Legrand GeoAI
          </h1>
          <p className="text-[10px] text-surface-400">
            Agent IA Géomatique
          </p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4 scrollbar-thin">
        {navItems.map((item) => {
          if (item.adminOnly && user?.role !== "admin") return null;

          const isActive =
            item.href === "/dashboard"
              ? pathname === "/dashboard"
              : pathname.startsWith(item.href);

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                isActive
                  ? "bg-brand-50 text-brand-700 dark:bg-brand-950/50 dark:text-brand-400"
                  : "text-surface-600 hover:bg-surface-100 hover:text-surface-900 dark:text-surface-400 dark:hover:bg-surface-800 dark:hover:text-surface-100"
              )}
            >
              <item.icon
                className={cn(
                  "h-5 w-5",
                  isActive
                    ? "text-brand-600 dark:text-brand-400"
                    : "text-surface-400"
                )}
              />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* User info */}
      <div className="border-t border-surface-200 px-4 py-3 dark:border-surface-700">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-100 text-sm font-semibold text-brand-700 dark:bg-brand-900/30 dark:text-brand-400">
            {user?.full_name?.charAt(0)?.toUpperCase() || "U"}
          </div>
          <div className="flex-1 min-w-0">
            <p className="truncate text-sm font-medium text-surface-900 dark:text-surface-100">
              {user?.full_name || "Utilisateur"}
            </p>
            <p className="truncate text-xs text-surface-500">
              {user?.role === "admin"
                ? "Administrateur"
                : user?.role === "user"
                ? "Utilisateur"
                : "Lecteur"}
            </p>
          </div>
        </div>
      </div>
    </aside>
  );
}
