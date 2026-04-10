import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";

import TesourariaRefinanciamentosPage from "./page";
import type { RefinanciamentoItem, RefinanciamentoResumo } from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";

jest.mock("@/lib/api/client", () => ({
  apiFetch: jest.fn(),
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
      value={value ? value.toISOString().slice(0, 10) : ""}
      onChange={(event) =>
        onChange?.(event.target.value ? new Date(`${event.target.value}T12:00:00`) : undefined)
      }
    />
  ),
}));

const mockedApiFetch = jest.mocked(apiFetch);

function buildRefinanciamento(overrides: Partial<RefinanciamentoItem> = {}): RefinanciamentoItem {
  return {
    id: overrides.id ?? 1,
    contrato_id: overrides.contrato_id ?? 11,
    contrato_codigo: overrides.contrato_codigo ?? "CTR-REN-001",
    associado_id: overrides.associado_id ?? 101,
    associado_nome: overrides.associado_nome ?? "Associado Renovação",
    cpf_cnpj: overrides.cpf_cnpj ?? "12345678900",
    matricula: overrides.matricula ?? "MAT-001",
    matricula_display: overrides.matricula_display ?? "MAT-001",
    agente: overrides.agente ?? { id: 2, full_name: "Agente Coordenação" },
    solicitado_por: overrides.solicitado_por,
    aprovado_por: overrides.aprovado_por,
    bloqueado_por: overrides.bloqueado_por,
    efetivado_por: overrides.efetivado_por,
    reviewed_by: overrides.reviewed_by,
    competencia_solicitada: overrides.competencia_solicitada ?? "2026-04-01",
    status: overrides.status ?? "aprovado_para_renovacao",
    valor_refinanciamento: overrides.valor_refinanciamento ?? "1200.00",
    valor_liberado_associado: overrides.valor_liberado_associado ?? "900.00",
    repasse_agente: overrides.repasse_agente ?? "120.00",
    ciclo_key: overrides.ciclo_key ?? "2026-02|2026-03|2026-04",
    referencias: overrides.referencias ?? ["2026-02-01", "2026-03-01", "2026-04-01"],
    itens: overrides.itens ?? [],
    mensalidades_pagas: overrides.mensalidades_pagas ?? 3,
    mensalidades_total: overrides.mensalidades_total ?? 3,
    numero_ciclos: overrides.numero_ciclos ?? 1,
    refinanciamento_numero: overrides.refinanciamento_numero ?? 1,
    pagamento_status: overrides.pagamento_status ?? "pendente",
    legacy_refinanciamento_id: overrides.legacy_refinanciamento_id ?? null,
    origem: overrides.origem ?? "operacional",
    data_renovacao: overrides.data_renovacao ?? null,
    origem_renovacao: overrides.origem_renovacao ?? "manual",
    data_primeiro_ciclo_ativado: overrides.data_primeiro_ciclo_ativado ?? null,
    data_ativacao_ciclo: overrides.data_ativacao_ciclo ?? null,
    origem_data_ativacao: overrides.origem_data_ativacao ?? "manual",
    data_solicitacao_renovacao: overrides.data_solicitacao_renovacao ?? "2026-04-01T10:00:00Z",
    data_solicitacao: overrides.data_solicitacao ?? "2026-04-01T10:00:00Z",
    ativacao_inferida: overrides.ativacao_inferida ?? false,
    etapa_operacional: overrides.etapa_operacional ?? "aprovado_para_renovacao",
    motivo_apto_renovacao: overrides.motivo_apto_renovacao ?? "Pronto para pagamento",
    motivo_bloqueio: overrides.motivo_bloqueio,
    observacao: overrides.observacao,
    analista_note: overrides.analista_note ?? "",
    coordenador_note: overrides.coordenador_note ?? "",
    reviewed_at: overrides.reviewed_at ?? null,
    executado_em: overrides.executado_em ?? null,
    created_at: overrides.created_at ?? "2026-03-20T09:00:00Z",
    updated_at: overrides.updated_at ?? "2026-04-02T14:00:00Z",
    auditoria: overrides.auditoria ?? {
      solicitado_por: null,
      aprovado_por: null,
      bloqueado_por: null,
      efetivado_por: null,
      reviewed_by: null,
      reviewed_at: null,
      analista_note: "",
      coordenador_note: "",
      observacao: "",
      motivo_bloqueio: "",
    },
    comprovantes: overrides.comprovantes ?? [],
  };
}

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

