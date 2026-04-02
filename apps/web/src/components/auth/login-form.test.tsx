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
  it("renderiza o branding novo e o CTA de recuperacao manual", () => {
    render(<LoginForm next="/dashboard" />);

    expect(screen.getByText("Entrar na ABASE")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Sessão do navegador por 48h, com renovação automática via refresh por até 7 dias.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Recuperar senha" }),
    ).toHaveAttribute("href", "/login/recuperar-senha");
    expect(screen.queryByText("Entrar no ABASE v2")).not.toBeInTheDocument();
    expect(screen.getAllByAltText("ABASE")).toHaveLength(2);
  });
});
