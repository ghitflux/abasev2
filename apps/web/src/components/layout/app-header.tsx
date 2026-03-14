"use client";

import { startTransition } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { usePermissions } from "@/hooks/use-permissions";
import { useRouteTransition } from "@/providers/route-transition-provider";
import { useAuthStore } from "@/store/auth-store";
import GlobalHeaderSearch from "@/components/layout/global-header-search";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export default function AppHeader() {
  const router = useRouter();
  const { user, role } = usePermissions();
  const { startRouteTransition } = useRouteTransition();
  const clear = useAuthStore((state) => state.clear);

  return (
    <header className="sticky top-0 z-30 border-b border-sidebar-border bg-background/80 px-4 py-3 backdrop-blur md:px-6">
      <div className="flex items-center gap-4">
        <GlobalHeaderSearch className="hidden min-w-0 flex-1 md:block" />
        <div className="ml-auto flex items-center gap-3">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="flex items-center gap-3 rounded-2xl border border-border/60 bg-card/60 px-3 py-2 text-left">
                <Avatar className="size-9 rounded-2xl border border-border/70 bg-primary/20">
                  <AvatarFallback className="rounded-2xl bg-primary/15 text-primary">
                    {user?.full_name
                      ?.split(" ")
                      .slice(0, 2)
                      .map((part) => part[0])
                      .join("") ?? "AB"}
                  </AvatarFallback>
                </Avatar>
                <div className="hidden sm:block">
                  <p className="text-sm font-medium text-foreground">{user?.full_name ?? "Usuário"}</p>
                  <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">{role ?? "sem role"}</p>
                </div>
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="rounded-2xl">
              <DropdownMenuLabel>{user?.email}</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onClick={() => {
                  startRouteTransition("/dashboard");
                  router.push("/dashboard");
                }}
              >
                Dashboard
              </DropdownMenuItem>
              <DropdownMenuItem
                variant="destructive"
                onClick={() => {
                  startTransition(async () => {
                    startRouteTransition("/login");
                    await fetch("/api/auth/logout", { method: "POST" });
                    clear();
                    toast.success("Sessão encerrada.");
                    router.replace("/login");
                    router.refresh();
                  });
                }}
              >
                Sair
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  );
}
