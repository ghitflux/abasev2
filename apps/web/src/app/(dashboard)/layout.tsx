import AuthGuard from "@/components/auth/auth-guard";
import AppHeader from "@/components/layout/app-header";
import AppSidebar from "@/components/layout/app-sidebar";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";

export default function DashboardLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <AuthGuard>
      <SidebarProvider defaultOpen>
        <AppSidebar />
        <SidebarInset className="min-h-screen bg-transparent">
          <AppHeader />
          <main className="animate-page-enter flex-1 min-w-0 overflow-x-hidden px-4 py-6 md:px-6">{children}</main>
        </SidebarInset>
      </SidebarProvider>
    </AuthGuard>
  );
}
