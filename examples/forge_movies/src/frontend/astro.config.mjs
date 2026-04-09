import { defineConfig } from 'astro/config';
import { forgeVitePlugin } from '@forge/vite-plugin';
import tailwind from '@astrojs/tailwind';

export default defineConfig({
  integrations: [tailwind()],
  vite: {
    plugins: [forgeVitePlugin()]
  }
});
