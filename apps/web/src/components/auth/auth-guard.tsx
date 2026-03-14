"use client";

import * as React from "react";
import { usePathname, useRouter } from "next/navigation";

import { usePermissions } from "@/hooks/use-permissions";
import { canAccessPath, getDefaultRouteForRole } from "@/lib/navigation";
import { useRouteTransition } from "@/providers/route-transition-provider";
import { Spinner } from "@/components/ui/spinner";

export default function AuthGuard({ children }: React.PropsWithChildren) {
  const router = useRouter();
  const pathname = usePathname();
  const { startRouteTransition } = useRouteTransition();
  const { isAuthenticated, role, roles, status } = usePermissions();
  const isAuthorizedPath = React.useMemo(() => canAccessPath(pathname, roles), [pathname, roles]);

  React.useEffect(() => {
    if (status === "unauthenticated") {
      const loginHref = `/login?next=${encodeURIComponent(pathname)}`;
      startRouteTransition(loginHref);
      router.replace(loginHref);
    }
    if (status === "authenticated" && !isAuthorizedPath) {
      const targetHref = getDefaultRouteForRole(role);
      startRouteTransition(targetHref);
      router.replace(targetHref);
    }
  }, [isAuthorizedPath, pathname, role, router, startRouteTransition, status]);

  if (!isAuthenticated || (status === "authenticated" && !isAuthorizedPath)) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="flex items-center gap-3 rounded-full border border-border/60 bg-card/70 px-4 py-3 text-sm text-muted-foreground shadow-lg shadow-black/20">
          <Spinner />
          Verificando sessão...
        </div>
      </div>
    );
  }

  return children;
}
