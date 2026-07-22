import { http, HttpResponse } from "msw";

/**
 * MSW request handlers.
 *
 * These mock the ShopFlow backend at the network level. Handlers are shared by
 * the browser worker (dev/Storybook) and the Node server (tests), so define
 * them once here. Start with an empty set — endpoints get added alongside the
 * pages/components that consume them.
 *
 * Example:
 *   http.get(`${process.env.NEXT_PUBLIC_API_BASE_URL}/products`, () =>
 *     HttpResponse.json({ items: [], nextCursor: null }),
 *   ),
 */
export const handlers = [
  // Health probe so we can sanity-check the worker is intercepting.
  http.get("/__msw-health", () => HttpResponse.json({ ok: true })),
];
