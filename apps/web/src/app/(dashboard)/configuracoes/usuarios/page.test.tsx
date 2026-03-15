import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import UsuariosConfiguracoesPage from "./page";
import { apiFetch } from "@/lib/api/client";
import { usePermissions } from "@/hooks/use-permissions";
import { toast } from "sonner";

jest.mock("@/lib/api/client", () => ({
  apiFetch: jest.fn(),
}));

jest.mock("@/hooks/use-permissions", () => ({
  usePermissions: jest.fn(),
}));

jest.mock("@/components/auth/role-guard", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => children,
}));

jest.mock("sonner", () => ({
  toast: {
    success: jest.fn(),
    error: jest.fn(),
  },
}));

const mockedApiFetch = jest.mocked(apiFetch);
const mockedUsePermissions = jest.mocked(usePermissions);
const mockedToast = jest.mocked(toast);

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <UsuariosConfiguracoesPage />
    </QueryClientProvider>,
  );
}

describe("UsuariosConfiguracoesPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();

    const refresh = jest.fn();
    mockedUsePermissions.mockReturnValue({
      user: {
        id: 1,
        email: "admin@abase.local",
        first_name: "Admin",
        last_name: "ABASE",
        full_name: "Admin ABASE",
        primary_role: "ADMIN",
        roles: ["ADMIN"],
      },
      role: "ADMIN",
      roles: ["ADMIN"],
      hasRole: () => true,
      hasAnyRole: () => true,
      status: "authenticated",
      isAuthenticated: true,
      refresh,
      clear: jest.fn(),
    });

    let currentUser = {
      id: 2,
      email: "joana@abase.com",
      first_name: "joana",
      last_name: "",
      full_name: "joana",
      primary_role: "AGENTE",
      roles: ["AGENTE"],
      is_active: true,
      must_set_password: true,
      date_joined: "2026-03-10T12:00:00Z",
      last_login: null,
      is_current_user: false,
    };

    mockedApiFetch.mockImplementation(async (path, options) => {
      if (path === "configuracoes/usuarios") {
        return {
          count: 1,
          next: null,
          previous: null,
          results: [currentUser],
          meta: {
            total: 1,
            ativos: 1,
            admins: 0,
            troca_senha_pendente: currentUser.must_set_password ? 1 : 0,
            available_roles: [{ codigo: "AGENTE", nome: "Agente" }],
          },
        };
      }

      if (path === "configuracoes/usuarios/2/resetar-senha") {
        currentUser = {
          ...currentUser,
          must_set_password: false,
        };

        return {
          detail: "Senha atualizada com sucesso.",
          must_set_password: false,
        };
      }

      throw new Error(`Unexpected apiFetch path: ${path}`);
    });
  });

  it("envia a senha definida pelo admin no reset", async () => {
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByText("joana@abase.com")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /resetar senha/i }));

    await user.type(screen.getByLabelText("Nova senha"), "NovaSenha@123");
    await user.type(screen.getByLabelText("Confirmar nova senha"), "NovaSenha@123");
    await user.click(screen.getByRole("button", { name: /salvar nova senha/i }));

    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith(
        "configuracoes/usuarios/2/resetar-senha",
        expect.objectContaining({
          method: "POST",
          body: {
            password: "NovaSenha@123",
            password_confirm: "NovaSenha@123",
          },
        }),
      ),
    );

    await waitFor(() =>
      expect(mockedToast.success).toHaveBeenCalledWith("Senha atualizada com sucesso."),
    );
  });
});
