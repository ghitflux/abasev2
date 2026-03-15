"use client";

import * as React from "react";
import { useRouter } from "next/navigation";

import { getLegacyRouteTarget } from "@/lib/navigation";
import { usePermissions } from "@/hooks/use-permissions";
import { useRouteTransition } from "@/providers/route-transition-provider";
import { Skeleton } from "@/components/ui/skeleton";

type LegacyRouteRedirectProps = {
  legacyPath: "/pagamentos" | "/renovacoes";
};

export default function LegacyRouteRedirect({ legacyPath }: LegacyRouteRedirectProps) {
  const router = useRouter();
  const { startRouteTransition } = useRouteTransition();
  const { role, status } = usePermissions();

  React.useEffect(() => {
    if (status === "authenticated") {
      const targetHref = getLegacyRouteTarget(legacyPath, role);
      startRouteTransition(targetHref);
      router.replace(targetHref);
    }
  }, [legacyPath, role, router, startRouteTransition, status]);

  return (
    <div className="mx-auto flex min-h-[40vh] max-w-3xl items-center justify-center">
      <div className="w-full rounded-[1.75rem] border border-border/60 bg-card/70 p-6 shadow-xl shadow-black/15">
        <div className="space-y-3">
          <Skeleton className="h-5 w-40" />
          <Skeleton className="h-4 w-full max-w-xl" />
          <Skeleton className="h-11 w-full rounded-2xl" />
        </div>
      </div>
    </div>
  );
}
