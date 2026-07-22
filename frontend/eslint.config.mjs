// For more info, see https://github.com/storybookjs/eslint-plugin-storybook#configuration-flat-config-format
import storybook from "eslint-plugin-storybook";

import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";
// Disables ESLint rules that conflict with Prettier. Must come last.
import prettier from "eslint-config-prettier";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    // Generated MSW worker script.
    "public/mockServiceWorker.js",
    // Build/output artifacts.
    "storybook-static/**",
    "coverage/**",
  ]),
  ...storybook.configs["flat/recommended"],
  // eslint-config-prettier disables stylistic rules; keep it last so it wins.
  prettier,
]);

export default eslintConfig;
