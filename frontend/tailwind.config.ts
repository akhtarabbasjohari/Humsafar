import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Two-color brand system: Teal #0D9488 + Deep Navy #0F2C3E + Neutrals
        humsafar: {
          teal: "#0D9488", // Primary interactive color (send button, active states)
          tealHover: "#0F766E",
          tealTint: "#F0FDFA", // Pale tint for agent message bubble
          tealBorder: "#CCFBF1", // Hairline border for agent bubble
          navy: "#0F2C3E", // Header, headings, text accents, approval button, source chips
          navyHover: "#183D54",
          navyLight: "#E8EEF2",
          surface: "#FFFFFF", // Base surface and page background
          neutralBg: "#F8FAFC",
          neutralBorder: "#E2E8F0",
          bodyText: "#1E293B",
          mutedText: "#64748B",
        },
      },
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          "'Segoe UI'",
          "Roboto",
          "'Helvetica Neue'",
          "Arial",
          "sans-serif",
        ],
      },
      boxShadow: {
        subtle: "0 1px 2px 0 rgba(15, 44, 62, 0.05)",
        composer: "0 4px 20px -2px rgba(15, 44, 62, 0.08), 0 2px 6px -1px rgba(15, 44, 62, 0.04)",
      },
      maxWidth: {
        chat: "880px", // Spacious modern chat column for itineraries and comparison tables
      },
    },
  },
  plugins: [],
};

export default config;
