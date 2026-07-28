import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/components/providers";

// Pas de next/font/google : l'app est 100% on-premise et le build ne doit pas
// dépendre d'un accès réseau à Google Fonts. On s'appuie sur la pile de polices
// système (Tailwind `font-sans` → Inter si dispo, sinon system-ui).

export const metadata: Metadata = {
  title: "Legrand GeoAI — Agent IA Géomatique",
  description:
    "Assistant IA interne pour la recherche documentaire en géomatique",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="fr" suppressHydrationWarning>
      <body className="font-sans antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
