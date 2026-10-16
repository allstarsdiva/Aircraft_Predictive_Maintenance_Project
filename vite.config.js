import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// This variable is read by the Node-based dev/preview server only. Never use a
// VITE_-prefixed name for the shared API key; VITE_ values enter the browser bundle.
const apiKey = process.env.AIRCRAFT_API_KEY;
const apiProxy = () => ({
  target: process.env.AIRCRAFT_API_TARGET || "http://127.0.0.1:8000",
  changeOrigin: true,
  headers: apiKey ? { "X-API-Key": apiKey } : {},
});

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    strictPort: false,
    proxy: { '/api': apiProxy() },
  },
  preview: { proxy: { '/api': apiProxy() } },
});
