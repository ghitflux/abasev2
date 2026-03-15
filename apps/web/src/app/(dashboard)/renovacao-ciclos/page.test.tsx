import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import RenovacaoCiclosPage, { parseCompetenciaDate } from "./page";
import { apiFetch } from "@/lib/api/client";

const useV1RenovacaoCiclosMesesList = jest.fn();
const useV1RenovacaoCiclosList = jest.fn();
const useV1RenovacaoCiclosVisaoMensalRetrieve = jest.fn();
const useV1ImportacaoArquivoRetornoList = jest.fn();
const useV1ImportacaoArquivoRetornoDescontadosList = jest.fn();
const useV1ImportacaoArquivoRetornoNaoDescontadosList = jest.fn();
const useV1ImportacaoArquivoRetornoPendenciasManuaisList = jest.fn();

jest.mock("@/gen", () => ({
  useV1RenovacaoCiclosMesesList: (...args: unknown[]) =>
    useV1RenovacaoCiclosMesesList(...args),
  useV1RenovacaoCiclosList: (...args: unknown[]) =>
    useV1RenovacaoCiclosList(...args),
  useV1RenovacaoCiclosVisaoMensalRetrieve: (...args: unknown[]) =>
    useV1RenovacaoCiclosVisaoMensalRetrieve(...args),
  useV1ImportacaoArquivoRetornoList: (...args: unknown[]) =>
    useV1ImportacaoArquivoRetornoList(...args),
  useV1ImportacaoArquivoRetornoDescontadosList: (...args: unknown[]) =>
    useV1ImportacaoArquivoRetornoDescontadosList(...args),
  useV1ImportacaoArquivoRetornoNaoDescontadosList: (...args: unknown[]) =>
    useV1ImportacaoArquivoRetornoNaoDescontadosList(...args),
  useV1ImportacaoArquivoRetornoPendenciasManuaisList: (...args: unknown[]) =>
    useV1ImportacaoArquivoRetornoPendenciasManuaisList(...args),
}));

jest.mock("@/lib/api/client", () => ({
  apiFetch: jest.fn(),
}));

jest.mock("sonner", () => ({
  toast: {
    success: jest.fn(),
    error: jest.fn(),
  },
}));

const mockedApiFetch = jest.mocked(apiFetch);

beforeAll(() => {
  if (!Element.prototype.hasPointerCapture) {
    Element.prototype.hasPointerCapture = () => false;
  }
  if (!Element.prototype.setPointerCapture) {
    Element.prototype.setPointerCapture = () => undefined;
  }
  if (!Element.prototype.releasePointerCapture) {
    Element.prototype.releasePointerCapture = () => undefined;
  }
});

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <RenovacaoCiclosPage />
    </QueryClientProvider>,
  );
}

async function openMonthDialog(user: ReturnType<typeof userEvent.setup>, monthLabel: string) {
  const monthCardTitle = await screen.findByText(monthLabel);
  const monthCard = monthCardTitle.closest('[data-slot="card"]');

  expect(monthCard).not.toBeNull();

  await user.click(
    within(monthCard as HTMLElement).getByRole("button", { name: /Ampliar tabela/i }),
  );

  return screen.findByRole("dialog");
}

