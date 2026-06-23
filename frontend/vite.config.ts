import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/health": "http://127.0.0.1:8000",
      "/projects": "http://127.0.0.1:8000",
      "/runs": "http://127.0.0.1:8000",
      "/app-threads": "http://127.0.0.1:8000",
      "/app-turns": "http://127.0.0.1:8000",
      "/run-templates": "http://127.0.0.1:8000"
    }
  }
});
