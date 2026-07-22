"use client";

import { QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";

import { enableMocking, isMockingEnabled } from "@/mocks";
import { getQueryClient } from "@/lib/query-client";

/**
 * App-wide client providers.
 *
 * Wraps children in TanStack Query. When API mocking is enabled
 * (NEXT_PUBLIC_API_MOCKING=enabled) it defers rendering until the MSW worker is
 * ready so no request escapes unmocked. When mocking is off (the default),
 * `ready` starts true and nothing is blocked.
 */
export function Providers({ children }: { children: ReactNode }) {
  const queryClient = getQueryClient();
  const [ready, setReady] = useState(() => !isMockingEnabled());

  useEffect(() => {
    if (ready) return;
    let active = true;
    void enableMocking().then(() => {
      if (active) setReady(true);
    });
    return () => {
      active = false;
    };
  }, [ready]);

  if (!ready) return null;

  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}
