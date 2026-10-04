/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        atlas: '#14213D',
        lagoon: '#1E6F6D',
        sun: '#F4C95D',
        coral: '#F07167',
        paper: '#F8F7F2',
        mist: '#DDE8E7',
      },
      fontFamily: {
        display: ['Fraunces', 'Georgia', 'serif'],
        sans: ['Manrope', 'Avenir Next', 'sans-serif'],
      },
      boxShadow: {
        lift: '0 18px 50px rgba(20, 33, 61, 0.12)',
      },
    },
  },
  plugins: [],
}
