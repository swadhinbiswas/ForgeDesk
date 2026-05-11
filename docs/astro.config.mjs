// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

// https://astro.build/config
export default defineConfig({
        site: 'https://docs.forgedesk.eu.cc',
        output: 'static',
        integrations: [
                starlight({
                        title: 'ForgeDesk',
                        head: [
                                { tag: 'link', attrs: { rel: 'alternate', type: 'application/rss+xml', title: 'ForgeDesk Blog', href: 'https://docs.forgedesk.eu.cc/rss.xml' } }
                        ],
                        customCss: [
                                './src/styles/custom.css',
                        ],
                        logo: {
                                src: './src/assets/logo.svg',
                        },
                        description: 'Build small, fast, secure desktop apps with Python + native webviews.',
                        social: [
                                { icon: 'github', label: 'GitHub', href: 'https://github.com/swadhinbiswas/ForgeDesk' }
                        ],
                        components: {
                                SocialIcons: './src/components/SiteNavigation.astro',
                        },
                        sidebar: [
                                {
                                        label: 'Getting Started',
                                        autogenerate: { directory: 'quick-start' },
                                },
                                {
                                        label: 'Core Concepts',
                                        autogenerate: { directory: 'core-concepts' },
                                },
                                {
                                        label: 'Guides',
                                        autogenerate: { directory: 'guides' },
                                },
                                {
                                        label: 'Develop',
                                        autogenerate: { directory: 'develop' },
                                },
                                {
                                        label: 'Security',
                                        autogenerate: { directory: 'security' },
                                },
                                {
                                        label: 'Distribute',
                                        autogenerate: { directory: 'distribute' },
                                },
                                {
                                        label: 'Plugins',
                                        autogenerate: { directory: 'plugins' },
                                },
                                {
                                        label: 'Learn',
                                        autogenerate: { directory: 'learn' },
                                },
                                {
                                        label: 'References',
                                        autogenerate: { directory: 'references' },
                                        collapsed: true,
                                },
                        ],
                }),
        ],
});
