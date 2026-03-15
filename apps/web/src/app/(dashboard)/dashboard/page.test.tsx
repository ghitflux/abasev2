import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import DashboardPage from "./page";
import { apiFetch } from "@/lib/api/client";

const mockUsePermissions = jest.fn();
const mockReplace = jest.fn();

jest.mock("@/lib/api/client", () => ({
  apiFetch: jest.fn(),
}));

jest.mock("@/hooks/use-permissions", () => ({
  usePermissions: () => mockUsePermissions(),
}));

jest.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: mockReplace,
  }),
}));

jest.mock("recharts", () => {
  const React = require("react");

  const primitive =
    (name: string) =>
    ({ children, ...props }: { children?: unknown }) =>
      React.createElement("div", { "data-recharts": name, ...props }, children);

  return {
    Area: primitive("Area"),
    AreaChart: primitive("AreaChart"),
    Bar: primitive("Bar"),
    BarChart: primitive("BarChart"),
    CartesianGrid: primitive("CartesianGrid"),
    Cell: primitive("Cell"),
    Line: primitive("Line"),
    LineChart: primitive("LineChart"),
    Pie: primitive("Pie"),
    PieChart: primitive("PieChart"),
    PolarAngleAxis: primitive("PolarAngleAxis"),
    PolarGrid: primitive("PolarGrid"),
    Radar: primitive("Radar"),
    RadarChart: primitive("RadarChart"),
    RadialBar: primitive("RadialBar"),
    RadialBarChart: primitive("RadialBarChart"),
    XAxis: primitive("XAxis"),
  };
});

jest.mock("@/components/ui/chart", () => {
  const React = require("react");

  return {
    ChartContainer: ({ children }: { children: unknown }) =>
      React.createElement("div", null, children),
    ChartTooltip: () => null,
    ChartTooltipContent: () => null,
    ChartLegend: () => null,
    ChartLegendContent: () => null,
  };
});

jest.mock("@/components/shared/export-button", () => {
  const React = require("react");

  return {
    __esModule: true,
    default: ({
      onExport,
      disabled = false,
      label = "Exportar",
    }: {
      onExport: (format: "csv" | "pdf" | "excel") => void;
      disabled?: boolean;
      label?: string;
    }) =>
      React.createElement(
        "button",
        { disabled, onClick: () => onExport("csv") },
        label,
      ),
  };
});

jest.mock("@/components/shared/dashboard-detail-dialog", () => {
  const React = require("react");

  return {
    __esModule: true,
    default: ({
      open,
      title,
      rows,
    }: {
      open: boolean;
      title: string;
      rows: Array<{ id: string; associado_nome: string }>;
    }) =>
      open
        ? React.createElement(
            "div",
            { role: "dialog" },
            React.createElement("h2", null, title),
            ...rows.map((row) =>
              React.createElement("div", { key: row.id }, row.associado_nome),
            ),
          )
        : null,
  };
});

jest.mock("sonner", () => ({
  toast: {
    error: jest.fn(),
    success: jest.fn(),
  },
}));

const mockedApiFetch = jest.mocked(apiFetch);

const summaryPayload = {
  competencia: "2026-03",
  kpis: [
    {
      key: "associados_cadastrados",
      label: "Associados cadastrados",
      value: "12",
      numeric_value: 12,
      format: "integer" as const,
      tone: "neutral" as const,
      description: "Base total de associados no recorte atual.",
      detail_metric: "associados_cadastrados",
    },
    {
      key: "associados_ativos",
      label: "Associados ativos",
      value: "8",
      numeric_value: 8,
      format: "integer" as const,
      tone: "positive" as const,
      description: "Associados com status ativo.",
      detail_metric: "associados_ativos",
    },
  ],
  flow_bars: [
    {
      key: "efetivados",
      label: "Efetivados",
      value: 5,
      detail_metric: "efetivados",
    },
  ],
  status_pie: [
    {
      key: "ativo",
      label: "Ativo",
      value: 8,
      detail_metric: "status:ativo",
    },
  ],
  trend_lines: [
    {
      bucket: "2026-03",
      label: "03/2026",
      cadastros: 4,
      efetivados: 3,
      renovacoes: 2,
      cadastros_metric: "trend:cadastros:2026-03",
      efetivados_metric: "trend:efetivados:2026-03",
      renovacoes_metric: "trend:renovacoes:2026-03",
    },
  ],
};

