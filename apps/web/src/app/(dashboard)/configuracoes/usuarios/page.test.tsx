import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
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

    let currentUsers = [
      {
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
      },
    ];

    mockedApiFetch.mockImplementation(async (path, options) => {
      if (path === "configuracoes/usuarios" && !options?.method) {
        return {
          count: currentUsers.length,
          next: null,
          previous: null,
          results: currentUsers,
          meta: {
            total: currentUsers.length,
            ativos: currentUsers.filter((user) => user.is_active).length,
            admins: 0,
            troca_senha_pendente: currentUsers.filter((user) => user.must_set_password).length,
            available_roles: [
              { codigo: "AGENTE", nome: "Agente" },
              { codigo: "ANALISTA", nome: "Analista" },
            ],
          },
        };
      }

      if (path === "configuracoes/usuarios" && options?.method === "POST") {
        const body = options.body as {
          email: string;
          first_name: string;
          last_name: string;
          roles: string[];
        };
        const createdUser = {
          id: 3,
          email: body.email,
          first_name: body.first_name,
          last_name: body.last_name,
          full_name: `${body.first_name} ${body.last_name}`.trim(),
          primary_role: body.roles[0],
          roles: body.roles,
          is_active: true,
          must_set_password: true,
          date_joined: "2026-03-11T12:00:00Z",
          last_login: null,
          is_current_user: false,
        };
        currentUsers = [...currentUsers, createdUser];
        return createdUser;
      }

      if (path === "configuracoes/usuarios/2/resetar-senha") {
        currentUsers = currentUsers.map((user) =>
          user.id === 2 ? { ...user, must_set_password: false } : user,
        );

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

  it("cria um novo usuario interno", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: /novo usu[aá]rio/i }));
    const dialog = screen.getByRole("dialog");

    await user.type(within(dialog).getByLabelText("Nome"), "Maria");
    await user.type(within(dialog).getByLabelText("Sobrenome"), "Coord");
    await user.type(within(dialog).getByLabelText("E-mail"), "maria@abase.com");
    await user.click(within(dialog).getByText("Agente"));
    await user.type(within(dialog).getByLabelText("Senha temporária"), "SenhaTemp@123");
    await user.type(within(dialog).getByLabelText("Confirmar senha"), "SenhaTemp@123");
    await user.click(within(dialog).getByRole("button", { name: /criar usu[aá]rio/i }));

    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith(
        "configuracoes/usuarios",
        expect.objectContaining({
          method: "POST",
          body: {
            email: "maria@abase.com",
            first_name: "Maria",
            last_name: "Coord",
            roles: ["AGENTE"],
            password: "SenhaTemp@123",
            password_confirm: "SenhaTemp@123",
            is_active: true,
          },
        }),
      ),
    );

    await waitFor(() =>
      expect(mockedToast.success).toHaveBeenCalledWith(
        "Usuário Maria Coord criado com sucesso.",
      ),
    );
  });
});
