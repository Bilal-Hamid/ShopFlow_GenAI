/**
 * Conditionally starts MSW.
 *
 * Mocking is OFF by default — normal development talks to the real backend.
 * Set `NEXT_PUBLIC_API_MOCKING=enabled` (see .env.example) to intercept
 * requests with the handlers in ./handlers.ts. This is a dynamic import so MSW
 * is never bundled into production when the flag is off.
 */
export async function enableMocking(): Promise<void> {
  if (process.env.NEXT_PUBLIC_API_MOCKING !== "enabled") {
    return;
  }

  if (typeof window === "undefined") {
    const { server } = await import("./server");
    server.listen({ onUnhandledRequest: "bypass" });
  } else {
    const { worker } = await import("./browser");
    await worker.start({ onUnhandledRequest: "bypass" });
  }
}

export function isMockingEnabled(): boolean {
  return process.env.NEXT_PUBLIC_API_MOCKING === "enabled";
}
