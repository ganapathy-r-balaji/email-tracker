"use client";

/**
 * lib/providers.tsx – Client-side React Query provider wrapper.
 *
 * Must be a client component ("use client") because QueryClientProvider
 * uses React context. Imported in the root layout so all pages share
 * a single QueryClient instance.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

export function Providers({ children }: { children: React.ReactNode }) {
  // useState ensures each browser session gets its own QueryClient
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,       // treat data as fresh for 30s
            retry: (failureCount, error: unknown) => {
              const axiosError = error as { response?: { status?: number } };
              // Don't retry on 401 – the user isn't logged in
              if (axiosError?.response?.status === 401) return false;
              return failureCount < 2;
            },
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}
