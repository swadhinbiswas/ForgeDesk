# Frontend Connectors

Forge is frontend-agnostic, much like Tauri or Electron. The Forge architecture expects a separated Python backend and an HTML/JS/CSS frontend. During the build process, the frontend is compiled to static files and served by the Forge Rust core securely.

Forge officially supports and provides scaffolding for:
- [Astro](/frontend/astro)
- [React & Next.js](/frontend/react)
- [Vue & Nuxt](/frontend/vue)
- [Svelte & SvelteKit](/frontend/svelte)
- [SolidJS](/frontend/solid)
- [Qwik](/frontend/qwik)
- [Angular](/frontend/angular)
- [Preact](/frontend/preact)

## Inter-Process Communication (IPC)

Connecting your frontend to the Python backend requires our lightweight `@forge/api` package, which works universally across all web frameworks.

```bash
npm install @forge/api
```
