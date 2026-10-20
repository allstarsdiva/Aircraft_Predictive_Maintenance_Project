import { createSystem, defaultConfig, defineConfig } from "@chakra-ui/react";

/**
 * Chakra UI theme aligned with the app's design tokens. Colours point at the
 * CSS variables, so Chakra tables and progress bars follow light / dark mode.
 * Preflight is off because Tailwind already ships a reset; Chakra is used for
 * a few rich primitives (tables, progress) and must not restyle the page.
 */
const config = defineConfig({
  preflight: false,
  theme: {
    tokens: {
      fonts: {
        body: { value: "'IBM Plex Sans', system-ui, sans-serif" },
        heading: { value: "'Schibsted Grotesk', system-ui, sans-serif" },
        mono: { value: "'IBM Plex Mono', ui-monospace, monospace" },
      },
      colors: {
        ink: { value: "var(--ink)" },
      },
    },
    semanticTokens: {
      colors: {
        bg: { DEFAULT: { value: "var(--card)" }, muted: { value: "var(--hover)" }, subtle: { value: "var(--muted)" } },
        fg: { DEFAULT: { value: "var(--ink)" }, muted: { value: "var(--ink-3)" } },
        border: { DEFAULT: { value: "var(--hairline)" } },
      },
    },
  },
});

export const system = createSystem(defaultConfig, config);
