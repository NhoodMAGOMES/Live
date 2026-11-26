import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}"
  ],
  theme: {
    extend: {
      colors: {
        border: "hsl(var(--border))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        muted: "hsl(var(--muted))",
        accent: "hsl(var(--accent))",
        primary: "hsl(var(--primary))",
        "primary-light": "hsl(var(--primary-light))",
        "primary-extra-light": "hsl(var(--primary-extra-light))",
        danger: "hsl(var(--danger))",
        "danger-light": "hsl(var(--danger-light))",
        "brand-marine": "hsl(var(--brand-marine))",
        "brand-blue": "hsl(var(--brand-blue))",
        "brand-gold": "hsl(var(--brand-gold))",
        "brand-fuchsia": "hsl(var(--brand-fuchsia))"
      }
    }
  },
  plugins: []
};

export default config;
