"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { startTransition } from "react";
import { ChevronRightIcon, LogOutIcon, PanelLeftCloseIcon, ShieldIcon } from "lucide-react";
import { toast } from "sonner";

import { getNavigationForRole } from "@/lib/navigation";
import { usePermissions } from "@/hooks/use-permissions";
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
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  SidebarRail,
  useSidebar,
} from "@/components/ui/sidebar";

export default function AppSidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { state, toggleSidebar } = useSidebar();
  const { role, user } = usePermissions();
  const clear = useAuthStore((s) => s.clear);
  const isCollapsed = state === "collapsed";

  const sections = React.useMemo(() => getNavigationForRole(role), [role]);

  // Track which collapsible sections are open (controlled)
  const [openItems, setOpenItems] = React.useState<Record<string, boolean>>(() => {
    const initial: Record<string, boolean> = {};
    sections.forEach((section) => {
      section.items.forEach((item) => {
        if (item.children?.some((child) => pathname.startsWith(child.href ?? ""))) {
          initial[item.title] = true;
        }
      });
    });
    return initial;
  });

  const handleLogout = () => {
    startTransition(async () => {
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
      <SidebarHeader className="border-b border-sidebar-border p-4 group-data-[collapsible=icon]:px-2">
        <div className="flex items-center gap-3 group-data-[collapsible=icon]:justify-center">
          {/* Logo mark */}
          <button
            onClick={isCollapsed ? toggleSidebar : undefined}
            className="flex size-10 shrink-0 cursor-pointer items-center justify-center rounded-xl bg-sidebar-primary text-sidebar-primary-foreground shadow-lg shadow-primary/20 transition-all duration-200 hover:brightness-110 hover:shadow-primary/30 active:scale-95"
          >
            <ShieldIcon className="size-5" />
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
      <SidebarContent className="px-3 py-4 group-data-[collapsible=icon]:px-2">
        {sections.map((section) => (
          <SidebarGroup key={section.title}>
            <SidebarGroupLabel>{section.title}</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {section.items.map((item) =>
                  item.children?.length ? (
                    // ── Collapsible group item ──────────────────
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
                            className="transition-all duration-150 hover:translate-x-0.5 active:scale-[0.98]"
                          >
                            <item.icon className="shrink-0 transition-colors duration-150" />
                            {!isCollapsed ? <span className="truncate">{item.title}</span> : null}
                            {!isCollapsed ? (
                              <ChevronRightIcon className="ml-auto size-4 shrink-0 transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90" />
                            ) : null}
                          </SidebarMenuButton>
                        </CollapsibleTrigger>

                        <CollapsibleContent>
                          <SidebarMenuSub>
                            {item.children.map((child) => (
                              <SidebarMenuSubItem key={child.href}>
                                <SidebarMenuSubButton
                                  asChild
                                  isActive={pathname === child.href}
                                  className="transition-all duration-150 hover:translate-x-0.5 active:scale-[0.98]"
                                >
                                  <Link href={child.href ?? "#"}>
                                    <span>{child.title}</span>
                                  </Link>
                                </SidebarMenuSubButton>
                              </SidebarMenuSubItem>
                            ))}
                          </SidebarMenuSub>
                        </CollapsibleContent>
                      </SidebarMenuItem>
                    </Collapsible>
                  ) : (
                    // ── Simple item ────────────────────────────
                    <SidebarMenuItem key={item.href}>
                      <SidebarMenuButton
                        asChild
                        tooltip={item.title}
                        isActive={pathname === item.href}
                        className="transition-all duration-150 hover:translate-x-0.5 active:scale-[0.98]"
                      >
                        <Link href={item.href ?? "#"}>
                          <item.icon className="shrink-0" />
                          {!isCollapsed ? <span className="truncate">{item.title}</span> : null}
                        </Link>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  ),
                )}
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
