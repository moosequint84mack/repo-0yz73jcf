import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The frontend talks to the FastAPI backend on :8000. In dev we proxy /api and
// /health so the app works from a single origin.
export default defineConfig({
  // The SPA is served under /screener/ in production (the landing page owns /).
  base: "/screener/",
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
      "/health": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
