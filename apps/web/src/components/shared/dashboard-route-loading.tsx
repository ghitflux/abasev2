"use client";

import { usePathname } from "next/navigation";

import RouteLoadingScreen from "@/components/shared/route-loading-screen";

export default function DashboardRouteLoading() {
  const pathname = usePathname();

  return (
    <RouteLoadingScreen
      variant="dashboard"
      scope="content"
      pathname={pathname}
      label="Carregando modulo..."
    />
  );
}
