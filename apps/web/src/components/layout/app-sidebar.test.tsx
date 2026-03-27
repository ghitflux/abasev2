import * as React from "react";
import { render, screen } from "@testing-library/react";
import { useQuery } from "@tanstack/react-query";

import AppSidebar from "@/components/layout/app-sidebar";

jest.mock("@tanstack/react-query", () => ({
  useQuery: jest.fn(() => ({ data: undefined })),
}));

jest.mock("next/navigation", () => ({
  usePathname: () => "/tesouraria/refinanciamentos",
  useRouter: () => ({
    replace: jest.fn(),
    refresh: jest.fn(),
  }),
}));

jest.mock("next/image", () => ({
  __esModule: true,
  default: ({
    priority: _priority,
    ...props
  }: React.ImgHTMLAttributes<HTMLImageElement> & { priority?: boolean }) => (
    <img {...props} alt={props.alt ?? ""} />
  ),
}));

jest.mock("@/lib/navigation", () => ({
  getNavigationForRole: () => [
    {
      title: "Financeiro",
      items: [
        {
          title: "Tesouraria",
          icon: () => <svg data-testid="icon-tesouraria" />,
          children: [
            {
              title: "Renovações",
              href: "/tesouraria/refinanciamentos",
              icon: () => <svg data-testid="icon-renovacoes" />,
            },
            {
              title: "Devoluções",
              href: "/tesouraria/devolucoes",
              icon: () => <svg data-testid="icon-devolucoes" />,
            },
          ],
        },
      ],
    },
  ],
}));

jest.mock("@/hooks/use-permissions", () => ({
  usePermissions: () => ({
    role: "TESOUREIRO",
    roles: ["TESOUREIRO"],
    user: { full_name: "Maria Souza" },
  }),
}));

const mockedUseQuery = jest.mocked(useQuery);

jest.mock("@/providers/route-transition-provider", () => ({
  useRouteTransition: () => ({
    isRouteTransitioning: false,
    isRouteLoadingVisible: false,
    pendingHref: null,
    startRouteTransition: jest.fn(),
  }),
}));

jest.mock("@/store/auth-store", () => ({
  useAuthStore: (selector: (state: { clear: jest.Mock }) => unknown) =>
    selector({ clear: jest.fn() }),
}));

jest.mock("@/components/ui/collapsible", () => ({
  Collapsible: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  CollapsibleContent: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
  CollapsibleTrigger: ({ children }: React.PropsWithChildren) => <>{children}</>,
}));

jest.mock("@/components/ui/sidebar", () => {
  const ReactModule = require("react") as typeof React;

  function cloneChild(
    children: React.ReactNode,
    props: Record<string, unknown>,
  ) {
    if (!ReactModule.isValidElement(children)) {
      return children;
    }

    return ReactModule.cloneElement(
      children as React.ReactElement<Record<string, unknown>>,
      props,
    );
  }

  return {
    Sidebar: ({ children }: React.PropsWithChildren) => <aside>{children}</aside>,
    SidebarContent: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
    SidebarFooter: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
    SidebarGroup: ({ children }: React.PropsWithChildren) => <section>{children}</section>,
    SidebarGroupContent: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
    SidebarGroupLabel: ({ children }: React.PropsWithChildren) => <p>{children}</p>,
    SidebarHeader: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
    SidebarMenu: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
    SidebarMenuBadge: ({ children }: React.PropsWithChildren) => <span>{children}</span>,
    SidebarMenuItem: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
    SidebarMenuSub: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
    SidebarMenuSubItem: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
    SidebarRail: () => <div />,
    SidebarInset: ({ children }: React.PropsWithChildren) => <main>{children}</main>,
    SidebarProvider: ({ children }: React.PropsWithChildren) => <div>{children}</div>,
    SidebarMenuButton: ({
      children,
      asChild,
      isActive,
      ...props
    }: React.PropsWithChildren<{ asChild?: boolean; isActive?: boolean }>) =>
      asChild ? (
        cloneChild(children, { ...props, "data-active": isActive ? "true" : "false" })
      ) : (
        <button data-active={isActive ? "true" : "false"} {...props}>
          {children}
        </button>
      ),
    SidebarMenuSubButton: ({
      children,
      asChild,
      isActive,
      ...props
    }: React.PropsWithChildren<{ asChild?: boolean; isActive?: boolean }>) =>
      asChild ? (
        cloneChild(children, { ...props, "data-active": isActive ? "true" : "false" })
      ) : (
        <button data-active={isActive ? "true" : "false"} {...props}>
          {children}
        </button>
      ),
    useSidebar: () => ({
      state: "expanded",
      toggleSidebar: jest.fn(),
    }),
  };
});

describe("AppSidebar", () => {
  beforeEach(() => {
    mockedUseQuery.mockImplementation(({ queryKey }) => {
      if (Array.isArray(queryKey) && queryKey[0] === "tesouraria-duplicidades-sidebar") {
        return {
          data: {
            count: 3,
            next: null,
            previous: null,
            results: [],
            kpis: {
              total: 3,
              abertas: 3,
              em_tratamento: 0,
              resolvidas: 0,
              descartadas: 0,
            },
          },
        } as never;
      }

      return { data: undefined } as never;
    });
  });

  it("mantém o logo sem compressão e marca o item ativo com animação de slide", () => {
    render(<AppSidebar />);

    const logo = screen.getByAltText("ABASE");
    const activeParent = screen.getByText("Tesouraria");
    const activeChild = screen.getByText("Renovações");

    expect(logo).toHaveClass("w-auto");
    expect(logo).toHaveClass("object-contain");
    expect(activeParent).toHaveAttribute("data-route-title", "active");
    expect(activeParent).toHaveClass("translate-x-1");
    expect(activeChild).toHaveAttribute("data-route-subtitle", "active");
    expect(activeChild).toHaveClass("translate-x-1");
  });

  it("exibe badge de duplicidades abertas na rota de devolucoes", () => {
    render(<AppSidebar />);

    expect(screen.getByText("Devoluções")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
  });
});
