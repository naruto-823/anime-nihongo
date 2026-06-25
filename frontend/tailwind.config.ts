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
        // 主调：AIDC 紫（Brand Purple #5C4AFF 色阶）；点缀：樱花粉
        brand: {
          50: "#F1EFFF", 100: "#E4E1FF", 200: "#CFCAFD",
          300: "#B5ADFF", 400: "#8F83FB", 500: "#7465FF",
          600: "#5C4AFF", 700: "#3421DF", 800: "#2A1AB5", 900: "#1F1486",
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
        // AIDC 紫色主题（首页 opt-in，不影响既有 brand/sakura/ink）
        aidc: {
          purple: "#5C4AFF",
          purpleHover: "#7465FF",
          purplePressed: "#3421DF",
          purpleLight: "#E4E1FF",
          ai: "#9239FA",
        },
      },
      backgroundImage: {
        // AIDC 签名 AI 渐变
        aiGradient: "linear-gradient(201.6deg, #9239FA 0%, #5DB1FF 49%, #0454EE 100%)",
        aiGradientBar: "linear-gradient(182.4deg, #9239FA 0%, #5DB1FF 49%, #0454EE 100%)",
      },
      boxShadow: {
        card: "0 1px 2px 0 rgb(15 23 42 / 0.04), 0 1px 4px -1px rgb(15 23 42 / 0.06)",
        cardHover: "0 4px 12px -2px rgb(124 58 237 / 0.12)",
        // AIDC 四档阴影体系（rgba(211,214,219,0.5)）
        aidcL1: "0px 4px 12px 0px rgba(211, 214, 219, 0.5)",
        aidcL2: "0px 4px 12px 4px rgba(211, 214, 219, 0.5)",
        aidcL3: "0px 6px 16px 8px rgba(211, 214, 219, 0.5)",
      },
      borderRadius: {
        card: "0.875rem",  // 14px
        aidc: "1rem",      // 16px (AIDC LG)
      },
      transitionDuration: {
        DEFAULT: "150ms",
      },
    },
  },
  plugins: [],
} satisfies Config;
