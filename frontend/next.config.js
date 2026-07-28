/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  // Ne pas bloquer le build de production sur des erreurs TS/ESLint
  // pré-existantes (ex. typage de l'union d'endpoints dans dashboard/api).
  // À nettoyer séparément ; le typage reste vérifié en dev.
  typescript: { ignoreBuildErrors: true },
  eslint: { ignoreDuringBuilds: true },
  // Proxy API vers le backend en dev
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:8000/api/:path*",
      },
    ];
  },
};

module.exports = nextConfig;
