"use client";

import * as React from "react";
import { usePathname } from "next/navigation";

import RouteLoadingScreen from "@/components/shared/route-loading-screen";
import { isDashboardRoute } from "@/lib/dashboard-routes";
import { useRouteTransition } from "@/providers/route-transition-provider";

export default function DashboardContentShell({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const pathname = usePathname();
  const { isRouteLoadingVisible, pendingHref } = useRouteTransition();
  const targetPath = pendingHref ?? pathname;
  const shouldRenderOverlay =
    isRouteLoadingVisible && isDashboardRoute(targetPath);

  return (
    <main className="animate-page-enter relative flex-1 min-w-0 overflow-x-hidden px-4 py-6 md:px-6">
      {shouldRenderOverlay ? (
        <RouteLoadingScreen
          overlay
          variant="dashboard"
          scope="content"
          pathname={targetPath}
          label="Carregando modulo..."
        />
      ) : null}
      {children}
    </main>
  );
}
