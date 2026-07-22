import type { Preview } from "@storybook/nextjs-vite";
import { useEffect } from "react";

// Tailwind base + design tokens, so stories render with the real theme.
import "../src/app/globals.css";

const preview: Preview = {
  parameters: {
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },
    a11y: {
      // 'todo' - show a11y violations in the test UI only
      // 'error' - fail CI on a11y violations
      // 'off' - skip a11y checks entirely
      test: "todo",
    },
    backgrounds: { disable: true },
  },
  // Toolbar switch mirroring the app's class-based dark mode.
  globalTypes: {
    theme: {
      description: "Global theme for components",
      toolbar: {
        title: "Theme",
        icon: "circlehollow",
        items: [
          { value: "light", title: "Light", icon: "sun" },
          { value: "dark", title: "Dark", icon: "moon" },
        ],
        dynamicTitle: true,
      },
    },
  },
  initialGlobals: { theme: "light" },
  decorators: [
    (Story, context) => {
      const theme = context.globals.theme as "light" | "dark";
      useEffect(() => {
        const root = document.documentElement;
        root.classList.toggle("dark", theme === "dark");
      }, [theme]);
      return (
        <div className="min-h-24 bg-background p-4 text-foreground">
          <Story />
        </div>
      );
    },
  ],
};

export default preview;
