# ForgeDesk Documentation

This folder contains the production documentation site for ForgeDesk, built with Astro + Starlight.

## Docs Architecture

- `src/content/docs/install` → installation journey (prerequisites, create project, troubleshooting)
- `src/content/docs/frontend` → frontend-specific integration guides
- `src/content/docs/blog` → release notes and project updates
- `src/content/docs/api-reference.md` → core API reference

## Local Development

```bash
npm install
npm run dev
```

## Build

```bash
npx astro build
```

## Deploy to Cloudflare Pages

Use these settings in Cloudflare Pages:

- Framework preset: `Astro`
- Build command: `npx astro build`
- Build output directory: `docs/dist`
- Root directory: `docs`

If using monorepo builds, set project root to `forge-framework/docs`.
