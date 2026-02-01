/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        'war-room': {
          bg: '#0a0f1c',
          panel: '#111827',
          surface: '#1a2332',
          border: '#1f2937',
          accent: '#3b82f6',
          danger: '#ef4444',
          warning: '#f59e0b',
          success: '#10b981',
          muted: '#6b7280',
          'text-primary': '#f3f4f6',
          'text-secondary': '#9ca3af',
        },
      },
      fontSize: {
        display: ['1.5rem', { lineHeight: '2rem', fontWeight: '700' }],
        heading: ['1.125rem', { lineHeight: '1.5rem', fontWeight: '600' }],
        body: ['0.875rem', { lineHeight: '1.25rem', fontWeight: '400' }],
        caption: ['0.75rem', { lineHeight: '1rem', fontWeight: '400' }],
        mono: ['0.8125rem', { lineHeight: '1.125rem', fontWeight: '400' }],
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Courier New', 'monospace'],
      },
      animation: {
        'pulse-glow': 'pulse-glow 2s ease-in-out infinite',
      },
      keyframes: {
        'pulse-glow': {
          '0%, 100%': { boxShadow: '0 0 5px currentColor, 0 0 10px currentColor' },
          '50%': { boxShadow: '0 0 15px currentColor, 0 0 25px currentColor' },
        },
      },
    },
  },
  plugins: [],
}