const cyclePayload = {
  count: 2,
  next: null,
  previous: null,
  results: [
    {
      id: 1,
      competencia: "2026-02",
      contrato_id: 1,
      contrato_codigo: "CTR-001",
      associado_id: 1,
      nome_associado: "Maria de Jesus Santana Costa",
      cpf_cnpj: "23993596315",
      orgao_publico: "Órgão Teste",
      ciclo_id: 1,
      ciclo_numero: 1,
      status_ciclo: "ciclo_renovado",
      status_parcela: "descontado",
      status_visual: "ciclo_renovado",
      matricula: "MAT-10049",
      agente_responsavel: "Carlos Mendes",
      parcelas_pagas: 3,
      parcelas_total: 3,
      valor_mensalidade: "30.00",
      valor_parcela: "30.00",
      data_pagamento: "2026-02-10",
      orgao_pagto_nome: "SEC. EST. ADMIN. E PREVIDEN.",
      resultado_importacao: "baixa_efetuada",
      status_codigo_etipi: "1",
      status_descricao_etipi: "Lançado e Efetivado",
      gerou_encerramento: true,
      gerou_novo_ciclo: true,
    },
    {
      id: 2,
      competencia: "2026-02",
      contrato_id: 2,
      contrato_codigo: "CTR-002",
      associado_id: 2,
      nome_associado: "João Carlos da Silva",
      cpf_cnpj: "11122233344",
      orgao_publico: "Órgão Teste",
      ciclo_id: 2,
      ciclo_numero: 1,
      status_ciclo: "em_aberto",
      status_parcela: "em_aberto",
      status_visual: "em_aberto",
      matricula: "MAT-20001",
      agente_responsavel: "Ana Souza",
      parcelas_pagas: 1,
      parcelas_total: 3,
      valor_mensalidade: "35.00",
      valor_parcela: "35.00",
      data_pagamento: null,
      orgao_pagto_nome: "SEC. EST. ADMIN. E PREVIDEN.",
      resultado_importacao: "nao_descontado",
      status_codigo_etipi: "2",
      status_descricao_etipi: "Não Lançado por Falta de Margem Temporariamente",
      gerou_encerramento: false,
      gerou_novo_ciclo: false,
    },
  ],
};

const importacaoPayload = {
  count: 4,
  next: null,
  previous: null,
  results: [
    {
      id: 11,
      arquivo_nome: "retorno_fevereiro_2026.txt",
      formato: "txt",
      sistema_origem: "ETIPI/iNETConsig",
      competencia: "2026-02-01",
      competencia_display: "02/2026",
      total_registros: 639,
      processados: 639,
      nao_encontrados: 55,
      erros: 0,
      status: "concluido",
      resumo: {
        baixa_efetuada: 497,
        nao_descontado: 71,
        pendencias_manuais: 16,
        nao_encontrado: 55,
        ciclo_aberto: 0,
      },
      financeiro: {
        ok: 497,
        total: 639,
        faltando: 142,
        esperado: "47364.38",
        recebido: "45491.38",
        pendente: "1873.00",
        percentual: 96.0,
        mensalidades: {
          recebido: "44351.38",
          esperado: "45651.38",
        },
        valores_30_50: {
          recebido: "1140.00",
          esperado: "1713.00",
        },
      },
      uploaded_by_nome: "Tes ABASE",
      created_at: "2026-03-12T08:00:00Z",
      processado_em: "2026-03-12T08:10:00Z",
    },
    {
      id: 12,
      arquivo_nome: "retorno_janeiro_2026.txt",
      formato: "txt",
      sistema_origem: "ETIPI/iNETConsig",
      competencia: "2026-01-01",
      competencia_display: "01/2026",
      total_registros: 588,
      processados: 588,
      nao_encontrados: 25,
      erros: 0,
      status: "concluido",
      resumo: {
        baixa_efetuada: 466,
        nao_descontado: 122,
        pendencias_manuais: 0,
        nao_encontrado: 25,
        ciclo_aberto: 0,
      },
      financeiro: {
        ok: 466,
        total: 588,
        faltando: 122,
        esperado: "138996.42",
        recebido: "113099.84",
        pendente: "25896.58",
        percentual: 81.4,
        mensalidades: {
          recebido: "110667.17",
          esperado: "136917.92",
        },
        valores_30_50: {
          recebido: "1770.00",
          esperado: "1990.00",
        },
      },
      uploaded_by_nome: "Tes ABASE",
      created_at: "2026-02-12T08:00:00Z",
      processado_em: "2026-02-12T08:10:00Z",
    },
    {
      id: 13,
      arquivo_nome: "retorno_dezembro_2025.txt",
      formato: "txt",
      sistema_origem: "ETIPI/iNETConsig",
      competencia: "2025-12-01",
      competencia_display: "12/2025",
      total_registros: 506,
      processados: 506,
      nao_encontrados: 12,
      erros: 0,
      status: "concluido",
      resumo: {
        baixa_efetuada: 402,
        nao_descontado: 104,
        pendencias_manuais: 0,
        nao_encontrado: 12,
        ciclo_aberto: 4,
      },
      financeiro: {
        ok: 402,
        total: 506,
        faltando: 104,
        esperado: "119860.88",
        recebido: "106102.44",
        pendente: "13758.44",
        percentual: 88.5,
        mensalidades: {
          recebido: "104612.44",
          esperado: "118100.88",
        },
        valores_30_50: {
          recebido: "1490.00",
          esperado: "1760.00",
        },
      },
      uploaded_by_nome: "Tes ABASE",
      created_at: "2026-01-12T08:00:00Z",
      processado_em: "2026-01-12T08:10:00Z",
    },
    {
      id: 14,
      arquivo_nome: "retorno_novembro_2025.txt",
      formato: "txt",
      sistema_origem: "ETIPI/iNETConsig",
      competencia: "2025-11-01",
      competencia_display: "11/2025",
      total_registros: 480,
      processados: 480,
      nao_encontrados: 10,
      erros: 0,
      status: "concluido",
      resumo: {
        baixa_efetuada: 390,
        nao_descontado: 90,
        pendencias_manuais: 0,
        nao_encontrado: 10,
        ciclo_aberto: 5,
      },
      financeiro: {
        ok: 390,
        total: 480,
        faltando: 90,
        esperado: "115000.00",
        recebido: "101000.00",
        pendente: "14000.00",
        percentual: 87.8,
        mensalidades: {
          recebido: "99700.00",
          esperado: "113200.00",
        },
        valores_30_50: {
          recebido: "1300.00",
          esperado: "1800.00",
        },
      },
      uploaded_by_nome: "Tes ABASE",
      created_at: "2025-12-12T08:00:00Z",
      processado_em: "2025-12-12T08:10:00Z",
    },
  ],
};

