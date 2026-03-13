import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import RelatoriosPage from "./page";
import { apiFetch } from "@/lib/api/client";
import { usePermissions } from "@/hooks/use-permissions";
import { toast } from "sonner";

jest.mock("@/lib/api/client", () => ({
  apiFetch: jest.fn(),
}));

jest.mock("@/hooks/use-permissions", () => ({
  usePermissions: jest.fn(),
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
      <RelatoriosPage />
    </QueryClientProvider>,
  );
}

describe("RelatoriosPage", () => {
  let anchorClickSpy: jest.SpyInstance;

  beforeEach(() => {
    jest.clearAllMocks();
    anchorClickSpy = jest.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

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
      refresh: jest.fn(),
      clear: jest.fn(),
    });

    mockedApiFetch.mockImplementation(async (path, options) => {
      if (path === "relatorios/resumo") {
        return {
          associados_ativos: 10,
          associados_em_analise: 2,
          associados_inadimplentes: 1,
          contratos_ativos: 8,
          contratos_em_analise: 1,
          pendencias_abertas: 3,
          esteira_aguardando: 4,
          refinanciamentos_pendentes: 2,
          refinanciamentos_efetivados: 5,
          importacoes_concluidas: 7,
          baixas_mes: 12,
          valor_baixado_mes: "1234.56",
          ultima_importacao: {
            id: 99,
            arquivo_nome: "retorno_marco.txt",
            competencia: "03/2026",
            status: "concluido",
            processado_em: "2026-03-13T10:00:00Z",
          },
        };
      }

      if (path === "relatorios") {
        return [
          {
            id: 10,
            nome: "tesouraria_20260313100000.pdf",
            formato: "pdf",
            created_at: "2026-03-13T10:00:00Z",
            download_url: "/api/v1/relatorios/10/download/",
          },
        ];
      }

      if (path === "relatorios/exportar") {
        return {
          id: 11,
          nome: `${(options?.body as { tipo: string }).tipo}_20260313101500.${(options?.body as { formato: string }).formato}`,
          formato: (options?.body as { formato: string }).formato,
          created_at: "2026-03-13T10:15:00Z",
          download_url: "/api/v1/relatorios/11/download/",
        };
      }

      throw new Error(`Unexpected apiFetch path: ${path}`);
    });
  });

  afterEach(() => {
    anchorClickSpy.mockRestore();
  });

  it("exporta um relatorio em pdf pelo card do tipo", async () => {
    const user = userEvent.setup();
    renderPage();

    const card = await screen.findByTestId("relatorio-card-tesouraria");

    await user.click(
      within(card).getByRole("button", {
        name: "Exportar Tesouraria em PDF",
      }),
    );

    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith(
        "relatorios/exportar",
        expect.objectContaining({
          method: "POST",
          body: {
            tipo: "tesouraria",
            formato: "pdf",
          },
        }),
      ),
    );

    await waitFor(() =>
      expect(mockedToast.success).toHaveBeenCalledWith("Relatorio gerado com sucesso."),
    );
  });

  it("renderiza o historico de exportacoes com o formato persistido", async () => {
    renderPage();

    expect(await screen.findByText("tesouraria_20260313100000.pdf")).toBeInTheDocument();
    expect(screen.getByText("PDF")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /baixar/i })).toBeInTheDocument();
  });
});
