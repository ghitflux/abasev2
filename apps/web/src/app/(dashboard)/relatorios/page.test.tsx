import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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

jest.mock("@/components/custom/date-picker", () => ({
  __esModule: true,
  default: ({
    value,
    onChange,
    placeholder = "dd/mm/aaaa",
  }: {
    value?: Date;
    onChange?: (date?: Date) => void;
    placeholder?: string;
  }) => (
    <input
      aria-label={placeholder}
      placeholder={placeholder}
      value={value && !Number.isNaN(value.getTime()) ? value.toISOString().slice(0, 10) : ""}
      onChange={(event) =>
        onChange?.(event.target.value ? new Date(`${event.target.value}T12:00:00`) : undefined)
      }
    />
  ),
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

      if (path === "tesouraria/contratos/agentes") {
        return [
          {
            id: 9,
            full_name: "Agente A",
            email: "agente-a@abase.local",
            primary_role: "AGENTE",
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
    renderPage();

    expect(await screen.findByText("tesouraria_20260313100000.pdf")).toBeInTheDocument();
    expect(screen.getByText("PDF")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /baixar/i })).toBeInTheDocument();
  });

  it("exporta relatorio de associados ativos pagadores com filtros", async () => {
    const user = userEvent.setup();
    renderPage();

    const card = await screen.findByTestId("relatorio-card-associados_ativos_com_3_parcelas_pagas");
    await user.click(
      within(card).getByRole("button", { name: /Exportar CSV \/ PDF \/ XLS/i }),
    );

    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: /Faixa de período/i }));
    const dateInputs = within(dialog).getAllByPlaceholderText("dd/mm/aaaa");
    fireEvent.change(dateInputs[0], { target: { value: "2026-04-01" } });
    fireEvent.change(dateInputs[1], { target: { value: "2026-04-30" } });
    await user.click(within(dialog).getByText("Todos os agentes"));
    await user.click(await screen.findByText("Agente A"));
    await user.click(within(dialog).getByRole("button", { name: /Todas as faixas/i }));
    const popovers = await screen.findAllByRole("dialog");
    const faixaPopover = popovers[popovers.length - 1];
    await user.click(
      within(faixaPopover).getByRole("checkbox", { name: /R\$ 200 a R\$ 299,99/i }),
    );
    await user.click(
      within(faixaPopover).getByRole("checkbox", { name: /Acima de R\$ 500/i }),
    );
    await user.click(within(dialog).getByRole("button", { name: "XLS" }));

    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith(
        "relatorios/exportar",
        expect.objectContaining({
          method: "POST",
          body: {
            tipo: "associados_ativos_com_3_parcelas_pagas",
            formato: "xlsx",
            filtros: {
              data_inicio: "2026-04-01",
              data_fim: "2026-04-30",
              agente_id: "9",
              faixa_mensalidade: ["200_300", "acima_500"],
            },
          },
        }),
      ),
    );
  });

  it("exporta relatorio de associados inativos com periodo maximo sem datas", async () => {
    const user = userEvent.setup();
    renderPage();

    const card = await screen.findByTestId("relatorio-card-associados_inativos_com_1_parcela_paga");
    await user.click(
      within(card).getByRole("button", { name: /Exportar CSV \/ PDF \/ XLS/i }),
    );

    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: /Período máximo/i }));
    await user.click(within(dialog).getByRole("button", { name: "CSV" }));

    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith(
        "relatorios/exportar",
        expect.objectContaining({
          method: "POST",
          body: {
            tipo: "associados_inativos_com_1_parcela_paga",
            formato: "csv",
            filtros: {
              data_inicio: undefined,
              data_fim: undefined,
              agente_id: undefined,
              faixa_mensalidade: undefined,
            },
          },
        }),
      ),
    );
  });
});
