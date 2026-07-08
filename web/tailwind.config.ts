import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        sidebar: {
          bg: "var(--sidebar-bg)",
          fg: "var(--sidebar-fg)",
          muted: "var(--sidebar-muted)",
          active: "var(--sidebar-active)",
          hover: "var(--sidebar-hover)",
        },
        surface: {
          DEFAULT: "var(--surface-bg)",
          alt: "var(--surface-alt)",
          border: "var(--surface-border)",
        },
      },
    },
  },
  plugins: [require("@tailwindcss/typography")],
};

export default config;
