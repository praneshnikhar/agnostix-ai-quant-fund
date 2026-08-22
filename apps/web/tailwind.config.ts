import type { Config } from "tailwindcss";

/**
 * Design tokens per documents/16_Design_System_Direction.md.
 * Institutional dark terminal: graphite background, near-black panels,
 * restrained borders, semantic status colors, tabular numerals.
 */
const config: Config = {
  content: [
    "./src/**/*.{ts,tsx}",
    "../../packages/ui/src/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--bg)",
        surface: "var(--surface)",
        elevated: "var(--elevated)",
        border: "var(--border)",
        "border-strong": "var(--border-strong)",
        foreground: "var(--text-primary)",
        muted: "var(--text-secondary)",
        subtle: "var(--text-muted)",
        positive: "var(--positive)",
        negative: "var(--negative)",
        warning: "var(--warning)",
        info: "var(--info)",
        accent: "var(--accent)",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      fontSize: {
        "2xs": ["0.6875rem", { lineHeight: "1rem" }],
      },
    },
  },
  plugins: [],
};

export default config;