import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import LiquidacoesTesourariaPage from "./page";
import type { LiquidacaoContratoItem, LiquidacaoKpis } from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import { usePermissions } from "@/hooks/use-permissions";
import { toast } from "sonner";

let mockSearchParams = new URLSearchParams();

jest.mock("@/lib/api/client", () => ({
  apiFetch: jest.fn(),
}));

jest.mock("@/hooks/use-permissions", () => ({
  usePermissions: jest.fn(),
}));

jest.mock("next/navigation", () => ({
  useSearchParams: () => mockSearchParams,
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
    disabled,
  }: {
    value?: Date;
    onChange?: (date?: Date) => void;
    placeholder?: string;
    disabled?: boolean;
  }) => {
    const React = require("react");
    const [internalValue, setInternalValue] = React.useState(
      value ? value.toISOString().slice(0, 10) : "",
    );

    React.useEffect(() => {
      setInternalValue(value ? value.toISOString().slice(0, 10) : "");
    }, [value]);

    return (
      <input
        value={internalValue}
        disabled={disabled}
        placeholder={placeholder}
        onChange={(event) => {
          const nextValue = event.target.value;
          setInternalValue(nextValue);

          if (!nextValue.trim()) {
            onChange?.(undefined);
            return;
          }

          const isoMatch = /^(\d{4})-(\d{2})-(\d{2})$/.exec(nextValue);
          if (isoMatch) {
            onChange?.(
              new Date(
                Number(isoMatch[1]),
                Number(isoMatch[2]) - 1,
                Number(isoMatch[3]),
                12,
                0,
                0,
                0,
              ),
            );
          }
        }}
      />
    );
  },
}));

jest.mock("@/components/custom/file-upload-dropzone", () => ({
  __esModule: true,
  default: ({
    onUploadMany,
    files,
  }: {
    onUploadMany?: (files: File[]) => void;
    files?: File[];
  }) => (
    <button
      type="button"
      onClick={() =>
        onUploadMany?.([
          new File(["primeiro"], "comprovante-1.pdf", { type: "application/pdf" }),
          new File(["segundo"], "comprovante-2.pdf", { type: "application/pdf" }),
        ])
      }
    >
      {files?.length ? `${files.length} comprovante(s)` : "Selecionar comprovantes"}
    </button>
  ),
}));

jest.mock("@/components/custom/input-currency", () => ({
  __esModule: true,
  default: ({
    value,
    onChange,
    placeholder = "R$ 0,00",
  }: {
    value?: number | null;
    onChange?: (value: number | null) => void;
    placeholder?: string;
  }) => {
    const React = require("react");
    const [internalValue, setInternalValue] = React.useState(
      value == null ? "" : (value / 100).toFixed(2),
    );

    React.useEffect(() => {
      setInternalValue(value == null ? "" : (value / 100).toFixed(2));
    }, [value]);

    return (
      <input
        value={internalValue}
        placeholder={placeholder}
        onChange={(event) => {
          const nextValue = event.target.value;
          setInternalValue(nextValue);
          if (!nextValue.trim()) {
            onChange?.(null);
            return;
          }

          const normalized = Number.parseFloat(nextValue.replace(",", "."));
          onChange?.(Number.isNaN(normalized) ? null : Math.round(normalized * 100));
        }}
      />
    );
  },
}));

const mockedApiFetch = jest.mocked(apiFetch);
const mockedUsePermissions = jest.mocked(usePermissions);
const mockedToast = jest.mocked(toast);

beforeAll(() => {
  if (!Element.prototype.hasPointerCapture) {
    Element.prototype.hasPointerCapture = () => false;
  }
  if (!Element.prototype.setPointerCapture) {
    Element.prototype.setPointerCapture = () => {};
  }
  if (!Element.prototype.releasePointerCapture) {
    Element.prototype.releasePointerCapture = () => {};
  }
});

