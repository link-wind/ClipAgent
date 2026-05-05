import type { Config } from 'tailwindcss'

const config: Config = {
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    extend: {
      colors: {
        page: 'var(--page-bg)',
        surface: 'var(--surface)',
        subtle: 'var(--surface-subtle)',
        muted: 'var(--surface-muted)',
        ink: 'var(--ink)',
        primary: 'var(--text-primary)',
        secondary: 'var(--text-secondary)',
        mutedtext: 'var(--text-muted)',
        border: 'var(--border)',
        bordersoft: 'var(--border-soft)',
        accent: 'var(--accent)',
        accentstrong: 'var(--accent-strong)',
        accentink: 'var(--accent-ink)',
        danger: 'var(--danger)',
        infoblue: 'var(--info)',
      },
      boxShadow: {
        soft: 'var(--shadow-soft)',
      },
    },
  },
  plugins: [],
}

export default config
