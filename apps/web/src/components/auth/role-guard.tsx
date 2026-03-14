"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import type { Role } from "@abase/shared-types";

import { usePermissions } from "@/hooks/use-permissions";
import { getDefaultRouteForRole } from "@/lib/navigation";
import { useRouteTransition } from "@/providers/route-transition-provider";
import { Spinner } from "@/components/ui/spinner";

type RoleGuardProps = {
  allow: Role[];
  children: React.ReactNode;
  fallbackHref?: string;
};

export default function RoleGuard({ allow, children, fallbackHref }: RoleGuardProps) {
  const router = useRouter();
  const { startRouteTransition } = useRouteTransition();
  const { role, status } = usePermissions();
  const isAllowed = Boolean(role && allow.includes(role));
  const targetHref = fallbackHref ?? getDefaultRouteForRole(role);

  React.useEffect(() => {
    if (status === "authenticated" && !isAllowed) {
      startRouteTransition(targetHref);
      router.replace(targetHref);
    }
  }, [isAllowed, router, startRouteTransition, status, targetHref]);

  if (status !== "authenticated" || !isAllowed) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="flex items-center gap-3 rounded-full border border-border/60 bg-card/70 px-4 py-3 text-sm text-muted-foreground shadow-lg shadow-black/20">
          <Spinner />
          Verificando acesso...
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
