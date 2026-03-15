import { cookies } from "next/headers";

import AuthGuard from "@/components/auth/auth-guard";
import DashboardContentShell from "@/components/layout/dashboard-content-shell";
import AppHeader from "@/components/layout/app-header";
import AppSidebar from "@/components/layout/app-sidebar";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";

export default async function DashboardLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const cookieStore = await cookies();
  const sidebarStateCookie = cookieStore.get("sidebar_state")?.value;
  const defaultOpen = sidebarStateCookie !== "false";

  return (
    <SidebarProvider defaultOpen={defaultOpen}>
      <AppSidebar />
      <SidebarInset className="min-h-screen bg-transparent">
        <AppHeader />
        <AuthGuard>
          <DashboardContentShell>{children}</DashboardContentShell>
        </AuthGuard>
      </SidebarInset>
    </SidebarProvider>
  );
}
