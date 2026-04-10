// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

// https://astro.build/config
export default defineConfig({
	site: 'https://docs.forgedesk.dev',
	integrations: [
		starlight({
			title: 'ForgeDesk',
			description: 'Build small, fast, secure desktop apps with Python + native webviews.',
			social: [
				{ icon: 'github', label: 'GitHub', href: 'https://github.com/swadhinbiswas/ForgeDesk' }
			],
			sidebar: [
				{
					label: 'Start',
					items: [
						{ label: 'What is ForgeDesk?', slug: 'getting-started' },
						{ label: 'Architecture', slug: 'architecture' },
						{ label: 'Migration from Electron', slug: 'migration-from-electron' },
					],
				},
				{
					label: 'Installation',
					autogenerate: { directory: 'install' },
				},
				{
					label: 'Guides',
					items: [
						{ label: 'Backend Power', slug: 'backend-power' },
						{ label: 'Plugins', slug: 'plugins' },
						{ label: 'Security', slug: 'security' },
					],
				},
				{
					label: 'Frontend',
					autogenerate: { directory: 'frontend' },
				},
				{
					label: 'Reference',
					items: [
						{ label: 'API Reference', slug: 'api-reference' },
					],
				},
				{
					label: 'Blog',
					autogenerate: { directory: 'blog' },
				},
			],
		}),
	],
});
