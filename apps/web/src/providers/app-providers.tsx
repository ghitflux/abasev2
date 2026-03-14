"use client";

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
          <RouteTransitionProvider>{children}</RouteTransitionProvider>
        </TooltipProvider>
        <Toaster richColors position="top-right" />
      </QueryProvider>
    </ThemeProvider>
  );
}
