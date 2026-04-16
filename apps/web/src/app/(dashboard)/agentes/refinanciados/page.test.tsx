import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import AgenteRefinanciadosPage from "./page";
import { apiFetch } from "@/lib/api/client";
import { exportRouteReport, fetchAllPaginatedRows } from "@/lib/reports";
import { usePermissions } from "@/hooks/use-permissions";

jest.mock("@/lib/api/client", () => ({
  apiFetch: jest.fn(),
}));

jest.mock("@/lib/reports", () => ({
  describeReportScope: jest.fn(() => ({ scope: "month", referencia: "2026-04" })),
  exportRouteReport: jest.fn(),
  fetchAllPaginatedRows: jest.fn(),
  filterRowsByReportScope: jest.fn(({ rows }) => rows),
}));

jest.mock("@/hooks/use-permissions", () => ({
  usePermissions: jest.fn(),
}));

jest.mock("@/components/shared/report-export-dialog", () => ({
  __esModule: true,
  default: function MockReportExportDialog({
    onExport,
    label,
  }: {
    onExport: (
      filters: {
        scope: "month";
        referenceDate: Date;
        agente?: string;
        columns?: string[];
      },
      format: "xlsx",
    ) => void;
    label?: string;
  }) {
    return (
      <button
        onClick={() =>
          onExport(
            {
              scope: "month",
              referenceDate: new Date("2026-03-01T00:00:00"),
              agente: "2",
              columns: ["associado_nome"],
            },
            "xlsx",
          )
        }
      >
        {label ?? "Exportar"}
      </button>
    );
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
    data: Array<{
      id: number;
      associado?: { nome_completo: string };
      associado_nome?: string;
      nome_associado?: string;
    }>;
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
            <div key={row.id}>
              {row.associado?.nome_completo || row.associado_nome || row.nome_associado}
            </div>
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
const mockedExportRouteReport = jest.mocked(exportRouteReport);
const mockedFetchAllPaginatedRows = jest.mocked(fetchAllPaginatedRows);
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

const aptosResumoPayload = {
  competencia: "2026-04-01",
  em_analise: 1,
  aprovados: 0,
  desistentes: 1,
  renovados: 23,
};

const aptosPayload = {
  count: 1,
  next: null,
  previous: null,
  results: [
    {
      id: 10,
      competencia: "04/2026",
      contrato_id: 10,
      contrato_codigo: "CTR-00010",
      associado_id: 20,
      nome_associado: "Associado Apto",
      cpf_cnpj: "12345678901",
      orgao_publico: "SEFAZ",
      ciclo_id: 99,
      ciclo_numero: 1,
      status_ciclo: "apto_a_renovar",
      status_parcela: "descontado",
      status_visual: "apto_a_renovar",
      status_explicacao: "Apto a renovar porque o contrato CTR-00010 atingiu 2/3 parcelas baixadas.",
      data_primeiro_ciclo_ativado: "2026-03-12T10:00:00Z",
      data_ativacao_ciclo: "2026-03-12T10:00:00Z",
      origem_data_ativacao: "modelo",
      data_solicitacao_renovacao: null,
      ativacao_inferida: false,
      matricula: "123456",
      agente_responsavel: "Agente Norte",
      parcelas_pagas: 2,
      parcelas_total: 3,
      contrato_referencia_renovacao_id: 10,
      contrato_referencia_renovacao_codigo: "CTR-00010",
      possui_multiplos_contratos: false,
      valor_mensalidade: "400.00",
      valor_parcela: "400.00",
      data_pagamento: "2026-03-15",
      orgao_pagto_nome: "SEFAZ",
      resultado_importacao: "baixa_efetuada",
      status_codigo_etipi: "1",
      status_descricao_etipi: "Lançado e Efetivado",
      gerou_encerramento: false,
      gerou_novo_ciclo: false,
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
    mockedExportRouteReport.mockResolvedValue(undefined);
    mockedFetchAllPaginatedRows.mockResolvedValue(aptosPayload.results);
    mockedApiFetch.mockImplementation(async (path) => {
      if (path === "refinanciamentos") {
        return { count: 0, next: null, previous: null, results: [] };
      }

      if (path === "refinanciamentos/resumo") {
        return resumoVazio;
      }

      if (path === "contratos/renovacao-resumo") {
        return aptosResumoPayload;
      }

      if (path === "associados/agentes") {
        return [
          { id: 1, full_name: "Agente Sul" },
          { id: 2, full_name: "Agente Norte" },
        ];
      }

      if (path === "renovacao-ciclos") {
        return aptosPayload;
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
        "renovacao-ciclos",
        expect.objectContaining({
          query: expect.objectContaining({
            status: "apto_a_renovar",
            search: undefined,
            data_inicio: "2026-03-01",
            data_fim: "2026-03-31",
            agente: "2",
          }),
        }),
      ),
    );

    await user.click(screen.getByRole("button", { name: "Exportar" }));

    await waitFor(() =>
      expect(mockedFetchAllPaginatedRows).toHaveBeenCalledWith(
        expect.objectContaining({
          sourcePath: "renovacao-ciclos",
          sourceQuery: {
            search: undefined,
            status: "apto_a_renovar",
            data_inicio: "2026-03-01",
            data_fim: "2026-03-31",
            agente: "2",
          },
        }),
      ),
    );

    await waitFor(() =>
      expect(mockedExportRouteReport).toHaveBeenCalledWith(
        expect.objectContaining({
          route: "/agentes/refinanciados",
          format: "xlsx",
          filters: expect.objectContaining({
            agente_label: "Agente Norte",
            columns: ["associado_nome"],
          }),
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
