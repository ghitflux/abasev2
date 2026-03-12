"use client";

import * as React from "react";
import { useRouter } from "next/navigation";

import { getLegacyRouteTarget } from "@/lib/navigation";
import { usePermissions } from "@/hooks/use-permissions";
import { Spinner } from "@/components/ui/spinner";

type LegacyRouteRedirectProps = {
  legacyPath: "/pagamentos" | "/renovacoes";
};

export default function LegacyRouteRedirect({ legacyPath }: LegacyRouteRedirectProps) {
  const router = useRouter();
  const { role, status } = usePermissions();

  React.useEffect(() => {
    if (status === "authenticated") {
      router.replace(getLegacyRouteTarget(legacyPath, role));
    }
  }, [legacyPath, role, router, status]);

  return (
    <div className="flex min-h-[40vh] items-center justify-center gap-3 rounded-[1.75rem] border border-border/60 bg-card/60 px-6 py-8 text-sm text-muted-foreground">
      <Spinner />
      Redirecionando para o modulo operacional correto...
    </div>
  );
}
