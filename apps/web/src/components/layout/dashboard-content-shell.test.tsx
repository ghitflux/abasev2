import { render, screen } from "@testing-library/react";

import DashboardContentShell from "@/components/layout/dashboard-content-shell";
import { useRouteTransition } from "@/providers/route-transition-provider";

jest.mock("next/navigation", () => ({
  usePathname: jest.fn(),
}));

jest.mock("@/providers/route-transition-provider", () => ({
  useRouteTransition: jest.fn(),
}));

jest.mock("@/components/shared/route-loading-screen", () =>
  jest.fn((props: { pathname?: string | null }) => (
    <div data-testid="dashboard-route-loader">{props.pathname}</div>
  )),
);

const { usePathname } = jest.requireMock("next/navigation") as {
  usePathname: jest.Mock;
};

const mockedUseRouteTransition = jest.mocked(useRouteTransition);

describe("DashboardContentShell", () => {
  beforeEach(() => {
    usePathname.mockReturnValue("/dashboard");
  });

  it("renderiza o loader scoped quando a transição segue dentro do dashboard", () => {
    mockedUseRouteTransition.mockReturnValue({
      isRouteTransitioning: true,
      isRouteLoadingVisible: true,
      pendingHref: "/associados/12",
      startRouteTransition: jest.fn(),
    });

    render(<DashboardContentShell>conteudo</DashboardContentShell>);

    expect(screen.getByTestId("dashboard-route-loader")).toHaveTextContent("/associados/12");
    expect(screen.getByText("conteudo")).toBeInTheDocument();
  });

  it("não renderiza o loader scoped quando o destino não pertence ao dashboard", () => {
    mockedUseRouteTransition.mockReturnValue({
      isRouteTransitioning: true,
      isRouteLoadingVisible: true,
      pendingHref: "/login",
      startRouteTransition: jest.fn(),
    });

    render(<DashboardContentShell>conteudo</DashboardContentShell>);

    expect(screen.queryByTestId("dashboard-route-loader")).not.toBeInTheDocument();
  });
});
