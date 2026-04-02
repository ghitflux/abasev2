import * as React from "react";
import { render, screen } from "@testing-library/react";

import LoginForm from "@/components/auth/login-form";

jest.mock("next/image", () => ({
  __esModule: true,
  default: ({
    priority: _priority,
    ...props
  }: React.ImgHTMLAttributes<HTMLImageElement> & { priority?: boolean }) => (
    <img {...props} alt={props.alt ?? ""} />
  ),
}));

jest.mock("next/link", () => ({
  __esModule: true,
  default: ({
    href,
    children,
    ...props
  }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

jest.mock("@/providers/route-transition-provider", () => ({
  useRouteTransition: () => ({
    startRouteTransition: jest.fn(),
  }),
}));

jest.mock("@/store/auth-store", () => ({
  useAuthStore: (
    selector: (state: {
      clear: jest.Mock;
      setLoading: jest.Mock;
      setUser: jest.Mock;
    }) => unknown,
  ) =>
    selector({
      clear: jest.fn(),
      setLoading: jest.fn(),
      setUser: jest.fn(),
    }),
}));

describe("LoginForm", () => {
  it("renderiza o login em modo logo-only com recuperar senha e toggle de senha", () => {
    render(<LoginForm next="/dashboard" />);

    expect(screen.queryByText("Entrar na ABASE")).not.toBeInTheDocument();
    expect(screen.queryByText("Entrar no ABASE v2")).not.toBeInTheDocument();
    expect(
      screen.queryByText("Operação, análise e financeiro do associado no mesmo fluxo."),
    ).not.toBeInTheDocument();
    expect(screen.getByPlaceholderText("Digite seu email de acesso")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Digite sua senha")).toBeInTheDocument();
    expect(screen.queryByText("Email")).not.toBeInTheDocument();
    expect(screen.queryByText("Senha")).not.toBeInTheDocument();
    expect(screen.getAllByAltText("ABASE")).toHaveLength(1);
    expect(
      screen.getByRole("link", { name: "Recuperar senha" }),
    ).toHaveAttribute("href", "/login/recuperar-senha");
    expect(
      screen.getByRole("button", { name: "Mostrar senha" }),
    ).toBeInTheDocument();
  });
});