function buildRow(
  overrides: Partial<LiquidacaoContratoItem> = {},
): LiquidacaoContratoItem {
  return {
    id: overrides.id ?? 1,
    contrato_id: overrides.contrato_id ?? overrides.id ?? 1,
    liquidacao_id: overrides.liquidacao_id ?? null,
    associado_id: overrides.associado_id ?? (overrides.id ?? 1) + 100,
    nome: overrides.nome ?? "Associado Exemplo",
    cpf_cnpj: overrides.cpf_cnpj ?? "123.456.789-00",
    matricula: overrides.matricula ?? "MAT-001",
    agente_nome: overrides.agente_nome ?? "Agente Padrão",
    contrato_codigo: overrides.contrato_codigo ?? "CTR-001",
    quantidade_parcelas: overrides.quantidade_parcelas ?? 2,
    quantidade_parcelas_contrato: overrides.quantidade_parcelas_contrato ?? 4,
    valor_total: overrides.valor_total ?? "150.00",
    referencia_inicial: overrides.referencia_inicial ?? "2026-01-01",
    referencia_final: overrides.referencia_final ?? "2026-02-01",
    status_liquidacao: overrides.status_liquidacao ?? "elegivel_agora",
    status_operacional: overrides.status_operacional ?? "elegivel_agora",
    pode_liquidar_agora: overrides.pode_liquidar_agora ?? true,
    status_associado: overrides.status_associado ?? "ciclo_aberto",
    status_associado_label: overrides.status_associado_label ?? "Ativo",
    status_contrato: overrides.status_contrato ?? "ativo",
    status_renovacao: overrides.status_renovacao ?? "",
    origem_solicitacao: overrides.origem_solicitacao ?? "",
    data_liquidacao: overrides.data_liquidacao ?? null,
    observacao: overrides.observacao ?? "",
    realizado_por: overrides.realizado_por ?? null,
    revertida_em: overrides.revertida_em ?? null,
    revertida_por: overrides.revertida_por ?? null,
    motivo_reversao: overrides.motivo_reversao ?? "",
    comprovante: overrides.comprovante ?? null,
    anexos: overrides.anexos ?? [],
    parcelas: overrides.parcelas ?? [
      {
        id: 11,
        numero: 1,
        referencia_mes: "2025-12-01",
        valor: "75.00",
        status: "descontado",
        data_vencimento: "2025-12-10",
        data_pagamento: "2025-12-10",
        observacao: "",
      },
      {
        id: 12,
        numero: 2,
        referencia_mes: "2026-01-01",
        valor: "75.00",
        status: "em_aberto",
        data_vencimento: "2026-01-10",
        data_pagamento: null,
        observacao: "",
      },
      {
        id: 13,
        numero: 3,
        referencia_mes: "2026-02-01",
        valor: "75.00",
        status: "futuro",
        data_vencimento: "2026-02-10",
        data_pagamento: null,
        observacao: "",
      },
      {
        id: 14,
        numero: 4,
        referencia_mes: "2026-03-01",
        valor: "75.00",
        status: "liquidada",
        data_vencimento: "2026-03-10",
        data_pagamento: "2026-03-10",
        observacao: "",
      },
    ],
    pode_reverter: overrides.pode_reverter ?? false,
  };
}

function buildKpis(overrides: Partial<LiquidacaoKpis> = {}): LiquidacaoKpis {
  return {
    total_contratos: overrides.total_contratos ?? 3,
    total_parcelas: overrides.total_parcelas ?? 3,
    valor_total: overrides.valor_total ?? "210.00",
    associados_impactados: overrides.associados_impactados ?? 3,
    revertidas: overrides.revertidas ?? 0,
    ativas: overrides.ativas ?? 0,
    liquidaveis_agora: overrides.liquidaveis_agora ?? 2,
    sem_parcelas_elegiveis: overrides.sem_parcelas_elegiveis ?? 1,
    por_status_associado: overrides.por_status_associado ?? {
      ciclo_aberto: 1,
      apto_a_renovar: 1,
      contrato_encerrado: 1,
      em_analise: 0,
    },
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
      <LiquidacoesTesourariaPage />
    </QueryClientProvider>,
  );
}

