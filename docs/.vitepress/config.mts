import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'Forge',
  description: 'Forge the future. Ship with Python.',
  cleanUrls: true,
  themeConfig: {
    nav: [
      { text: 'Home', link: '/' },
      { text: 'Guide', link: '/getting-started' },
      { text: 'Frontend Connectors', link: '/frontend/' }
    ],
    sidebar: [
      {
        text: 'Introduction',
        items: [
          { text: 'Getting Started', link: '/getting-started' },
          { text: 'The Python Backend Power', link: '/backend-power' },
          { text: 'Architecture', link: '/architecture' },
          { text: 'Security', link: '/security' }
        ]
      },
      {
        text: 'Frontend Connectors',
        items: [
          { text: 'Overview', link: '/frontend/' },
          { text: 'Astro', link: '/frontend/astro' },
          { text: 'Next.js / React', link: '/frontend/react' },
          { text: 'Nuxt / Vue', link: '/frontend/vue' },
          { text: 'SvelteKit / Svelte', link: '/frontend/svelte' },
          { text: 'SolidJS', link: '/frontend/solid' },
          { text: 'Qwik', link: '/frontend/qwik' },
          { text: 'Angular', link: '/frontend/angular' },
          { text: 'Preact', link: '/frontend/preact' }
        ]
      },
      {
        text: 'API Reference',
        items: [
          { text: 'Python API', link: '/api-reference' },
          { text: 'Plugins', link: '/plugins' }
        ]
      }
    ]
  }
})