const visaoMensalPayload = {
  competencia: "02/2026",
  total_associados: 1,
  ciclo_renovado: 1,
  apto_a_renovar: 0,
  em_aberto: 0,
  ciclo_iniciado: 1,
  inadimplente: 0,
  esperado_total: "30.00",
  arrecadado_total: "30.00",
  percentual_arrecadado: 100,
};

const retornoItemsPayload = {
  count: 1,
  next: null,
  previous: null,
  results: [
    {
      id: 100,
      linha_numero: 1,
      cpf_cnpj: "23993596315",
      matricula_servidor: "MAT-10049",
      nome_servidor: "Maria de Jesus Santana Costa",
      cargo: "Assistente",
      competencia: "02/2026",
      valor_descontado: "30.00",
      status_codigo: "1",
      status_desconto: "efetivado",
      status_descricao: "Lançado e efetivado",
      motivo_rejeicao: null,
      orgao_codigo: "002",
      orgao_pagto_codigo: "002",
      orgao_pagto_nome: "SEC. EST. ADMIN. E PREVIDEN.",
      resultado_processamento: "baixa_efetuada",
      observacao: "Parcela baixada automaticamente.",
      gerou_encerramento: true,
      gerou_novo_ciclo: true,
      associado_id: 1,
      associado_nome: "Maria de Jesus Santana Costa",
      associado_matricula: "MAT-10049",
      agente_responsavel: "Carlos Mendes",
      contrato_codigo: "CTR-001",
    },
  ],
};

