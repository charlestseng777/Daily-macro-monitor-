/** Colour is reserved for meaning: moves (up/down), risk, surprises, attribution.
 *  Everything else is ink on surface. Values from the validated dark palette. */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        page: '#0b0c0e',
        surface: '#141518',
        raised: '#1b1c20',
        line: '#26272b',
        ink: { DEFAULT: '#f0efec', 2: '#c3c2b7', 3: '#898781' },
        up: '#3987e5',          // move up (diverging blue pole)
        down: '#e66767',        // move down (diverging red pole)
        surprise: '#fab219',    // unusual move / attention
        riskon: '#0ca30c',
        riskoff: '#d03b3b',
      },
      fontFamily: {
        sans: ['system-ui', '-apple-system', 'BlinkMacSystemFont', '"SF Pro Text"', '"Segoe UI"', 'Inter', 'sans-serif'],
        display: ['system-ui', '-apple-system', '"SF Pro Display"', '"Segoe UI"', 'sans-serif'],
      },
      maxWidth: { page: '1440px' },
    },
  },
  plugins: [],
};
