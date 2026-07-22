import { setupWorker } from "msw/browser";

import { handlers } from "./handlers";

// Browser worker — used in the app (dev, when mocking is enabled) and Storybook.
export const worker = setupWorker(...handlers);
