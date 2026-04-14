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

  const noRoles = status === "authenticated" && roles.length === 0;
  const defaultRoute = React.useMemo(() => getDefaultRouteForRole(role), [role]);
  const isOnDefaultRoute = pathname === defaultRoute;

  React.useEffect(() => {
    if (status === "unauthenticated") {
      const loginHref = `/login?next=${encodeURIComponent(pathname)}`;
      startRouteTransition(loginHref);
      router.replace(loginHref);
    }
    // Only redirect if user has roles but current path is not allowed
    // Skip redirect if user has no roles (avoids infinite loop)
    if (status === "authenticated" && !isAuthorizedPath && !noRoles && !isOnDefaultRoute) {
      startRouteTransition(defaultRoute);
      router.replace(defaultRoute);
    }
  }, [isAuthorizedPath, noRoles, isOnDefaultRoute, defaultRoute, pathname, router, startRouteTransition, status]);

  // Still loading / redirecting to login
  if (status === "idle" || status === "loading") {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="flex items-center gap-3 rounded-full border border-border/60 bg-card/70 px-4 py-3 text-sm text-muted-foreground shadow-lg shadow-black/20">
          <Spinner />
          Verificando sessão...
        </div>
      </div>
    );
  }

  // Redirecting to login
  if (status === "unauthenticated") {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="flex items-center gap-3 rounded-full border border-border/60 bg-card/70 px-4 py-3 text-sm text-muted-foreground shadow-lg shadow-black/20">
          <Spinner />
          Redirecionando para login...
        </div>
      </div>
    );
  }

  // Authenticated but no roles assigned — avoid infinite redirect loop
  if (noRoles) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="flex flex-col items-center gap-3 rounded-xl border border-border/60 bg-card/70 px-8 py-6 text-sm shadow-lg shadow-black/20">
          <p className="font-medium text-foreground">Sem permissão de acesso</p>
          <p className="text-muted-foreground">
            Seu usuário não possui nenhuma função atribuída.
          </p>
          <p className="text-muted-foreground">
            Entre em contato com um administrador.
          </p>
        </div>
      </div>
    );
  }

  // Authenticated but not allowed on this path — show spinner while redirect happens
  if (!isAuthorizedPath) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="flex items-center gap-3 rounded-full border border-border/60 bg-card/70 px-4 py-3 text-sm text-muted-foreground shadow-lg shadow-black/20">
          <Spinner />
          Redirecionando...
        </div>
      </div>
    );
  }

  return children;
}