const treasuryPayload = {
  competencia: "2026-03",
  cards: [
    {
      key: "valores_recebidos",
      label: "Valores recebidos",
      value: "105.00",
      numeric_value: 105,
      format: "currency" as const,
      tone: "positive" as const,
      description: "Recebimentos consolidados da competencia.",
      detail_metric: "valores_recebidos",
    },
  ],
  projection_area: [
    {
      bucket: "2026-03",
      label: "03/2026",
      recebido: 105,
      projetado: 120,
      recebido_metric: "recebido:2026-03",
      projetado_metric: "projetado:2026-03",
    },
  ],
  movement_bars: [
    {
      key: "manual",
      label: "Manual",
      value: 1,
      detail_metric: "baixas_manuais",
    },
  ],
  composition_radial: [
    {
      key: "recebido_atual",
      label: "Recebido",
      value: 105,
      detail_metric: "valores_recebidos",
    },
  ],
};

const newAssociadosPayload = {
  date_start: "2026-03-01",
  date_end: "2026-03-31",
  cards: [
    {
      key: "novos_cadastrados",
      label: "Novos cadastrados",
      value: "4",
      numeric_value: 4,
      format: "integer" as const,
      tone: "neutral" as const,
      description: "Associados criados dentro do periodo.",
      detail_metric: "novos_cadastrados",
    },
  ],
  trend_area: [
    {
      bucket: "2026-03",
      label: "03/2026",
      cadastros: 4,
      efetivados: 2,
      cadastros_metric: "cadastros:2026-03",
      efetivados_metric: "efetivados:2026-03",
    },
  ],
  status_pie: [
    {
      key: "ativo",
      label: "Ativo",
      value: 1,
      detail_metric: "status:ativo",
    },
  ],
};

const agentsPayload = {
  date_start: "2026-03-01",
  date_end: "2026-03-31",
  cards: [
    {
      key: "agentes_no_ranking",
      label: "Agentes monitorados",
      value: "2",
      numeric_value: 2,
      format: "integer" as const,
      tone: "neutral" as const,
      description: "Quantidade de agentes com dados no periodo.",
      detail_metric: "agentes_no_ranking",
    },
  ],
  ranking: [
    {
      agent_id: 1,
      agent_name: "Alice ABASE",
      efetivados: 3,
      cadastros: 5,
      em_processo: 1,
      renovados: 2,
      inadimplentes: 0,
      participacao: 60,
      detail_metric: "agente:1:efetivados",
    },
    {
      agent_id: 2,
      agent_name: "Bruno ABASE",
      efetivados: 2,
      cadastros: 4,
      em_processo: 2,
      renovados: 1,
      inadimplentes: 1,
      participacao: 40,
      detail_metric: "agente:2:efetivados",
    },
  ],
};

const detailPayload = {
  count: 1,
  next: null,
  previous: null,
  results: [
    {
      id: "associado-1",
      associado_id: 1,
      associado_nome: "Maria Ativa",
      cpf_cnpj: "11111111111",
      matricula: "MAT-1111",
      status: "ativo",
      agente_nome: "Alice ABASE",
      contrato_codigo: "CTR-A1",
      etapa: "concluido",
      competencia: "03/2026",
      valor: "30.00",
      origem: "Associado cadastrado",
      data_referencia: "2026-03-01",
      observacao: "",
    },
  ],
};

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <DashboardPage />
    </QueryClientProvider>,
  );
}

