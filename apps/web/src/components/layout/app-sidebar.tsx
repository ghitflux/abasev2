"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { startTransition } from "react";
import Image from "next/image";
import { ChevronRightIcon, LogOutIcon, PanelLeftCloseIcon, PanelLeftOpenIcon } from "lucide-react";
import { toast } from "sonner";

import type { PagamentoAgenteNotificacoes } from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import { getNavigationForRole } from "@/lib/navigation";
import { cn } from "@/lib/utils";
import { usePermissions } from "@/hooks/use-permissions";
import { useRouteTransition } from "@/providers/route-transition-provider";
import { useAuthStore } from "@/store/auth-store";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  SidebarRail,
  useSidebar,
} from "@/components/ui/sidebar";

function isPathActive(pathname: string, href?: string | null) {
  if (!href) {
    return false;
  }

  return pathname === href || pathname.startsWith(`${href}/`);
}

function getAnimatedLabelClass(isActive: boolean) {
  return cn(
    "truncate transition-[opacity,transform] duration-200 ease-out motion-reduce:transform-none motion-reduce:transition-none",
    isActive ? "translate-x-1 opacity-100" : "translate-x-0 opacity-80",
  );
}

export default function AppSidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { state, toggleSidebar } = useSidebar();
  const { role, user } = usePermissions();
  const { startRouteTransition } = useRouteTransition();
  const clear = useAuthStore((s) => s.clear);
  const isCollapsed = state === "collapsed";

  const sections = React.useMemo(() => getNavigationForRole(role), [role]);
  const pagamentoNotificacoesQuery = useQuery({
    queryKey: ["agente-pagamentos-notificacoes"],
    enabled: role === "AGENTE",
    refetchInterval: 30000,
    queryFn: () =>
      apiFetch<PagamentoAgenteNotificacoes>("agente/pagamentos/notificacoes"),
  });
  const routeBadges = React.useMemo<Record<string, number>>(
    () => {
      const badges: Record<string, number> = {};

      if (role === "AGENTE") {
        badges["/agentes/pagamentos"] =
          pagamentoNotificacoesQuery.data?.unread_count ?? 0;
      }

      return badges;
    },
    [pagamentoNotificacoesQuery.data?.unread_count, role],
  );

  // Track which collapsible sections are open (controlled)
  const [openItems, setOpenItems] = React.useState<Record<string, boolean>>(() => {
    const initial: Record<string, boolean> = {};
    sections.forEach((section) => {
      section.items.forEach((item) => {
        if (item.children?.some((child) => isPathActive(pathname, child.href))) {
          initial[item.title] = true;
        }
      });
    });
    return initial;
  });

  // Auto-open the relevant collapsible section when pathname changes
  React.useEffect(() => {
    const updates: Record<string, boolean> = {};
    sections.forEach((section) => {
      section.items.forEach((item) => {
        if (item.children?.some((child) => isPathActive(pathname, child.href))) {
          updates[item.title] = true;
        }
      });
    });
    if (Object.keys(updates).length > 0) {
      setOpenItems((prev) => ({ ...prev, ...updates }));
    }
  }, [pathname, sections]);

  const handleLogout = () => {
    startTransition(async () => {
      startRouteTransition("/login");
      await fetch("/api/auth/logout", { method: "POST" });
      clear();
      toast.success("Sessão encerrada.");
      router.replace("/login");
      router.refresh();
    });
  };

  return (
    <Sidebar collapsible="icon" variant="sidebar">
      {/* ─── Header ─────────────────────────────────────────────── */}
      <SidebarHeader className="border-b border-sidebar-border py-[18px] px-4 group-data-[collapsible=icon]:px-2">
        <div className="flex items-center gap-3 group-data-[collapsible=icon]:justify-center">
          {/* Logo mark — acts as expand toggle when collapsed */}
          <button
            onClick={isCollapsed ? toggleSidebar : undefined}
            aria-label={isCollapsed ? "Expandir sidebar" : undefined}
            className={
              isCollapsed
                ? "flex size-10 shrink-0 cursor-pointer items-center justify-center rounded-xl text-sidebar-foreground/60 transition-all duration-200 hover:bg-sidebar-accent hover:text-sidebar-foreground active:scale-95"
                : "flex h-10 min-w-10 w-auto shrink-0 cursor-default items-center justify-center rounded-xl px-0.5 transition-all duration-200"
            }
          >
            {isCollapsed ? (
              <PanelLeftOpenIcon className="size-5" />
            ) : (
              <Image
                src="/abase-icon.png"
                alt="ABASE"
                width={36}
                height={36}
                className="h-9 w-auto object-contain"
                priority
              />
            )}
          </button>

          {/* Brand + user name (hidden when collapsed) */}
          <div className="min-w-0 flex-1 group-data-[collapsible=icon]:hidden">
            <p className="truncate text-sm font-bold tracking-[0.2em] text-sidebar-foreground">
              ABASE
            </p>
            <p className="truncate text-xs text-sidebar-foreground/55">
              {user?.full_name ?? "Sessão"}
            </p>
          </div>

          {/* Collapse toggle (hidden when collapsed) */}
          <button
            onClick={toggleSidebar}
            aria-label="Recolher sidebar"
            className="shrink-0 rounded-lg p-1.5 text-sidebar-foreground/40 transition-all duration-200 hover:bg-sidebar-accent hover:text-sidebar-foreground active:scale-90 group-data-[collapsible=icon]:hidden"
          >
            <PanelLeftCloseIcon className="size-4" />
          </button>
        </div>
      </SidebarHeader>

      {/* ─── Navigation ─────────────────────────────────────────── */}
      <SidebarContent className="px-3 py-4 group-data-[collapsible=icon]:px-2 [&::-webkit-scrollbar]:hidden [scrollbar-width:none]">
        {sections.map((section) => (
          <SidebarGroup key={section.title}>
            <SidebarGroupLabel>{section.title}</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {section.items.map((item) => {
                  if (item.children?.length) {
                    const isItemActive = item.children.some((child) =>
                      isPathActive(pathname, child.href),
                    );

                    return (
                      <Collapsible
                        key={item.title}
                        className="group/collapsible"
                        open={openItems[item.title] ?? false}
                        onOpenChange={(isOpen) =>
                          setOpenItems((prev) => ({ ...prev, [item.title]: isOpen }))
                        }
                      >
                        <SidebarMenuItem>
                          <CollapsibleTrigger asChild>
                            <SidebarMenuButton
                              tooltip={item.title}
                              isActive={isItemActive}
                              className="transition-all duration-150 hover:translate-x-0.5 active:scale-[0.98]"
                            >
                              <item.icon className="shrink-0 transition-colors duration-150" />
                              {!isCollapsed ? (
                                <span
                                  data-route-title={isItemActive ? "active" : "inactive"}
                                  className={getAnimatedLabelClass(isItemActive)}
                                >
                                  {item.title}
                                </span>
                              ) : null}
                              {!isCollapsed ? (
                                <ChevronRightIcon className="ml-auto size-4 shrink-0 transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90" />
                              ) : null}
                            </SidebarMenuButton>
                          </CollapsibleTrigger>

                          <CollapsibleContent>
                            <SidebarMenuSub>
                              {item.children.map((child) => {
                                const isChildActive = isPathActive(pathname, child.href);
                                const childBadgeCount = child.href
                                  ? routeBadges[child.href] ?? 0
                                  : 0;

                                return (
                                  <SidebarMenuSubItem key={child.href}>
                                    <SidebarMenuSubButton
                                      asChild
                                      isActive={isChildActive}
                                      className="transition-all duration-150 hover:translate-x-0.5 active:scale-[0.98]"
                                    >
                                      <Link href={child.href ?? "#"}>
                                        <span
                                          data-route-subtitle={isChildActive ? "active" : "inactive"}
                                          className={getAnimatedLabelClass(isChildActive)}
                                        >
                                          {child.title}
                                        </span>
                                      </Link>
                                    </SidebarMenuSubButton>
                                    {childBadgeCount > 0 ? (
                                      <SidebarMenuBadge className="rounded-full bg-rose-500/15 px-2 text-rose-200">
                                        {childBadgeCount > 99 ? "99+" : childBadgeCount}
                                      </SidebarMenuBadge>
                                    ) : null}
                                  </SidebarMenuSubItem>
                                );
                              })}
                            </SidebarMenuSub>
                          </CollapsibleContent>
                        </SidebarMenuItem>
                      </Collapsible>
                    );
                  }

                  const isItemActive = isPathActive(pathname, item.href);

                  return (
                    <SidebarMenuItem key={item.href}>
                      {/*
                        Route badges are currently used only for direct links like
                        "Meus Pagamentos" when rendered outside submenus.
                      */}
                      <SidebarMenuButton
                        asChild
                        tooltip={item.title}
                        isActive={isItemActive}
                        className="transition-all duration-150 hover:translate-x-0.5 active:scale-[0.98]"
                      >
                        <Link href={item.href ?? "#"}>
                          <item.icon className="shrink-0" />
                          {!isCollapsed ? (
                            <span
                              data-route-title={isItemActive ? "active" : "inactive"}
                              className={getAnimatedLabelClass(isItemActive)}
                            >
                              {item.title}
                            </span>
                          ) : null}
                        </Link>
                      </SidebarMenuButton>
                      {item.href && (routeBadges[item.href] ?? 0) > 0 ? (
                        <SidebarMenuBadge className="rounded-full bg-rose-500/15 px-2 text-rose-200">
                          {(routeBadges[item.href] ?? 0) > 99
                            ? "99+"
                            : routeBadges[item.href]}
                        </SidebarMenuBadge>
                      ) : null}
                    </SidebarMenuItem>
                  );
                })}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        ))}
      </SidebarContent>

      {/* ─── Footer ─────────────────────────────────────────────── */}
      <SidebarFooter className="border-t border-sidebar-border p-3 group-data-[collapsible=icon]:px-2">
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              onClick={handleLogout}
              tooltip="Sair"
              className="transition-all duration-150 hover:translate-x-0.5 active:scale-[0.98]"
            >
              <LogOutIcon className="shrink-0" />
              {!isCollapsed ? <span>Sair</span> : null}
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>

      <SidebarRail />
    </Sidebar>
  );
}
