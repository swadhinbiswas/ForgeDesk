import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'Forge',
  description: 'Forge the future. Ship with Python.',
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
          { text: 'Architecture', link: '/architecture' },
          { text: 'Security', link: '/security' }
        ]
      },
      {
        text: 'Frontend Connectors',
        items: [
          { text: 'Overview', link: '/frontend/' },
          { text: 'Astro', link: '/frontend/astro' },
          { text: 'React & Next.js', link: '/frontend/react' },
          { text: 'Vue & Nuxt', link: '/frontend/vue' },
          { text: 'Svelte & SvelteKit', link: '/frontend/svelte' },
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
