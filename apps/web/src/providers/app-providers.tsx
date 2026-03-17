"use client";

import * as React from "react";
import { ThemeProvider } from "next-themes";

import { QueryProvider } from "@/providers/query-provider";
import { RouteTransitionProvider } from "@/providers/route-transition-provider";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";

export function AppProviders({ children }: React.PropsWithChildren) {
  return (
    <ThemeProvider attribute="class" defaultTheme="dark" forcedTheme="dark" enableSystem={false}>
      <QueryProvider>
        <TooltipProvider delayDuration={100}>
          <React.Suspense fallback={null}>
            <RouteTransitionProvider>{children}</RouteTransitionProvider>
          </React.Suspense>
        </TooltipProvider>
        <Toaster richColors position="top-right" />
      </QueryProvider>
    </ThemeProvider>
  );
}
