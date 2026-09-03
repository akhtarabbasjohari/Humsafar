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
        humsafar: {
          // Required Palette
          header: "#12372A",
          accent: "#D89B32", // logo and icon accent
          approval: "#D89B32", // approval button
          background: "#FFFDF7", // page background
          agentBubble: "#E8F4EF", // agent message bubble
          agentBubbleBorder: "#D0E7DC",
          userBubble: "#FFFFFF", // user message bubble
          userBubbleBorder: "#E8E3D8",
          mainButton: "#0B6B50", // main button
          mainButtonHover: "#08533D",
          approvalHover: "#C48A25",

          // Tonal Variations
          alpineMuted: "#1F4E3D",
          alpineBorder: "#1D4A39",
          slate: "#2C3E35",
          charcoal: "#1A2420",
          mutedText: "#5F7167",
          subtleBorder: "#E3DDD2",
          surfaceParchment: "#FAF6ED",
        },
      },
      fontFamily: {
        sans: ["system-ui", "-apple-system", "BlinkMacSystemFont", "'Segoe UI'", "Roboto", "sans-serif"],
        serif: ["'Playfair Display'", "Georgia", "serif"],
      },
      boxShadow: {
        subtle: "0 1px 3px 0 rgba(18, 55, 42, 0.04), 0 1px 2px -1px rgba(18, 55, 42, 0.04)",
        card: "0 4px 12px 0 rgba(18, 55, 42, 0.05)",
        floating: "0 10px 30px -4px rgba(18, 55, 42, 0.08), 0 4px 12px -2px rgba(18, 55, 42, 0.04)",
      },
    },
  },
  plugins: [],
};

export default config;
