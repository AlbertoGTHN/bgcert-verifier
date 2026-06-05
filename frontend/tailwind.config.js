/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: "class",
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#f0f4ff",
          100: "#dce7ff",
          200: "#c0d1ff",
          300: "#93b2ff",
          400: "#6089fd",
          500: "#3a61fa",
          600: "#2041ef",
          700: "#1832d0",
          800: "#1a2e4a",
          900: "#0f1e31",
          950: "#0a1320",
        },
        verified: {
          DEFAULT: "#16a34a",
          light: "#dcfce7",
          dark: "#14532d",
        },
        failed: {
          DEFAULT: "#dc2626",
          light: "#fee2e2",
          dark: "#7f1d1d",
        },
        technical: {
          DEFAULT: "#d97706",
          light: "#fef3c7",
          dark: "#78350f",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "sans-serif"],
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
      animation: {
        "slide-in": "slideIn 0.3s ease-out",
        "fade-in": "fadeIn 0.2s ease-out",
        "pulse-slow": "pulse 3s infinite",
        "spin-slow": "spin 3s linear infinite",
      },
      keyframes: {
        slideIn: {
          "0%": { transform: "translateX(-100%)", opacity: "0" },
          "100%": { transform: "translateX(0)", opacity: "1" },
        },
        fadeIn: {
          "0%": { opacity: "0", transform: "translateY(4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      boxShadow: {
        glass: "0 4px 30px rgba(0, 0, 0, 0.1)",
        "card-hover": "0 8px 30px rgba(0, 0, 0, 0.12)",
      },
    },
  },
  plugins: [],
};