describe("LiquidacoesTesourariaPage", () => {
  let filaRows: LiquidacaoContratoItem[];
  let filaKpis: LiquidacaoKpis;
  let liquidadoRows: LiquidacaoContratoItem[];
  let liquidadoKpis: LiquidacaoKpis;

  beforeEach(() => {
    jest.clearAllMocks();
    mockSearchParams = new URLSearchParams();

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

    filaRows = [
      buildRow({
        id: 1,
        contrato_id: 1,
        associado_id: 101,
        nome: "Maria Silva",
        cpf_cnpj: "111.111.111-11",
        matricula: "SERV-001",
        agente_nome: "Agente Norte",
        contrato_codigo: "CTR-001",
        status_associado: "ciclo_aberto",
        status_associado_label: "Ativo",
        valor_total: "150.00",
      }),
      buildRow({
        id: 2,
        contrato_id: 2,
        associado_id: 102,
        nome: "João Souza",
        cpf_cnpj: "222.222.222-22",
        matricula: "SERV-002",
        agente_nome: "Agente Sul",
        contrato_codigo: "CTR-002",
        quantidade_parcelas: 0,
        quantidade_parcelas_contrato: 3,
        valor_total: "0.00",
        referencia_inicial: null,
        referencia_final: null,
        status_liquidacao: "elegivel_agora",
        status_operacional: "elegivel_agora",
        pode_liquidar_agora: true,
        status_associado: "apto_a_renovar",
        status_associado_label: "Apto para Renovação",
        parcelas: [
          {
            id: 21,
            numero: 1,
            referencia_mes: "2025-11-01",
            valor: "90.00",
            status: "descontado",
            data_vencimento: "2025-11-10",
            data_pagamento: "2025-11-10",
            observacao: "",
          },
          {
            id: 22,
            numero: 2,
            referencia_mes: "2025-12-01",
            valor: "90.00",
            status: "descontado",
            data_vencimento: "2025-12-10",
            data_pagamento: "2025-12-10",
            observacao: "",
          },
          {
            id: 23,
            numero: 3,
            referencia_mes: "2026-01-01",
            valor: "90.00",
            status: "descontado",
            data_vencimento: "2026-01-10",
            data_pagamento: "2026-01-10",
            observacao: "",
          },
        ],
      }),
      buildRow({
        id: 3,
        contrato_id: 3,
        associado_id: 103,
        nome: "Ana Renovação",
        cpf_cnpj: "333.333.333-33",
        matricula: "SERV-003",
        agente_nome: "Agente Centro",
        contrato_codigo: "CTR-003",
        quantidade_parcelas: 1,
        quantidade_parcelas_contrato: 2,
        valor_total: "60.00",
        referencia_inicial: "2026-03-01",
        referencia_final: "2026-03-01",
        status_associado: "solicitado_para_liquidacao",
        status_associado_label: "Solicitado para Liquidação",
        origem_solicitacao: "renovacao",
        status_renovacao: "solicitado_para_liquidacao",
        parcelas: [
          {
            id: 31,
            numero: 1,
            referencia_mes: "2026-02-01",
            valor: "60.00",
            status: "descontado",
            data_vencimento: "2026-02-10",
            data_pagamento: "2026-02-10",
            observacao: "",
          },
          {
            id: 32,
            numero: 2,
            referencia_mes: "2026-03-01",
            valor: "60.00",
            status: "em_aberto",
            data_vencimento: "2026-03-10",
            data_pagamento: null,
            observacao: "",
          },
        ],
      }),
    ];
    filaKpis = buildKpis();

    liquidadoRows = [
      buildRow({
        id: 4,
        contrato_id: 4,
        liquidacao_id: 44,
        associado_id: 104,
        nome: "Carlos Liquidado",
        status_liquidacao: "liquidado",
        status_operacional: "liquidado",
        pode_liquidar_agora: false,
        data_liquidacao: "2026-03-20",
        observacao: "Liquidação registrada.",
        origem_solicitacao: "administracao",
        quantidade_parcelas_contrato: 2,
        pode_reverter: true,
      }),
    ];
    liquidadoKpis = buildKpis({
      total_contratos: 1,
      total_parcelas: 2,
      valor_total: "150.00",
      liquidaveis_agora: 0,
      sem_parcelas_elegiveis: 0,
      ativas: 1,
      por_status_associado: {
        contrato_encerrado: 1,
      },
    });

    mockedApiFetch.mockImplementation(async (path, options = {}) => {
      const method = options.method ?? "GET";

      if (path === "associados/agentes" && method === "GET") {
        return [
          {
            id: 1,
            full_name: "Agente Norte",
            email: "agente.norte@abase.local",
            first_name: "Agente",
            last_name: "Norte",
          },
          {
            id: 2,
            full_name: "Agente Sul",
            email: "agente.sul@abase.local",
            first_name: "Agente",
            last_name: "Sul",
          },
          {
            id: 3,
            full_name: "Agente Centro",
            email: "agente.centro@abase.local",
            first_name: "Agente",
            last_name: "Centro",
          },
        ] as never;
      }

      if (path === "tesouraria/liquidacoes" && method === "GET") {
        const status = (options.query as { status?: string } | undefined)?.status;
        if (status === "liquidado") {
          return {
            count: liquidadoRows.length,
            next: null,
            previous: null,
            results: liquidadoRows,
            kpis: liquidadoKpis,
          } as never;
        }

        return {
          count: filaRows.length,
          next: null,
          previous: null,
          results: filaRows,
          kpis: filaKpis,
        } as never;
      }

      if (path === "tesouraria/liquidacoes/1/liquidar" && method === "POST") {
        const formData = options.formData as FormData;
        return {
          ...filaRows[0],
          liquidacao_id: 88,
          status_liquidacao: "liquidado",
          status_operacional: "liquidado",
          pode_liquidar_agora: false,
          data_liquidacao: String(formData.get("data_liquidacao") ?? ""),
          observacao: String(formData.get("observacao") ?? ""),
          origem_solicitacao: String(formData.get("origem_solicitacao") ?? ""),
          anexos: [
            {
              nome: "comprovante-1.pdf",
              url: "/media/liquidacoes/comprovante-1.pdf",
              arquivo_referencia: "liquidacao/comprovante-1.pdf",
              arquivo_disponivel_localmente: true,
              tipo_referencia: "local",
            },
          ],
        } as never;
      }

      throw new Error(`Unexpected apiFetch call: ${method} ${path}`);
    });
  });

  it("renderiza a fila com filtros avançados e sem os cards antigos", async () => {
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByRole("tab", { name: "Fila" })).toBeInTheDocument();
    expect(await screen.findByText("Maria Silva")).toBeInTheDocument();
    expect(screen.getByText("Total na Fila")).toBeInTheDocument();
    expect(screen.getByText("Liquidáveis Agora")).toBeInTheDocument();
    expect(screen.getByText("Sem Parcelas Elegíveis")).toBeInTheDocument();
    expect(screen.getAllByText("Valor Potencial").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: /Filtros avançados/i })).toBeInTheDocument();
    expect(screen.queryByText("Tipos de clientes")).not.toBeInTheDocument();
    expect(screen.queryByText(/Todos os associados aparecem aqui/i)).not.toBeInTheDocument();
    expect(screen.getByText("João Souza")).toBeInTheDocument();
    expect(screen.getByText("Apto para Renovação")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Filtros avançados/i }));
    expect(await screen.findByText("Todos os agentes")).toBeInTheDocument();
    expect(screen.getAllByRole("combobox").length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: "Filtros avançados" })).toBeInTheDocument();
    expect(screen.getByText("Etapa no fluxo")).toBeInTheDocument();
  });

  it("expande a linha com todas as parcelas do contrato", async () => {
    const user = userEvent.setup();
    renderPage();

    const row = (await screen.findByText("Maria Silva")).closest("tr");
    expect(row).not.toBeNull();

    await user.click(row as HTMLElement);

    expect(await screen.findByText(/Parcelas do contrato/i)).toBeInTheDocument();
    expect(screen.getByText("Parcela 1")).toBeInTheDocument();
    expect(screen.getByText("Parcela 4")).toBeInTheDocument();
  });

  it("permite encerramento direto quando não há parcelas aptas", async () => {
    renderPage();

    const row = (await screen.findByText("João Souza")).closest("tr");
    expect(row).not.toBeNull();
    expect(within(row as HTMLElement).getByRole("button", { name: "Liquidar" })).toBeEnabled();
    expect(
      within(row as HTMLElement).getByText("Pronto para inativação imediata, sem baixa de parcelas."),
    ).toBeInTheDocument();
    expect(
      within(row as HTMLElement).getByText("Encerramento sem parcelas pendentes"),
    ).toBeInTheDocument();
  });

  it("exige origem e comprovantes antes de confirmar a liquidação", async () => {
    const user = userEvent.setup();
    renderPage();

    const row = (await screen.findByText("Maria Silva")).closest("tr");
    expect(row).not.toBeNull();

    await user.click(within(row as HTMLElement).getByRole("button", { name: "Liquidar" }));

    const dialog = await screen.findByRole("dialog");
    const confirmarButton = within(dialog).getByRole("button", {
      name: "Confirmar liquidação",
    });
    expect(confirmarButton).toBeDisabled();

    await user.click(within(dialog).getByRole("combobox"));
    await user.click(await screen.findByRole("option", { name: "Agente" }));
    await user.click(within(dialog).getByRole("button", { name: "Selecionar comprovantes" }));
    await user.type(
      within(dialog).getByPlaceholderText("Descreva o encerramento e o contexto da liquidação..."),
      "Liquidação validada pela tesouraria.",
    );

    await waitFor(() => expect(confirmarButton).toBeEnabled());

    await user.click(confirmarButton);

    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith(
        "tesouraria/liquidacoes/1/liquidar",
        expect.objectContaining({
          method: "POST",
          formData: expect.any(FormData),
        }),
      ),
    );

    const liquidarCall = mockedApiFetch.mock.calls.find(
      ([path]) => path === "tesouraria/liquidacoes/1/liquidar",
    );
    expect(liquidarCall).toBeDefined();

    const formData = liquidarCall?.[1]?.formData as FormData;
    expect(formData.get("origem_solicitacao")).toBe("agente");
    expect(formData.getAll("comprovantes")).toHaveLength(2);

    await waitFor(() =>
      expect(mockedToast.success).toHaveBeenCalledWith("Liquidação registrada com sucesso."),
    );
  });

  it("trava a origem quando a liquidação veio do fluxo de renovação", async () => {
    const user = userEvent.setup();
    renderPage();

    const row = (await screen.findByText("Ana Renovação")).closest("tr");
    expect(row).not.toBeNull();

    await user.click(within(row as HTMLElement).getByRole("button", { name: "Liquidar" }));

    const dialog = await screen.findByRole("dialog");
    const origemSelect = within(dialog).getByRole("combobox");
    expect(origemSelect).toBeDisabled();
    expect(origemSelect).toHaveTextContent("Renovação");
    expect(
      screen.getByText("Origem preenchida automaticamente pelo fluxo de renovação."),
    ).toBeInTheDocument();
  });

  it("envia filtros avançados por agente, status, etapa e data", async () => {
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByText("Maria Silva")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Filtros avançados/i }));
    const filterCombos = await screen.findAllByRole("combobox");
    await user.click(filterCombos[0]);
    await user.click(await screen.findByRole("option", { name: "Agente Norte" }));

    await user.click(filterCombos[1]);
    await user.click(await screen.findByRole("option", { name: "Apto para Renovação" }));

    await user.click(filterCombos[2]);
    await user.click(await screen.findByRole("option", { name: "Tesouraria" }));

    const dateInputs = screen.getAllByPlaceholderText("dd/mm/aaaa");
    await user.clear(dateInputs[0]);
    await user.type(dateInputs[0], "2026-01-01");
    await user.clear(dateInputs[1]);
    await user.type(dateInputs[1], "2026-01-31");

    await user.click(screen.getByRole("button", { name: "Aplicar" }));

    await waitFor(() => {
      const getCalls = mockedApiFetch.mock.calls.filter(
        ([path, options]) => path === "tesouraria/liquidacoes" && (options?.method ?? "GET") === "GET",
      );
      expect(getCalls.length).toBeGreaterThan(1);
      const [, options] = getCalls.at(-1) ?? [];
      expect(options?.query).toEqual(
        expect.objectContaining({
          agente: "Agente Norte",
          status_associado: "apto_a_renovar",
          etapa_fluxo: "tesouraria",
          data_inicio: "2026-01-01",
          data_fim: "2026-01-31",
        }),
      );
    });
  });
});
