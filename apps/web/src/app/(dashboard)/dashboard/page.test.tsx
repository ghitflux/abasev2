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

jest.mock("@/providers/route-transition-provider", () => ({
  useRouteTransition: () => ({
    isRouteTransitioning: false,
    isRouteLoadingVisible: false,
    pendingHref: null,
    startRouteTransition: jest.fn(),
  }),
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
    ({ children }: { children?: unknown }) =>
      React.createElement("div", { "data-recharts": name }, children);

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
      onExport: (format: "csv" | "pdf" | "excel" | "xlsx") => void;
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
    {
      key: "saidas_agentes_associados",
      label: "Saidas a agentes/associados",
      value: "35.00",
      numeric_value: 35,
      format: "currency" as const,
      tone: "warning" as const,
      description: "Pagamentos operacionais e devolucoes liquidadas na competencia.",
      detail_metric: "saidas_agentes_associados",
    },
    {
      key: "despesas",
      label: "Despesas",
      value: "10.00",
      numeric_value: 10,
      format: "currency" as const,
      tone: "danger" as const,
      description: "Despesas pagas que impactam o caixa da associacao.",
      detail_metric: "despesas",
    },
    {
      key: "receita_liquida_associacao",
      label: "Receita liquida da associacao",
      value: "60.00",
      numeric_value: 60,
      format: "currency" as const,
      tone: "positive" as const,
      description: "Receita recebida menos saidas e despesas.",
      detail_metric: "receita_liquida_associacao",
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

const treasurySummaryPayload = {
  rows: [
    {
      mes: "2026-03-01",
      complementos_receita: "80.00",
      saldo_positivo: "67.50",
      novos_associados: 3,
      desvinculados: 1,
      renovacoes_associado: 1,
    },
    {
      mes: "2026-02-01",
      complementos_receita: "0.00",
      saldo_positivo: "0.00",
      novos_associados: 1,
      desvinculados: 0,
      renovacoes_associado: 0,
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
  competencia: "2026-03",
  date_start: "2026-03-01",
  date_end: "2026-03-31",
  cards: [
    {
      key: "volume_total",
      label: "Volume total",
      value: "18000.00",
      numeric_value: 18000,
      format: "currency" as const,
      tone: "neutral" as const,
      description: "Soma do valor liquido efetivado pelos agentes no recorte.",
      detail_metric: "agentes:volume_total",
    },
    {
      key: "top_agente_volume",
      label: "Top agente por volume",
      value: "10000.00",
      numeric_value: 10000,
      format: "currency" as const,
      tone: "positive" as const,
      description: "Alice ABASE",
      detail_metric: "agente:1:volume",
    },
    {
      key: "media_volume",
      label: "Media por agente",
      value: "9000.00",
      numeric_value: 9000,
      format: "currency" as const,
      tone: "neutral" as const,
      description: "Media de volume financeiro entre os agentes monitorados.",
      detail_metric: "agentes:volume_total",
    },
    {
      key: "associados_inativos",
      label: "Associados inativos",
      value: "1",
      numeric_value: 1,
      format: "integer" as const,
      tone: "neutral" as const,
      description: "Base atual de associados inativos vinculados aos agentes filtrados.",
      detail_metric: "agentes:inativos",
    },
    {
      key: "com_devolucao",
      label: "Associados com devolucao",
      value: "1",
      numeric_value: 1,
      format: "integer" as const,
      tone: "neutral" as const,
      description: "Devolucoes registradas na competencia filtrada.",
      detail_metric: "agentes:devolvidos",
    },
    {
      key: "renovados",
      label: "Associados renovados",
      value: "3",
      numeric_value: 3,
      format: "integer" as const,
      tone: "positive" as const,
      description: "Renovacoes efetivadas na competencia da secao.",
      detail_metric: "agentes:renovados",
    },
    {
      key: "aptos_renovar",
      label: "Associados para renovar",
      value: "4",
      numeric_value: 4,
      format: "integer" as const,
      tone: "neutral" as const,
      description: "Associados aptos a renovar na competencia da secao.",
      detail_metric: "agentes:aptos_renovar",
    },
  ],
  ranking: [
    {
      agent_id: 1,
      agent_name: "Alice ABASE",
      volume_financeiro: 10000,
      participacao_volume: 55.6,
      efetivados: 3,
      cadastros: 5,
      em_processo: 1,
      renovados: 2,
      aptos_renovar: 2,
      inadimplentes: 0,
      devolvidos: 1,
      cadastrado: 1,
      em_analise: 1,
      pendente: 0,
      ativo: 5,
      inadimplente: 0,
      inativo: 1,
      participacao: 60,
      detail_metric: "agente:1:volume",
    },
    {
      agent_id: 2,
      agent_name: "Bruno ABASE",
      volume_financeiro: 8000,
      participacao_volume: 44.4,
      efetivados: 2,
      cadastros: 4,
      em_processo: 2,
      renovados: 1,
      aptos_renovar: 2,
      inadimplentes: 1,
      devolvidos: 0,
      cadastrado: 1,
      em_analise: 0,
      pendente: 1,
      ativo: 3,
      inadimplente: 1,
      inativo: 0,
      participacao: 40,
      detail_metric: "agente:2:volume",
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
      if (path === "configuracoes/usuarios") {
        return {
          count: 0,
          next: null,
          previous: null,
          results: [],
          meta: {
            current_page: 1,
            page_size: 200,
            total_pages: 0,
            total_items: 0,
          },
        };
      }
      if (path === "dashboard/admin/resumo-geral") return summaryPayload;
      if (path === "dashboard/admin/tesouraria") return treasuryPayload;
      if (path === "dashboard/admin/resumo-mensal-associacao")
        return treasurySummaryPayload;
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
    Object.defineProperty(HTMLElement.prototype, "hasPointerCapture", {
      configurable: true,
      value: jest.fn(() => false),
    });
    Object.defineProperty(HTMLElement.prototype, "setPointerCapture", {
      configurable: true,
      value: jest.fn(),
    });
    Object.defineProperty(HTMLElement.prototype, "releasePointerCapture", {
      configurable: true,
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

  it("permite acesso do coordenador ao dashboard executivo", async () => {
    mockUsePermissions.mockReturnValue({
      role: "COORDENADOR",
      status: "authenticated",
      roles: ["COORDENADOR"],
      hasRole: jest.fn(),
      hasAnyRole: jest.fn(),
      user: {
        id: 2,
        email: "coordenacao@abase.local",
        first_name: "Coordenacao",
        last_name: "ABASE",
        full_name: "Coordenacao ABASE",
        primary_role: "COORDENADOR",
        roles: ["COORDENADOR"],
      },
    });

    renderPage();

    expect(await screen.findByText("Dashboard Executivo")).toBeInTheDocument();
    expect(mockReplace).not.toHaveBeenCalled();
  });

  it("renderiza as cinco secoes do dashboard e abre o modal detalhado ao clicar em KPI", async () => {
    const user = userEvent.setup();

    renderPage();

    expect(await screen.findByText("Dashboard Executivo")).toBeInTheDocument();
    expect(screen.getByText("Tesouraria")).toBeInTheDocument();
    expect(screen.getByText("KPIs gerais")).toBeInTheDocument();
    expect(screen.getByText("Novos associados")).toBeInTheDocument();
    expect(screen.getByText("Agentes")).toBeInTheDocument();
    expect(await screen.findByText("Resumo mensal da associação")).toBeInTheDocument();
    expect(await screen.findByText("Complementos de receita")).toBeInTheDocument();
    expect((await screen.findAllByText("março de 2026")).length).toBeGreaterThan(0);

    await user.click(
      await screen.findByRole("button", { name: "Associados cadastrados" }),
    );

    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(await screen.findByText("Maria Ativa")).toBeInTheDocument();
  });

  it("reaplica a consulta da secao ao alterar o filtro de status do panorama geral", async () => {
    const user = userEvent.setup();

    renderPage();

    await screen.findByText("KPIs gerais");
    await user.click(screen.getAllByRole("button", { name: /Filtros/i })[1]);
    await user.click(screen.getAllByRole("combobox")[1]);
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
    expect(mockedApiFetch).toHaveBeenCalledWith(
      "dashboard/admin/resumo-mensal-associacao",
      expect.objectContaining({
        query: expect.objectContaining({
          competencia: "2026-03",
        }),
      }),
    );
    expect(URL.createObjectURL).toHaveBeenCalled();
  });
});
