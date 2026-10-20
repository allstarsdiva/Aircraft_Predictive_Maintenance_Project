import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // The repository root also has a package-lock.json (the legacy Vite app);
  // pin the workspace root so Turbopack does not guess the wrong one.
  turbopack: { root: path.resolve(process.cwd()) },
  experimental: {
    optimizePackageImports: ["@chakra-ui/react", "lucide-react"],
  },
};

export default nextConfig;
