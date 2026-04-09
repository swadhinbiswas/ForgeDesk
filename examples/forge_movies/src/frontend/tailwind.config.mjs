/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{astro,html,js,jsx,md,mdx,svelte,ts,tsx,vue}'],
  theme: {
    extend: {
      colors: {
        background: '#0d0d12',
        surface: '#15151e',
        primary: '#4c3a69',
      }
    },
  },
  plugins: [],
}
