import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import AgenteRefinanciadosPage from "./page";
import { apiFetch } from "@/lib/api/client";
import { exportPaginatedRouteReport } from "@/lib/reports";
import { usePermissions } from "@/hooks/use-permissions";

jest.mock("@/lib/api/client", () => ({
  apiFetch: jest.fn(),
}));

jest.mock("@/lib/reports", () => ({
  exportPaginatedRouteReport: jest.fn(),
}));

jest.mock("@/hooks/use-permissions", () => ({
  usePermissions: jest.fn(),
}));

jest.mock("@/components/shared/export-button", () => ({
  __esModule: true,
  default: function MockExportButton({
    onExport,
    label,
  }: {
    onExport: (format: "xlsx") => void;
    label?: string;
  }) {
    return <button onClick={() => onExport("xlsx")}>{label ?? "Exportar"}</button>;
  },
}));

jest.mock("@/components/shared/data-table", () => ({
  __esModule: true,
  default: function MockDataTable({
    columns,
    data,
    emptyMessage,
  }: {
    columns: Array<{ id: string; header: string }>;
    data: Array<{ id: number; associado?: { nome_completo: string }; associado_nome?: string }>;
    emptyMessage: string;
  }) {
    return (
      <div>
        <div>
          {columns.map((column) => (
            <span key={column.id}>{column.header}</span>
          ))}
        </div>
        {data.length ? (
          data.map((row) => (
            <div key={row.id}>{row.associado?.nome_completo || row.associado_nome}</div>
          ))
        ) : (
          <div>{emptyMessage}</div>
        )}
      </div>
    );
  },
}));

jest.mock("@/components/custom/file-upload-dropzone", () => ({
  __esModule: true,
  default: function MockFileUploadDropzone() {
    return <div>Upload</div>;
  },
}));

jest.mock("@/components/custom/date-picker", () => ({
  __esModule: true,
  default: function MockDatePicker({
    value,
    onChange,
  }: {
    value?: Date;
    onChange?: (value?: Date) => void;
  }) {
    const resolvedValue =
      value instanceof Date && !Number.isNaN(value.getTime())
        ? value.toISOString().slice(0, 10)
        : "";

    return (
      <input
        data-testid="mock-date-picker"
        type="date"
        value={resolvedValue}
        onChange={(event) =>
          onChange?.(
            event.target.value ? new Date(`${event.target.value}T00:00:00`) : undefined,
          )
        }
      />
    );
  },
}));

jest.mock("@/components/custom/searchable-select", () => ({
  __esModule: true,
  default: function MockSearchableSelect({
    options,
    value,
    onChange,
    placeholder,
    clearLabel,
  }: {
    options: Array<{ value: string; label: string }>;
    value?: string;
    onChange?: (value: string) => void;
    placeholder?: string;
    clearLabel?: string;
  }) {
    return (
      <select
        aria-label={placeholder ?? "Selecione"}
        value={value ?? ""}
        onChange={(event) => onChange?.(event.target.value)}
      >
        <option value="">{clearLabel ?? placeholder ?? "Todos"}</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    );
  },
}));

const mockedApiFetch = jest.mocked(apiFetch);
const mockedExportPaginatedRouteReport = jest.mocked(exportPaginatedRouteReport);
const mockedUsePermissions = jest.mocked(usePermissions);

const resumoVazio = {
  total: 0,
  em_analise: 0,
  assumidos: 0,
  aprovados: 0,
  efetivados: 0,
  concluidos: 0,
  bloqueados: 0,
  revertidos: 0,
  em_fluxo: 0,
  com_anexo_agente: 0,
  repasse_total: "0.00",
};

const contratosPayload = {
  count: 1,
  next: null,
  previous: null,
  results: [
    {
      id: 10,
      codigo: "CTR-00010",
      associado: {
        id: 20,
        nome_completo: "Associado Apto",
        matricula: "123456",
        matricula_display: "123456",
        cpf_cnpj: "12345678901",
        orgao_publico: "SEFAZ",
        matricula_orgao: "MAT-123456",
      },
      agente: {
        id: 2,
        full_name: "Agente Norte",
      },
      status: "ativo",
      status_resumido: "concluido",
      status_contrato_visual: "ativo",
      status_visual_slug: "contrato_ativo",
      status_visual_label: "Ativo",
      etapa_fluxo: "concluido",
      data_contrato: "2026-03-12",
      valor_disponivel: "1200.00",
      valor_mensalidade: "400.00",
      comissao_agente: "80.00",
      valor_auxilio_liberado: "1200.00",
      percentual_repasse: "6.67",
      mensalidades: {
        pagas: 3,
        total: 3,
        descricao: "01/2026, 02/2026 e 05/2026",
        apto_refinanciamento: true,
        refinanciamento_ativo: false,
      },
      auxilio_liberado_em: "2026-03-12",
      ciclo_apto: {
        numero: 1,
        status: "apto_a_renovar",
        status_visual_slug: "ciclo_apto_renovar",
        status_visual_label: "Apto a renovar",
        resumo_referencias: "01/2026 a 03/2026",
        parcelas_pagas: 3,
        parcelas_total: 3,
        valor_total: "1200.00",
        primeira_competencia_ciclo: "2026-01-01",
        ultima_competencia_ciclo: "2026-03-01",
      },
      pode_solicitar_refinanciamento: true,
      status_renovacao: "apto_a_renovar",
      refinanciamento_id: null,
      possui_meses_nao_descontados: false,
      meses_nao_descontados_count: 0,
    },
  ],
};

