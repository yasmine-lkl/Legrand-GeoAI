"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { Collection, Document, PaginatedResponse } from "@/lib/types";
import {
  FolderOpen,
  FileText,
  CheckCircle2,
  AlertCircle,
  Clock,
  Cpu,
  HardDrive,
  Activity,
} from "lucide-react";

export default function StatsPage() {
  const { data: collectionsData } = useQuery({
    queryKey: ["collections"],
    queryFn: () =>
      api.get<PaginatedResponse<Collection>>("/collections?size=100"),
  });

  const { data: docsData } = useQuery({
    queryKey: ["documents-all"],
    queryFn: () =>
      api.get<PaginatedResponse<Document>>("/documents?size=1"),
  });

  const { data: health } = useQuery({
    queryKey: ["health"],
    queryFn: () => api.get<Record<string, unknown>>("/health/ready"),
    retry: false,
  });

  const collections = collectionsData?.items || [];
  const totalDocs = docsData?.total || 0;
  const totalCollections = collections.length;
  const totalDocuments = collections.reduce(
    (acc, c) => acc + c.document_count,
    0
  );

  const services = health as Record<string, unknown> | undefined;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const healthChecks: Record<string, { status?: string }> = (services as any)?.checks || {};

  const statsCards = [
    {
      title: "Collections",
      value: totalCollections,
      icon: FolderOpen,
      color: "text-brand-600 bg-brand-50 dark:bg-brand-950/30 dark:text-brand-400",
    },
    {
      title: "Documents",
      value: totalDocs,
      icon: FileText,
      color: "text-blue-600 bg-blue-50 dark:bg-blue-950/30 dark:text-blue-400",
    },
    {
      title: "Documents indexés",
      value: totalDocuments,
      icon: CheckCircle2,
      color: "text-green-600 bg-green-50 dark:bg-green-950/30 dark:text-green-400",
    },
  ];

  const serviceStatus = [
    { name: "PostgreSQL", key: "postgres", icon: HardDrive },
    { name: "Redis", key: "redis", icon: Clock },
    { name: "Ollama (LLM)", key: "ollama", icon: Cpu },
    { name: "ChromaDB", key: "chromadb", icon: Activity },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-surface-900 dark:text-surface-50">
          Statistiques
        </h1>
        <p className="text-sm text-surface-500">
          Vue d&apos;ensemble du système
        </p>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {statsCards.map((stat) => (
          <Card key={stat.title} className="flex items-center gap-4">
            <div className={`rounded-xl p-3 ${stat.color}`}>
              <stat.icon className="h-6 w-6" />
            </div>
            <div>
              <p className="text-sm text-surface-500">{stat.title}</p>
              <p className="text-2xl font-bold text-surface-900 dark:text-surface-50">
                {stat.value}
              </p>
            </div>
          </Card>
        ))}
      </div>

      {/* Services status */}
      <Card>
        <CardTitle className="mb-4">État des services</CardTitle>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {serviceStatus.map((svc) => {
            const isUp = healthChecks[svc.key]?.status === "ok";
            return (
              <div
                key={svc.key}
                className="flex items-center justify-between rounded-lg border border-surface-200 p-4 dark:border-surface-700"
              >
                <div className="flex items-center gap-3">
                  <svc.icon className="h-5 w-5 text-surface-400" />
                  <span className="font-medium text-surface-900 dark:text-surface-100">
                    {svc.name}
                  </span>
                </div>
                <Badge variant={isUp ? "success" : "danger"}>
                  {isUp ? (
                    <>
                      <CheckCircle2 className="mr-1 h-3 w-3" />
                      En ligne
                    </>
                  ) : (
                    <>
                      <AlertCircle className="mr-1 h-3 w-3" />
                      Hors ligne
                    </>
                  )}
                </Badge>
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
}
