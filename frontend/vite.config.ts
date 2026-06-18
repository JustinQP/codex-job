import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/health": "http://127.0.0.1:8000",
      "/projects": "http://127.0.0.1:8000",
      "/tasks": "http://127.0.0.1:8000",
      "/runners": "http://127.0.0.1:8000",
      "/app-threads": "http://127.0.0.1:8000",
      "/app-turns": "http://127.0.0.1:8000",
      "/app-server-bridge": "http://127.0.0.1:8000",
      "/task-templates": "http://127.0.0.1:8000"
    }
  }
});