function buildPermissionsMock(roles: string[]) {
  return {
    user: {
      id: 1,
      email: "usuario@abase.local",
      first_name: "Usuario",
      last_name: "ABASE",
      full_name: "Usuario ABASE",
      primary_role: roles[0] ?? null,
      roles,
    },
    role: roles[0] ?? null,
    roles,
    hasRole: (...expectedRoles: string[]) => expectedRoles.some((role) => roles.includes(role)),
    hasAnyRole: (expectedRoles: string[]) =>
      expectedRoles.some((role) => roles.includes(role)),
    status: "authenticated",
    isAuthenticated: true,
    refresh: jest.fn(),
    clear: jest.fn(),
  };
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <AgenteRefinanciadosPage />
    </QueryClientProvider>,
  );
}

describe("AgenteRefinanciadosPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedExportPaginatedRouteReport.mockResolvedValue(undefined);
    mockedApiFetch.mockImplementation(async (path) => {
      if (path === "refinanciamentos") {
        return { count: 0, next: null, previous: null, results: [] };
      }

      if (path === "refinanciamentos/resumo") {
        return resumoVazio;
      }

      if (path === "associados/agentes") {
        return [
          { id: 1, full_name: "Agente Sul" },
          { id: 2, full_name: "Agente Norte" },
        ];
      }

      if (path === "contratos") {
        return contratosPayload;
      }

      throw new Error(`Unexpected apiFetch path: ${path}`);
    });
  });

  it("aplica filtros avançados na aba de aptos e exporta com o mesmo recorte para admin", async () => {
    mockedUsePermissions.mockReturnValue(buildPermissionsMock(["ADMIN"]));
    const user = userEvent.setup();

    renderPage();

    await user.click(screen.getByRole("tab", { name: "Aptos a renovar" }));

    expect(await screen.findByText("Associado Apto")).toBeInTheDocument();
    expect(screen.getByText("Agente responsável")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Filtros avançados/i }));

    const [dataInicial, dataFinal] = screen.getAllByTestId("mock-date-picker");
    await user.clear(dataInicial);
    await user.type(dataInicial, "2026-03-01");
    await user.clear(dataFinal);
    await user.type(dataFinal, "2026-03-31");
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Todos os agentes" }),
      "2",
    );

    await user.click(screen.getByRole("button", { name: "Aplicar filtros" }));

    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith(
        "contratos",
        expect.objectContaining({
          query: expect.objectContaining({
            status_renovacao: ["apto_a_renovar", "pendente_termo_agente"],
            data_inicio: "2026-03-01",
            data_fim: "2026-03-31",
            agente: "2",
          }),
        }),
      ),
    );

    await user.click(screen.getByRole("button", { name: "Exportar" }));

    await waitFor(() =>
      expect(mockedExportPaginatedRouteReport).toHaveBeenCalledWith(
        expect.objectContaining({
          sourcePath: "contratos",
          sourceQuery: {
            associado: undefined,
            status_renovacao: ["apto_a_renovar", "pendente_termo_agente"],
            data_inicio: "2026-03-01",
            data_fim: "2026-03-31",
            agente: "2",
          },
          filters: expect.objectContaining({
            agente_label: "Agente Norte",
          }),
          format: "xlsx",
        }),
      ),
    );
  });

  it("mantem a visao do agente sem coluna global nem filtro de agente", async () => {
    mockedUsePermissions.mockReturnValue(buildPermissionsMock(["AGENTE"]));
    const user = userEvent.setup();

    renderPage();

    await user.click(screen.getByRole("tab", { name: "Aptos a renovar" }));

    expect(await screen.findByText("Associado Apto")).toBeInTheDocument();
    expect(screen.queryByText("Agente responsável")).not.toBeInTheDocument();
    expect(mockedApiFetch).not.toHaveBeenCalledWith("associados/agentes", expect.anything());
  });
});
