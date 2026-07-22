import { setupServer } from "msw/node";

import { handlers } from "./handlers";

// Node server — used in tests (React Testing Library / Vitest, added later).
export const server = setupServer(...handlers);
