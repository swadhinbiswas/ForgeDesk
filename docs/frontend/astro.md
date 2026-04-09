# Astro with Forge

Astro is highly recommended for building Forge applications due to its lightweight nature and Zero-JS by default approach. To use Astro with Forge:

## Creation

```bash
npx create-forge-app my-app --template astro
```

## Configure Vite Plugin

To enable auto-reloading and Forge features in Vite/Astro:

```ts
import { defineConfig } from 'astro/config';
import { forge } from '@forge/vite-plugin';

export default defineConfig({
  vite: {
    plugins: [forge()]
  }
});
```

## Client Side Execution
Because Forge apps are static deployments inside the native window, make sure you configure your components as client-side directives:

```html
---
// Component logic
---
<MyReactComponent client:load />
```
