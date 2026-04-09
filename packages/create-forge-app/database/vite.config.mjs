import { defineConfig } from "vite"
import { forgeVitePlugin } from "@forgedesk/vite-plugin"

export default defineConfig({
  root: "src/frontend",
  plugins: [forgeVitePlugin()],
  build: {
    outDir: "../../dist/static",
    emptyOutDir: true,
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
  },
})
