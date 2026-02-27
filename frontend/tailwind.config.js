/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  safelist: [
    'dark:bg-page',
    'dark:text-content',
    'dark:border-edge',
    'dark:bg-surface',
    'dark:text-primary',
    'bg-page',
    'text-primary',
    'bg-secondary',
    'text-secondary-accent',
  ],
  theme: {
    extend: {
      colors: {
        primary: 'var(--primary-color)',
        'primary-accent': 'var(--primary-color-accent)',
        secondary: 'var(--secondary-color)',
        'secondary-accent': 'var(--secondary-color-accent)',
        default: 'var(--default-color)',
        'primary-dark': 'var(--primary-dark-color)',
        page: 'var(--page-bg-color)',
        content: 'var(--content-color)',
        'content-muted': 'var(--content-muted)',
        edge: 'var(--border-color)',
        surface: 'var(--surface-color)',
      },
    },
  },
  plugins: [],
}
