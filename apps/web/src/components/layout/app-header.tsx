"use client";

import { format } from "date-fns";
import { ptBR } from "date-fns/locale";
import { BellIcon, SearchIcon } from "lucide-react";
import { startTransition } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { ROLES } from "@abase/shared-types";

import { usePermissions } from "@/hooks/use-permissions";
import { useAuthStore } from "@/store/auth-store";
import FilterAdvanced from "@/components/shared/filter-advanced";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { SidebarTrigger } from "@/components/ui/sidebar";

const roleOptions = ROLES.map((value) => ({
  value,
  label: value.charAt(0) + value.slice(1).toLowerCase(),
}));

const statusOptions = [
  { value: "ativo", label: "Ativo" },
  { value: "em_analise", label: "Em analise" },
  { value: "pendente", label: "Pendente" },
  { value: "inadimplente", label: "Inadimplente" },
];

export default function AppHeader() {
  const router = useRouter();
  const { user, role } = usePermissions();
  const clear = useAuthStore((state) => state.clear);
  const today = format(new Date(), "EEEE, d 'de' MMMM", { locale: ptBR });

  return (
    <header className="sticky top-0 z-30 border-b border-sidebar-border bg-background/80 px-4 py-3 backdrop-blur md:px-6">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex items-center gap-3">
          <SidebarTrigger className="rounded-2xl border border-border/60 bg-card/70" />
          <div className="relative hidden w-full max-w-md md:block">
            <SearchIcon className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input className="rounded-2xl border-border/60 bg-card/60 pl-9" placeholder="Buscar associado, matrícula ou órgão..." />
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <FilterAdvanced
            roleOptions={roleOptions}
            statusOptions={statusOptions}
            onApply={(filters) => {
              toast.success(
                `Filtros aplicados: ${filters.statuses.length} status, ${filters.role ?? "sem papel"}, ${filters.dateRange?.from ? "com período" : "sem período"}.`,
              );
            }}
          />
          <div className="hidden rounded-2xl border border-border/60 bg-card/60 px-4 py-2 text-sm text-muted-foreground lg:block">
            {today}
          </div>
          <Button variant="outline" size="icon" className="rounded-2xl">
            <BellIcon className="size-4" />
          </Button>
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
              <DropdownMenuItem onClick={() => router.push("/dashboard")}>Dashboard</DropdownMenuItem>
              <DropdownMenuItem
                variant="destructive"
                onClick={() => {
                  startTransition(async () => {
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