const retornoFinanceiroPayload = {
  resumo: importacaoPayload.results[0].financeiro,
  rows: [
    {
      id: 100,
      associado_id: 1,
      associado_nome: "Maria de Jesus Santana Costa",
      agente_responsavel: "Carlos Mendes",
      matricula: "MAT-10049",
      cpf_cnpj: "23993596315",
      valor: "30.00",
      esperado: "30.00",
      recebido: "30.00",
      status_code: "1",
      status_label: "Efetivado",
      ok: true,
      situacao_code: "ok",
      situacao_label: "Concluído",
      orgao_pagto: "SEC. EST. ADMIN. E PREVIDEN.",
      relatorio: "Maria de Jesus Santana Costa",
      manual_status: null,
      manual_valor: null,
      manual_forma_pagamento: null,
      manual_paid_at: null,
      manual_comprovante_path: null,
      categoria: "valores_30_50",
    },
    {
      id: 101,
      associado_id: 2,
      associado_nome: "João Carlos da Silva",
      agente_responsavel: "Ana Souza",
      matricula: "MAT-20001",
      cpf_cnpj: "11122233344",
      valor: "35.00",
      esperado: "35.00",
      recebido: "0.00",
      status_code: "2",
      status_label: "Sem margem (temp.)",
      ok: false,
      situacao_code: "warn",
      situacao_label: "No arquivo",
      orgao_pagto: "SEC. EST. ADMIN. E PREVIDEN.",
      relatorio: "João Carlos da Silva",
      manual_status: null,
      manual_valor: null,
      manual_forma_pagamento: null,
      manual_paid_at: null,
      manual_comprovante_path: null,
      categoria: "outros",
    },
  ],
};