beforeEach(() => {
  mockedApiFetch.mockImplementation(async (path, options) => {
    if (path === "tesouraria/refinanciamentos/resumo") {
      const resumo: RefinanciamentoResumo = {
        total: 3,
        em_analise: 0,
        assumidos: 0,
        aprovados: 0,
        efetivados: 1,
        concluidos: 1,
        bloqueados: 1,
        revertidos: 0,
        desativados: 0,
        em_fluxo: 1,
        com_anexo_agente: 0,
        repasse_total: "120.00",
      };
      return resumo;
    }

    if (path === "tesouraria/refinanciamentos") {
      const status = options?.query?.status;
      if (Array.isArray(status) && status.includes("aprovado_para_renovacao")) {
        return {
          count: 1,
          next: null,
          previous: null,
          results: [buildRefinanciamento()],
        };
      }
      if (Array.isArray(status) && status.includes("efetivado")) {
        return {
          count: 1,
          next: null,
          previous: null,
          results: [
            buildRefinanciamento({
              id: 2,
              status: "efetivado",
              executado_em: "2026-04-05T10:00:00Z",
              data_ativacao_ciclo: "2026-04-05T10:00:00Z",
            }),
          ],
        };
      }
      if (Array.isArray(status) && status.includes("bloqueado")) {
        return {
          count: 1,
          next: null,
          previous: null,
          results: [
            buildRefinanciamento({
              id: 3,
              status: "bloqueado",
              updated_at: "2026-04-06T10:00:00Z",
            }),
          ],
        };
      }
    }

    throw new Error(`Unexpected path: ${String(path)}`);
  });
});

function renderPage() {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return render(
    <QueryClientProvider client={client}>
      <TesourariaRefinanciamentosPage />
    </QueryClientProvider>,
  );
}

it("renderiza secoes operacionais e consulta apenas aprovados para a fila pendente", async () => {
  renderPage();

  await waitFor(() =>
    expect(mockedApiFetch).toHaveBeenCalledWith(
      "tesouraria/refinanciamentos",
      expect.objectContaining({
        query: expect.objectContaining({
          status: ["aprovado_para_renovacao"],
        }),
      }),
    ),
  );

  expect(screen.getByText("Contratos aprovados para pagamento")).toBeInTheDocument();
  expect(screen.getByText("Contratos concluídos")).toBeInTheDocument();
  expect(screen.getByText("Contratos bloqueados ou revertidos")).toBeInTheDocument();
  await waitFor(() =>
    expect(screen.getAllByRole("button", { name: /Ver detalhes do associado/i }).length).toBeGreaterThan(0),
  );
  await waitFor(() =>
    expect(screen.getByRole("button", { name: /Efetivar renovação/i })).toBeDisabled(),
  );

  const statusCalls = mockedApiFetch.mock.calls
    .filter(([path]) => path === "tesouraria/refinanciamentos")
    .map(([, options]) => options?.query?.status);
  expect(statusCalls).toEqual(
    expect.arrayContaining([
      ["aprovado_para_renovacao"],
      ["efetivado"],
      ["bloqueado", "revertido", "desativado"],
    ]),
  );
});

it("separa termo do agente dos comprovantes de pagamento e mostra o valor liberado do associado", async () => {
  mockedApiFetch.mockImplementation(async (path, options) => {
    if (path === "tesouraria/refinanciamentos/resumo") {
      return {
        total: 1,
        em_analise: 0,
        assumidos: 0,
        aprovados: 0,
        efetivados: 0,
        concluidos: 0,
        bloqueados: 0,
        revertidos: 0,
        desativados: 0,
        em_fluxo: 1,
        com_anexo_agente: 0,
        repasse_total: "73.50",
      } satisfies RefinanciamentoResumo;
    }

    if (path === "tesouraria/refinanciamentos") {
      const status = options?.query?.status;
      if (Array.isArray(status) && status.includes("aprovado_para_renovacao")) {
        return {
          count: 1,
          next: null,
          previous: null,
          results: [
            buildRefinanciamento({
              associado_nome: "JUSTINO DA SILVA LEAL",
              valor_refinanciamento: "1881.03",
              valor_liberado_associado: "735.00",
              repasse_agente: "73.50",
              comprovantes: [
                {
                  id: 1,
                  refinanciamento: 1,
                  contrato: 11,
                  ciclo: 3,
                  tipo: "termo_antecipacao",
                  papel: "agente",
                  arquivo: "",
                  arquivo_referencia: "refinanciamentos/renovacoes/termo-justino.pdf",
                  arquivo_disponivel_localmente: false,
                  tipo_referencia: "referencia_path",
                  nome_original: "ANTECIPAÇÃO- JUSTINO DA SILVA LEAL.pdf",
                  created_at: "2026-04-01T10:00:00Z",
                },
              ],
            }),
          ],
        };
      }
      return {
        count: 0,
        next: null,
        previous: null,
        results: [],
      };
    }

    throw new Error(`Unexpected path: ${String(path)}`);
  });

  renderPage();

  expect(await screen.findByText("Termo do agente")).toBeInTheDocument();
  expect(screen.getByText("Comp. associado")).toBeInTheDocument();
  expect(screen.getByText("Comp. agente")).toBeInTheDocument();
  expect(screen.getByText("ANTECIPAÇÃO- JUSTINO DA SILVA LEAL.pdf")).toBeInTheDocument();
  expect(screen.getByText("Referência")).toBeInTheDocument();
  expect(screen.queryByText("Legado")).not.toBeInTheDocument();
  await waitFor(() =>
    expect(
      screen.getAllByText((_, element) => element?.textContent?.includes("735,00") ?? false).length,
    ).toBeGreaterThan(0),
  );
  expect(
    screen.queryAllByText((_, element) => element?.textContent?.includes("1.881,03") ?? false),
  ).toHaveLength(0);
});
