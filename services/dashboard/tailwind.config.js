/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        vera: {
          bg: "#0a0a0f",
          card: "rgba(17, 19, 24, 0.55)",
          purple: "#8b5cf6",
          cyan: "#06b6d4",
          red: "#ef4444",
          green: "#10b981",
        },
      },
      fontFamily: {
        mono: ['"JetBrains Mono"', "SFMono-Regular", "Consolas", "Menlo", "monospace"],
      },
      boxShadow: {
        glass: "0 8px 32px rgba(0, 0, 0, 0.35)",
        glowRed: "0 0 32px rgba(239, 68, 68, 0.28)",
      },
    },
  },
  plugins: [],
};
