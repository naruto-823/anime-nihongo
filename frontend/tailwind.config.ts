import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        jp: ['"Noto Sans JP"', 'Inter', 'system-ui', 'sans-serif'],
      },
      colors: {
        // 主调：紫罗兰；点缀：樱花粉
        brand: {
          50: "#f5f3ff", 100: "#ede9fe", 200: "#ddd6fe",
          300: "#c4b5fd", 400: "#a78bfa", 500: "#8b5cf6",
          600: "#7c3aed", 700: "#6d28d9", 800: "#5b21b6", 900: "#4c1d95",
        },
        sakura: {
          50: "#fff1f6", 100: "#ffe4ed", 200: "#fbcfe0",
          300: "#f9a8c4", 400: "#f472a6", 500: "#ec4899",
          600: "#db2777", 700: "#be185d",
        },
        ink: {
          50: "#fbfaf9", 100: "#f5f3f0", 200: "#e7e3de",
          300: "#cfc8c0", 400: "#a89e94", 500: "#7a6e63",
          600: "#544a40", 700: "#3d342c", 800: "#2a221c", 900: "#1a1310",
        },
      },
      boxShadow: {
        card: "0 1px 2px 0 rgb(15 23 42 / 0.04), 0 1px 4px -1px rgb(15 23 42 / 0.06)",
        cardHover: "0 4px 12px -2px rgb(124 58 237 / 0.12)",
      },
      borderRadius: {
        card: "0.875rem",  // 14px
      },
      transitionDuration: {
        DEFAULT: "150ms",
      },
    },
  },
  plugins: [],
} satisfies Config;