describe("DashboardPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();

    mockUsePermissions.mockReturnValue({
      role: "ADMIN",
      status: "authenticated",
      roles: ["ADMIN"],
      hasRole: jest.fn(),
      hasAnyRole: jest.fn(),
      user: {
        id: 1,
        email: "admin@abase.local",
        first_name: "Admin",
        last_name: "ABASE",
        full_name: "Admin ABASE",
        primary_role: "ADMIN",
        roles: ["ADMIN"],
      },
    });

    mockedApiFetch.mockImplementation(async (path) => {
      if (path === "dashboard/admin/resumo-geral") return summaryPayload;
      if (path === "dashboard/admin/tesouraria") return treasuryPayload;
      if (path === "dashboard/admin/novos-associados")
        return newAssociadosPayload;
      if (path === "dashboard/admin/agentes") return agentsPayload;
      if (path === "dashboard/admin/detalhes") return detailPayload;

      throw new Error(`Unexpected apiFetch path: ${path}`);
    });

    Object.defineProperty(URL, "createObjectURL", {
      writable: true,
      value: jest.fn(() => "blob:dashboard-export"),
    });
    Object.defineProperty(URL, "revokeObjectURL", {
      writable: true,
      value: jest.fn(),
    });
    HTMLAnchorElement.prototype.click = jest.fn();
  });

  it("redireciona usuario nao admin para a rota padrao da role", async () => {
    mockUsePermissions.mockReturnValue({
      role: "AGENTE",
      status: "authenticated",
      roles: ["AGENTE"],
      hasRole: jest.fn(),
      hasAnyRole: jest.fn(),
      user: null,
    });

    renderPage();

    expect(
      await screen.findByText("Verificando acesso..."),
    ).toBeInTheDocument();
    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith("/agentes/meus-contratos");
    });
    expect(mockedApiFetch).not.toHaveBeenCalled();
  });

  it("renderiza as cinco secoes do dashboard e abre o modal detalhado ao clicar em KPI", async () => {
    const user = userEvent.setup();

    renderPage();

    expect(await screen.findByText("Dashboard Executivo")).toBeInTheDocument();
    expect(screen.getByText("Tesouraria")).toBeInTheDocument();
    expect(screen.getByText("KPIs gerais")).toBeInTheDocument();
    expect(screen.getByText("Novos associados")).toBeInTheDocument();
    expect(screen.getByText("Agentes")).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "Associados cadastrados" }),
    );

    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(await screen.findByText("Maria Ativa")).toBeInTheDocument();
  });

  it("reaplica a consulta da secao ao alterar o filtro de status do panorama geral", async () => {
    const user = userEvent.setup();

    renderPage();

    await screen.findByText("KPIs gerais");
    await user.click(screen.getAllByRole("button", { name: /Filtros/i })[1]);
    await user.click(screen.getByRole("combobox"));
    await user.click(await screen.findByRole("option", { name: "Ativo" }));
    await user.click(screen.getByRole("button", { name: "Aplicar" }));

    await waitFor(() => {
      expect(mockedApiFetch).toHaveBeenCalledWith(
        "dashboard/admin/resumo-geral",
        expect.objectContaining({
          query: expect.objectContaining({
            status: "ativo",
          }),
        }),
      );
    });
  });

  it("exporta uma secao buscando o detalhamento completo", async () => {
    const user = userEvent.setup();

    renderPage();

    await screen.findByText("KPIs gerais");
    await user.click(screen.getAllByRole("button", { name: /Exportar/i })[1]);
    await user.click(await screen.findByText("CSV"));

    await waitFor(() => {
      expect(mockedApiFetch).toHaveBeenCalledWith(
        "dashboard/admin/detalhes",
        expect.objectContaining({
          query: expect.objectContaining({
            section: "summary",
            page_size: "all",
          }),
        }),
      );
    });
    expect(URL.createObjectURL).toHaveBeenCalled();
  });
});
