import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import { forgeVitePlugin } from "@forgedesk/vite-plugin"

export default defineConfig({
  root: "src/frontend",
  plugins: [react(), forgeVitePlugin()],
  build: {
    outDir: "../../dist/static",
    emptyOutDir: true,
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
  },
})
