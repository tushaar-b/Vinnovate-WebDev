/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        obsidian: {
          DEFAULT: '#141210',
          base: '#141210',
          sidebar: '#100F0D',
          dark: '#0C0B0A',
        },
        surface: {
          DEFAULT: '#211D19',
          elevated: '#211D19',
          interactive: '#2A2520',
          hover: '#312B25',
          deep: '#1A1714',
        },
        gold: {
          DEFAULT: '#C5A474',
          champagne: '#C5A474',
          hover: '#D8BB8E',
          soft: '#342B20',
          muted: 'rgba(197, 164, 116, 0.12)',
        },
        ivory: {
          DEFAULT: '#F5EFE5',
          warm: '#F5EFE5',
          muted: '#BDB3A7',
          subtle: '#8F8579',
        },
        warmborder: {
          DEFAULT: '#40372D',
          subtle: '#40372D',
          strong: '#665744',
        },
        status: {
          success: '#34C59A',
          changed: '#E9AD5A',
          error: '#ED7777',
          info: '#8FAAD4',
          neutral: '#A69C90',
        },
        background: '#141210',
        surface: '#211D19',
        ink: '#F5EFE5',
        muted: '#BDB3A7',
        border: '#40372D',
        primary: {
          DEFAULT: '#C5A474',
          hover: '#D8BB8E',
        },
        success: '#34C59A',
        warning: '#E9AD5A',
        error: '#ED7777',
      },
      fontFamily: {
        serif: ['"Playfair Display"', 'Georgia', 'serif'],
        display: ['"Playfair Display"', 'Georgia', 'serif'],
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
      },
      borderRadius: {
        card: '14px',
        panel: '16px',
      },
      boxShadow: {
        luxury: '0 8px 32px 0 rgba(0, 0, 0, 0.45)',
        gold: '0 4px 20px -2px rgba(197, 164, 116, 0.25)',
      },
    },
  },
  plugins: [],
}