describe("RenovacaoCiclosPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();

    useV1RenovacaoCiclosMesesList.mockReturnValue({
      data: [
        { id: "2026-02", label: "02/2026" },
        { id: "2026-01", label: "01/2026" },
        { id: "2025-12", label: "12/2025" },
      ],
    });
    useV1RenovacaoCiclosList.mockReturnValue({ data: cyclePayload });
    useV1RenovacaoCiclosVisaoMensalRetrieve.mockReturnValue({
      data: visaoMensalPayload,
    });
    useV1ImportacaoArquivoRetornoList.mockImplementation((params?: { page_size?: number }) => ({
      data: {
        ...importacaoPayload,
        results: importacaoPayload.results.slice(0, params?.page_size ?? importacaoPayload.results.length),
      },
    }));
    useV1ImportacaoArquivoRetornoDescontadosList.mockReturnValue({
      data: retornoItemsPayload,
    });
    useV1ImportacaoArquivoRetornoNaoDescontadosList.mockReturnValue({
      data: { ...retornoItemsPayload, results: [] },
    });
    useV1ImportacaoArquivoRetornoPendenciasManuaisList.mockReturnValue({
      data: { ...retornoItemsPayload, results: [] },
    });
    mockedApiFetch.mockImplementation(async (path, options) => {
      if (path === "importacao/arquivo-retorno") {
        const competencia = options?.query && "competencia" in options.query
          ? options.query.competencia
          : undefined;
        if (!competencia) {
          return {
            ...importacaoPayload,
            results: importacaoPayload.results.slice(0, Number(options?.query?.page_size ?? importacaoPayload.results.length)),
          };
        }

        const match = importacaoPayload.results.filter((item) =>
          item.competencia.startsWith(String(competencia)),
        );

        return {
          results: match.slice(0, Number(options?.query?.page_size ?? match.length)),
        };
      }

      if (typeof path === "string" && /^importacao\/arquivo-retorno\/\d+\/financeiro$/.test(path)) {
        const match = /^importacao\/arquivo-retorno\/(\d+)\/financeiro$/.exec(path);
        const arquivoId = Number(match?.[1] ?? 0);
        const arquivoFinanceiro =
          importacaoPayload.results.find((item) => item.id === arquivoId)?.financeiro ??
          retornoFinanceiroPayload.resumo;

        return {
          resumo: arquivoFinanceiro,
          rows: retornoFinanceiroPayload.rows.map((row, index) => ({
            ...row,
            id: arquivoId * 100 + index,
          })),
        };
      }

      throw new Error(`Unexpected apiFetch path: ${path}`);
    });
  });

  it("renderiza as novas seções da rota com cards mensais e detalhamento mensal", async () => {
    renderPage();

    expect(screen.getByText("Renovação de Ciclos")).toBeInTheDocument();
    expect(screen.getByText("Gestão detalhada por mês")).toBeInTheDocument();
    expect(screen.getByText("Detalhamento mensal já conciliado")).toBeInTheDocument();
    expect(screen.getByText("Arquivos retorno")).toBeInTheDocument();
    expect(screen.getByText(/Monitoramento de ciclos/i)).toBeInTheDocument();
    expect((await screen.findAllByText("Maria de Jesus Santana Costa")).length).toBeGreaterThan(0);
    expect(await screen.findByText("Carlos Mendes")).toBeInTheDocument();
    expect(await screen.findByText("retorno_fevereiro_2026.txt")).toBeInTheDocument();
    expect(await screen.findByText("retorno_janeiro_2026.txt")).toBeInTheDocument();
    expect(await screen.findByText("retorno_dezembro_2025.txt")).toBeInTheDocument();
    expect(screen.queryByText("retorno_novembro_2025.txt")).not.toBeInTheDocument();
    expect(screen.getAllByText("Quitados").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Mensalidades").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Valores 30/50").length).toBeGreaterThan(0);
  });

  it("faz parse local de YYYY-MM-DD sem deslocar fevereiro para janeiro", () => {
    const date = parseCompetenciaDate("2026-02-01");

    expect(date).toBeDefined();
    expect(date?.getFullYear()).toBe(2026);
    expect(date?.getMonth()).toBe(1);
    expect(date?.getDate()).toBe(1);
  });

  it("lista arquivos retorno sem limitar a um unico card no carregamento inicial", async () => {
    renderPage();

    await waitFor(() =>
      expect(useV1ImportacaoArquivoRetornoList).toHaveBeenCalledWith(
        expect.objectContaining({
          competencia: undefined,
          periodo: undefined,
          page_size: 3,
        }),
        expect.anything(),
      ),
    );
  });

  it("carrega mais arquivos retorno em blocos de tres", async () => {
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByText("retorno_dezembro_2025.txt")).toBeInTheDocument();
    expect(screen.queryByText("retorno_novembro_2025.txt")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Ver mais arquivos/i }));

    expect(await screen.findByText("retorno_novembro_2025.txt")).toBeInTheDocument();
    await waitFor(() =>
      expect(useV1ImportacaoArquivoRetornoList).toHaveBeenCalledWith(
        expect.objectContaining({
          page_size: 6,
        }),
        expect.anything(),
      ),
    );
  });

  it("expande o detalhamento do arquivo retorno com a tabela do associado", async () => {
    const user = userEvent.setup();
    renderPage();

    const expandButtons = await screen.findAllByRole("button", {
      name: /Detalhamento do arquivo/i,
    });
    await user.click(expandButtons[0] as HTMLElement);

    expect((await screen.findAllByText("Agente responsável")).length).toBeGreaterThan(0);
    expect((await screen.findAllByText("Esperado")).length).toBeGreaterThan(0);
    expect((await screen.findAllByRole("link", { name: /Ver detalhes do associado/i })).length).toBeGreaterThan(0);
    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith("importacao/arquivo-retorno/11/financeiro"),
    );
  });

  it("usa o detalhamento financeiro no card mensal quando a competencia tem arquivo retorno", async () => {
    const user = userEvent.setup();
    renderPage();

    const dialog = await openMonthDialog(user, "Fevereiro de 2026");

    expect(within(dialog).getByText("Gestão financeira de Fevereiro de 2026")).toBeInTheDocument();
    expect(
      within(dialog).getByText(
        "Associados do arquivo retorno, valores esperados, recebidos e situação conciliada.",
      ),
    ).toBeInTheDocument();
    expect(within(dialog).getByText("Esperado")).toBeInTheDocument();
    expect(within(dialog).getByText("Recebido")).toBeInTheDocument();
    expect(within(dialog).queryByText(/Parcelas do ciclo/i)).not.toBeInTheDocument();
  });

  it("mostra a descrição do status ETIPI no detalhamento mensal", async () => {
    const user = userEvent.setup();
    renderPage();

    const detailCard = screen
      .getByText("Detalhamento mensal já conciliado")
      .closest('[data-slot="card"]');

    expect(detailCard).not.toBeNull();

    const summaryRow = within(detailCard as HTMLElement)
      .getAllByRole("row")
      .find(
        (row) =>
          within(row).queryByText("Maria de Jesus Santana Costa") &&
          within(row).queryByText("CTR-001"),
      );

    expect(summaryRow).not.toBeNull();

    await user.click(summaryRow as HTMLTableRowElement);

    expect(await screen.findByText("1 - Lançado e Efetivado")).toBeInTheDocument();
  });

  it("permite busca com autocomplete dentro da tabela ampliada do mês", async () => {
    const user = userEvent.setup();
    renderPage();

    const dialog = await openMonthDialog(user, "Fevereiro de 2026");
    const [searchTrigger] = within(dialog).getAllByRole("combobox");

    await user.click(searchTrigger as HTMLElement);
    const matchingOptions = await screen.findAllByRole("option", { name: /MAT-20001/i });
    await user.click(matchingOptions[0]);

    expect(within(dialog).getByText("João Carlos da Silva")).toBeInTheDocument();
    expect(within(dialog).queryByText("Maria de Jesus Santana Costa")).not.toBeInTheDocument();
    expect(within(dialog).getByText("Sem margem (temp.)")).toBeInTheDocument();
  });

  it("abre o modal de status ao clicar no KPI do card mensal", async () => {
    const user = userEvent.setup();
    renderPage();

    const monthCardTitle = await screen.findByText("Fevereiro de 2026");
    const monthCard = monthCardTitle.closest('[data-slot="card"]');

    expect(monthCard).not.toBeNull();

    await user.click(
      within(monthCard as HTMLElement).getByRole("button", { name: /Renovados/i }),
    );

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("Renovados em Fevereiro de 2026")).toBeInTheDocument();
    expect(within(dialog).getByText("Maria de Jesus Santana Costa")).toBeInTheDocument();
    expect(within(dialog).getByText("Por página")).toBeInTheDocument();
  });

  it("abre o modal do detalhamento mensal ao clicar no KPI total", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("button", { name: /^Total/i }));

    const dialog = await screen.findByRole("dialog");
    expect(
      within(dialog).getByText("Total de associados em Fevereiro de 2026"),
    ).toBeInTheDocument();
    expect(within(dialog).getByText("Maria de Jesus Santana Costa")).toBeInTheDocument();
    expect(within(dialog).getByText("João Carlos da Silva")).toBeInTheDocument();
    expect(within(dialog).getByText("Por página")).toBeInTheDocument();
  });

  it("abre o modal do monitoramento de ciclos ao clicar no KPI correspondente", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("button", { name: /Mês 1\/3 \(Início\)/i }));

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("Mês 1/3 (Início) em Fevereiro de 2026")).toBeInTheDocument();
    expect(within(dialog).getByText("João Carlos da Silva")).toBeInTheDocument();
    expect(within(dialog).getByText("Por página")).toBeInTheDocument();
  });

  it("abre o modal do arquivo retorno ao clicar no KPI quitados", async () => {
    const user = userEvent.setup();
    renderPage();

    const returnCardTitle = await screen.findByText("retorno_fevereiro_2026.txt");
    const returnCard = returnCardTitle.closest('[data-slot="card"]');

    expect(returnCard).not.toBeNull();

    await user.click(
      within(returnCard as HTMLElement).getByRole("button", { name: /Quitados/i }),
    );

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("Quitados no arquivo Fevereiro de 2026")).toBeInTheDocument();
    expect(await within(dialog).findByText("Maria de Jesus Santana Costa")).toBeInTheDocument();
    expect(within(dialog).getByText("Por página")).toBeInTheDocument();
  });

  it("exibe CPF, matrícula e seletor de paginação no detalhamento mensal", async () => {
    renderPage();

    expect(await screen.findByRole("columnheader", { name: "CPF" })).toBeInTheDocument();
    expect(await screen.findByRole("columnheader", { name: "Matrícula" })).toBeInTheDocument();
    expect(screen.getByText("Por página")).toBeInTheDocument();
  });
});
