"use client";

import * as React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import {
  DASHBOARD_QUERY_GC_TIME,
  DASHBOARD_QUERY_STALE_TIME,
} from "@/lib/dashboard-query";

export function QueryProvider({ children }: React.PropsWithChildren) {
  const [queryClient] = React.useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: 1,
            staleTime: DASHBOARD_QUERY_STALE_TIME,
            gcTime: DASHBOARD_QUERY_GC_TIME,
            refetchOnWindowFocus: false,
            refetchOnMount: false,
          },
        },
      }),
  );

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
