import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import ImportacaoPage from "./page";
import { apiFetch } from "@/lib/api/client";

const useV1ImportacaoArquivoRetornoList = jest.fn();
const useV1ImportacaoArquivoRetornoUltimaRetrieve = jest.fn();
const useV1ImportacaoArquivoRetornoFinanceiroRetrieve = jest.fn();
const useV1ImportacaoArquivoRetornoDescontadosList = jest.fn();
const useV1ImportacaoArquivoRetornoNaoDescontadosList = jest.fn();
const useV1ImportacaoArquivoRetornoPendenciasManuaisList = jest.fn();
const useV1ImportacaoArquivoRetornoEncerramentosList = jest.fn();
const useV1ImportacaoArquivoRetornoNovosCiclosList = jest.fn();

jest.mock("@/gen", () => ({
  useV1ImportacaoArquivoRetornoList: (...args: unknown[]) =>
    useV1ImportacaoArquivoRetornoList(...args),
  useV1ImportacaoArquivoRetornoUltimaRetrieve: (...args: unknown[]) =>
    useV1ImportacaoArquivoRetornoUltimaRetrieve(...args),
  useV1ImportacaoArquivoRetornoFinanceiroRetrieve: (...args: unknown[]) =>
    useV1ImportacaoArquivoRetornoFinanceiroRetrieve(...args),
  useV1ImportacaoArquivoRetornoDescontadosList: (...args: unknown[]) =>
    useV1ImportacaoArquivoRetornoDescontadosList(...args),
  useV1ImportacaoArquivoRetornoNaoDescontadosList: (...args: unknown[]) =>
    useV1ImportacaoArquivoRetornoNaoDescontadosList(...args),
  useV1ImportacaoArquivoRetornoPendenciasManuaisList: (...args: unknown[]) =>
    useV1ImportacaoArquivoRetornoPendenciasManuaisList(...args),
  useV1ImportacaoArquivoRetornoEncerramentosList: (...args: unknown[]) =>
    useV1ImportacaoArquivoRetornoEncerramentosList(...args),
  useV1ImportacaoArquivoRetornoNovosCiclosList: (...args: unknown[]) =>
    useV1ImportacaoArquivoRetornoNovosCiclosList(...args),
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

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <ImportacaoPage />
    </QueryClientProvider>,
  );
}

const latestImport = {
  id: 12,
  arquivo_nome: "retorno_etipi_052025.txt",
  formato: "txt",
  sistema_origem: "ETIPI/iNETConsig",
  competencia: "2025-05-01",
  competencia_display: "05/2025",
  total_registros: 4,
  processados: 4,
  associados_importados: 1,
  nao_encontrados: 1,
  erros: 0,
  status: "concluido",
  resumo: {
    baixa_efetuada: 1,
    nao_descontado: 1,
    pendencias_manuais: 1,
    nao_encontrado: 1,
    efetivados: 1,
    nao_descontados: 1,
    encerramentos: 1,
    novos_ciclos: 1,
  },
  financeiro: {
    ok: 2,
    total: 4,
    faltando: 2,
    esperado: "90.00",
    recebido: "60.00",
    pendente: "30.00",
    percentual: 66.7,
    mensalidades: {
      recebido: "30.00",
      esperado: "60.00",
    },
    valores_30_50: {
      recebido: "30.00",
      esperado: "30.00",
    },
  },
  uploaded_by_nome: "Tes ABASE",
  created_at: "2026-03-11T08:00:00Z",
  processado_em: "2026-03-11T08:01:00Z",
  arquivo_url: "/media/retorno.txt",
};

const dryRunResultado = {
  kpis: {
    total_no_arquivo: 4,
    atualizados: 3,
    baixa_efetuada: 1,
    nao_descontado: 1,
    nao_encontrado: 1,
    associados_importados: 1,
    pendencia_manual: 1,
    ciclo_aberto: 0,
    valor_previsto: "90.00",
    valor_real: "30.00",
    aptos_a_renovar: 1,
    associados_inativos_com_desconto: 0,
    valores_30_50: {
      descontaram: { count: 1, valor_total: "30.00" },
      nao_descontaram: { count: 1, valor_total: "30.00" },
    },
    mudancas_status_associado: [
      { antes: "inadimplente", depois: "ativo", count: 1 },
    ],
    mudancas_status_ciclo: [
      { antes: "aberto", depois: "apto_a_renovar", count: 1 },
    ],
  },
  items: [
    {
      linha_numero: 1,
      cpf_cnpj: "23993596315",
      nome_servidor: "MARIA DE JESUS SANTANA COSTA",
      matricula_servidor: "030759-9",
      orgao_pagto_nome: "SEC. EST. ADMIN. E PREVIDEN.",
      valor_descontado: "30.00",
      status_codigo: "1",
      resultado: "baixa_efetuada",
      associado_id: 77,
      associado_nome: "Maria de Jesus Santana Costa",
      associado_status_antes: "inadimplente",
      associado_status_depois: "ativo",
      ciclo_status_antes: "aberto",
      ciclo_status_depois: "apto_a_renovar",
      ficara_apto_renovar: true,
      desconto_em_associado_inativo: false,
      categoria: "valores_30_50",
    },
  ],
};

const dryRunResultadoComInativo = {
  kpis: {
    ...dryRunResultado.kpis,
    aptos_a_renovar: 0,
    associados_inativos_com_desconto: 1,
    mudancas_status_associado: [],
    mudancas_status_ciclo: [],
  },
  items: [
    {
      ...dryRunResultado.items[0],
      cpf_cnpj: "70486310310",
      nome_servidor: "RAQUEL PEREIRA DE OLIVEIRA",
      associado_nome: "Raquel Pereira de Oliveira",
      associado_status_antes: "inativo",
      associado_status_depois: "inativo",
      ciclo_status_antes: "fechado",
      ciclo_status_depois: "fechado",
      ficara_apto_renovar: false,
      desconto_em_associado_inativo: true,
      categoria: "mensalidades",
    },
  ],
};

const historyPayload = {
  count: 1,
  next: null,
  previous: null,
  results: [latestImport],
};

const itemPayload = {
  count: 1,
  next: null,
  previous: null,
  results: [
    {
      id: 1,
      linha_numero: 1,
      cpf_cnpj: "23993596315",
      matricula_servidor: "030759-9",
      nome_servidor: "MARIA DE JESUS SANTANA COSTA",
      cargo: "-",
      competencia: "05/2025",
      valor_descontado: "30.00",
      status_codigo: "1",
      status_desconto: "efetivado",
      status_descricao: "Lançado e Efetivado",
      motivo_rejeicao: null,
      orgao_codigo: "002",
      orgao_pagto_codigo: "002",
      orgao_pagto_nome: "SEC. EST. ADMIN. E PREVIDEN.",
      resultado_processamento: "baixa_efetuada",
      observacao: "Parcela baixada automaticamente.",
      gerou_encerramento: true,
      gerou_novo_ciclo: true,
      associado_nome: "Maria de Jesus Santana Costa",
      contrato_codigo: "CTR-001",
    },
  ],
};

const expandedItemPayload = {
  count: 2,
  next: null,
  previous: null,
  results: [
    itemPayload.results[0],
    {
      id: 2,
      linha_numero: 2,
      cpf_cnpj: "11122233344",
      matricula_servidor: "123456-7",
      nome_servidor: "JOSE DO NASCIMENTO",
      cargo: "-",
      competencia: "05/2025",
      valor_descontado: "50.00",
      status_codigo: "2",
      status_desconto: "rejeitado",
      status_descricao: "Não descontado",
      motivo_rejeicao: null,
      orgao_codigo: "003",
      orgao_pagto_codigo: "003",
      orgao_pagto_nome: "SEC. EST. FAZENDA",
      resultado_processamento: "nao_descontado",
      observacao: "Linha rejeitada no retorno.",
      gerou_encerramento: false,
      gerou_novo_ciclo: false,
      associado_id: 78,
      associado_nome: "Jose do Nascimento",
      agente_responsavel: "Agente Padrão",
      contrato_codigo: "CTR-002",
    },
  ],
};

describe("ImportacaoPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();

    useV1ImportacaoArquivoRetornoUltimaRetrieve.mockReturnValue({
      data: latestImport,
    });
    useV1ImportacaoArquivoRetornoFinanceiroRetrieve.mockReturnValue({
      data: {
        resumo: latestImport.financeiro,
        rows: [
          {
            id: 9,
            associado_nome: "Maria de Jesus Santana Costa",
            matricula: "030759-9",
            cpf_cnpj: "23993596315",
            categoria: "mensalidades",
            esperado: "30.00",
            recebido: "30.00",
            ok: true,
            situacao_code: "ok",
            situacao_label: "Quitado",
          },
          {
            id: 10,
            associado_nome: "José do Nascimento",
            matricula: "123456-7",
            cpf_cnpj: "11122233344",
            categoria: "valores_30_50",
            esperado: "30.00",
            recebido: "30.00",
            ok: true,
            situacao_code: "ok",
            situacao_label: "Quitado",
          },
        ],
      },
      isLoading: false,
    });
    useV1ImportacaoArquivoRetornoDescontadosList.mockReturnValue({
      data: itemPayload,
    });
    useV1ImportacaoArquivoRetornoNaoDescontadosList.mockReturnValue({
      data: itemPayload,
    });
    useV1ImportacaoArquivoRetornoPendenciasManuaisList.mockReturnValue({
      data: itemPayload,
    });
    useV1ImportacaoArquivoRetornoEncerramentosList.mockReturnValue({
      data: itemPayload,
    });
    useV1ImportacaoArquivoRetornoNovosCiclosList.mockReturnValue({
      data: itemPayload,
    });
    mockedApiFetch.mockImplementation(async (path, options) => {
      if (path === "importacao/arquivo-retorno") {
        return historyPayload;
      }

      if (path === `importacao/arquivo-retorno/${latestImport.id}/descontados`) {
        return expandedItemPayload;
      }

      if (
        path === `importacao/arquivo-retorno/${latestImport.id}/nao-descontados`
      ) {
        return expandedItemPayload;
      }

      if (path === "importacao/arquivo-retorno/upload") {
        const arquivo = options?.formData?.get("arquivo") as File | null;
        return {
          ...latestImport,
          status: "processando",
          arquivo_nome: arquivo?.name ?? latestImport.arquivo_nome,
        };
      }

      if (
        path === `importacao/arquivo-retorno/${latestImport.id}/reprocessar`
      ) {
        return {
          ...latestImport,
          status: "processando",
        };
      }

      if (path === `importacao/arquivo-retorno/${latestImport.id}/confirmar`) {
        return {
          ...latestImport,
          status: "pendente",
        };
      }

      if (path === `importacao/arquivo-retorno/${latestImport.id}/cancelar`) {
        return undefined;
      }

      throw new Error(`Unexpected apiFetch path: ${path}`);
    });
  });

  it("renderiza cards e histórico da última importação", () => {
    renderPage();

    expect(screen.getByText("Histórico de importações")).toBeInTheDocument();
    expect(screen.getByText("retorno_etipi_052025.txt")).toBeInTheDocument();
    expect(
      screen.getByText("Competência detectada: 05/2025"),
    ).toBeInTheDocument();
    expect(screen.getByText("Quitados")).toBeInTheDocument();
    expect(screen.getByText("Mensalidades Recebidas")).toBeInTheDocument();
    expect(screen.getByText("Valores 30/50 Recebidos")).toBeInTheDocument();
  });

  it("abre a listagem financeira ao clicar em um card numérico da importação", async () => {
    const user = userEvent.setup();

    renderPage();
    await user.click(
      await screen.findByRole("button", { name: /Valores 30\/50 Recebidos/i }),
    );

    const dialog = await screen.findByRole("dialog");
    expect(
      within(dialog).getByText("Valores 30/50 da última importação"),
    ).toBeInTheDocument();
    expect(within(dialog).getByText("José do Nascimento")).toBeInTheDocument();
  });

  it("abre a tabela expandida ao clicar no card de quitados", async () => {
    const user = userEvent.setup();

    renderPage();
    await user.click(await screen.findByRole("button", { name: /Quitados/i }));

    const dialog = await screen.findByRole("dialog");
    expect(
      within(dialog).getByText("Baixas automáticas da última importação"),
    ).toBeInTheDocument();
    expect(
      within(dialog).getByText("MARIA DE JESUS SANTANA COSTA"),
    ).toBeInTheDocument();
    expect(within(dialog).getByText("JOSE DO NASCIMENTO")).toBeInTheDocument();
  });

  it("abre a tabela expandida ao clicar no card de faltando", async () => {
    const user = userEvent.setup();

    renderPage();
    await user.click(await screen.findByRole("button", { name: /Faltando/i }));

    const dialog = await screen.findByRole("dialog");
    expect(
      within(dialog).getByText("Não descontados da última importação"),
    ).toBeInTheDocument();
    expect(
      within(dialog).getByText(
        "Itens rejeitados pelo ETIPI com marcação de não descontado no último arquivo retorno.",
      ),
    ).toBeInTheDocument();
    expect(within(dialog).getByText("JOSE DO NASCIMENTO")).toBeInTheDocument();
  });

  it("entra em polling visual após upload", async () => {
    const user = userEvent.setup();
    const { container } = renderPage();
    const input = container.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    const file = new File(["conteudo"], "retorno_etipi_052025.txt", {
      type: "text/plain",
    });

    await user.upload(input, file);

    expect(
      await screen.findByText("Processando arquivo retorno..."),
    ).toBeInTheDocument();
  });

  it("mostra progresso visual durante o upload do arquivo", async () => {
    const user = userEvent.setup();
    let resolveUpload: ((value: typeof latestImport) => void) | undefined;

    useV1ImportacaoArquivoRetornoUltimaRetrieve.mockReturnValue({
      data: { ...latestImport, status: "concluido" },
    });
    useV1ImportacaoArquivoRetornoList.mockReturnValue({
      data: {
        ...historyPayload,
        results: [{ ...latestImport, status: "concluido" }],
      },
    });

    mockedApiFetch.mockImplementation((path, options) => {
      if (path === "importacao/arquivo-retorno") {
        return Promise.resolve(historyPayload);
      }

      if (path === "importacao/arquivo-retorno/upload") {
        options?.onUploadProgress?.({ loaded: 10, total: 20, percent: 50 });
        return new Promise((resolve) => {
          resolveUpload = resolve as (value: typeof latestImport) => void;
        });
      }

      if (
        path === `importacao/arquivo-retorno/${latestImport.id}/reprocessar`
      ) {
        return Promise.resolve({
          ...latestImport,
          status: "processando",
        });
      }

      throw new Error(`Unexpected apiFetch path: ${path}`);
    });

    const { container } = renderPage();
    const input = container.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    const file = new File(["conteudo"], "retorno_etipi_052025.txt", {
      type: "text/plain",
    });

    await user.upload(input, file);

    expect(await screen.findByText("50%")).toBeInTheDocument();
    expect(
      screen.getByText(/Enviando retorno_etipi_052025.txt/i),
    ).toBeInTheDocument();

    await act(async () => {
      resolveUpload?.({
        ...latestImport,
        status: "processando",
      });
    });
  });

  it("abre o modal de dry-run quando o upload volta aguardando confirmação", async () => {
    const user = userEvent.setup();

    mockedApiFetch.mockImplementation(async (path, options) => {
      if (path === "importacao/arquivo-retorno") {
        return historyPayload;
      }

      if (path === "importacao/arquivo-retorno/upload") {
        const arquivo = options?.formData?.get("arquivo") as File | null;
        return {
          ...latestImport,
          status: "aguardando_confirmacao",
          arquivo_nome: arquivo?.name ?? latestImport.arquivo_nome,
          dry_run_resultado: dryRunResultado,
        };
      }
      if (path === `importacao/arquivo-retorno/${latestImport.id}/confirmar`) {
        return {
          ...latestImport,
          status: "pendente",
        };
      }
      if (path === `importacao/arquivo-retorno/${latestImport.id}/cancelar`) {
        return undefined;
      }
      throw new Error(`Unexpected apiFetch path: ${path}`);
    });

    const { container } = renderPage();
    const input = container.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    const file = new File(["conteudo"], "retorno_dry_run.txt", {
      type: "text/plain",
    });

    await user.upload(input, file);

    expect(await screen.findByText("Prévia da importação")).toBeInTheDocument();
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("Total no arquivo")).toBeInTheDocument();
    expect(
      within(dialog).getByText("Parcelas R$30 / R$50"),
    ).toBeInTheDocument();
    expect(
      within(dialog).getByText("Associados importados"),
    ).toBeInTheDocument();
    expect(
      within(dialog).getByText("Ficarão aptos a renovar"),
    ).toBeInTheDocument();
  });

  it("abre a tabela de associados que ficarao aptos a renovar na previa", async () => {
    const user = userEvent.setup();

    mockedApiFetch.mockImplementation(async (path, options) => {
      if (path === "importacao/arquivo-retorno") {
        return historyPayload;
      }

      if (path === "importacao/arquivo-retorno/upload") {
        const arquivo = options?.formData?.get("arquivo") as File | null;
        return {
          ...latestImport,
          status: "aguardando_confirmacao",
          arquivo_nome: arquivo?.name ?? latestImport.arquivo_nome,
          dry_run_resultado: dryRunResultado,
        };
      }
      if (path === `importacao/arquivo-retorno/${latestImport.id}/cancelar`) {
        return undefined;
      }
      throw new Error(`Unexpected apiFetch path: ${path}`);
    });

    const { container } = renderPage();
    const input = container.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    const file = new File(["conteudo"], "retorno_dry_run.txt", {
      type: "text/plain",
    });

    await user.upload(input, file);
    await user.click(
      await screen.findByRole("button", { name: /Ficarão aptos a renovar/i }),
    );

    const dialogs = await screen.findAllByRole("dialog");
    const detailDialog = dialogs[dialogs.length - 1];
    expect(
      within(detailDialog).getByText("Ficarão aptos a renovar"),
    ).toBeInTheDocument();
    expect(
      within(detailDialog).getByPlaceholderText(
        "Buscar por associado, CPF, matrícula ou órgão...",
      ),
    ).toBeInTheDocument();
    expect(
      within(detailDialog).getByText(
        "Entrará em Aptos a renovar após confirmar",
      ),
    ).toBeInTheDocument();
  });

  it("sinaliza associados inativos com desconto efetuado na previa", async () => {
    const user = userEvent.setup();

    mockedApiFetch.mockImplementation(async (path, options) => {
      if (path === "importacao/arquivo-retorno") {
        return historyPayload;
      }

      if (path === "importacao/arquivo-retorno/upload") {
        const arquivo = options?.formData?.get("arquivo") as File | null;
        return {
          ...latestImport,
          status: "aguardando_confirmacao",
          arquivo_nome: arquivo?.name ?? latestImport.arquivo_nome,
          dry_run_resultado: dryRunResultadoComInativo,
        };
      }
      if (path === `importacao/arquivo-retorno/${latestImport.id}/cancelar`) {
        return undefined;
      }
      throw new Error(`Unexpected apiFetch path: ${path}`);
    });

    const { container } = renderPage();
    const input = container.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    const file = new File(["conteudo"], "retorno_dry_run.txt", {
      type: "text/plain",
    });

    await user.upload(input, file);
    await user.click(
      await screen.findByRole("button", { name: /Inativos com desconto efetuado/i }),
    );

    const dialogs = await screen.findAllByRole("dialog");
    const detailDialog = dialogs[dialogs.length - 1];
    expect(
      within(detailDialog).getByText("Associados inativos com desconto efetuado"),
    ).toBeInTheDocument();
    expect(
      within(detailDialog).getByText("Raquel Pereira de Oliveira"),
    ).toBeInTheDocument();
    expect(
      within(detailDialog).getByText("Retorno descontou associado inativo"),
    ).toBeInTheDocument();
  });

  it("confirma a importação a partir do modal de dry-run", async () => {
    const user = userEvent.setup();

    mockedApiFetch.mockImplementation(async (path, options) => {
      if (path === "importacao/arquivo-retorno") {
        return historyPayload;
      }

      if (path === "importacao/arquivo-retorno/upload") {
        return {
          ...latestImport,
          status: "aguardando_confirmacao",
          dry_run_resultado: dryRunResultado,
        };
      }
      if (path === `importacao/arquivo-retorno/${latestImport.id}/confirmar`) {
        return {
          ...latestImport,
          status: "pendente",
        };
      }
      if (path === `importacao/arquivo-retorno/${latestImport.id}/cancelar`) {
        return undefined;
      }
      throw new Error(`Unexpected apiFetch path: ${path}`);
    });

    const { container } = renderPage();
    const input = container.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    const file = new File(["conteudo"], "retorno_dry_run.txt", {
      type: "text/plain",
    });

    await user.upload(input, file);
    await user.click(
      await screen.findByRole("button", { name: /confirmar importação/i }),
    );

    expect(mockedApiFetch).toHaveBeenCalledWith(
      `importacao/arquivo-retorno/${latestImport.id}/confirmar`,
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("cancela a importação a partir do modal de dry-run", async () => {
    const user = userEvent.setup();

    mockedApiFetch.mockImplementation(async (path, options) => {
      if (path === "importacao/arquivo-retorno") {
        return historyPayload;
      }

      if (path === "importacao/arquivo-retorno/upload") {
        return {
          ...latestImport,
          status: "aguardando_confirmacao",
          dry_run_resultado: dryRunResultado,
        };
      }
      if (path === `importacao/arquivo-retorno/${latestImport.id}/confirmar`) {
        return {
          ...latestImport,
          status: "pendente",
        };
      }
      if (path === `importacao/arquivo-retorno/${latestImport.id}/cancelar`) {
        return undefined;
      }
      throw new Error(`Unexpected apiFetch path: ${path}`);
    });

    const { container } = renderPage();
    const input = container.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    const file = new File(["conteudo"], "retorno_dry_run.txt", {
      type: "text/plain",
    });

    await user.upload(input, file);
    await user.click(
      await screen.findByRole("button", { name: /^cancelar$/i }),
    );

    expect(mockedApiFetch).toHaveBeenCalledWith(
      `importacao/arquivo-retorno/${latestImport.id}/cancelar`,
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("aciona cancelamento ao clicar no botao de fechar do modal", async () => {
    const user = userEvent.setup();

    mockedApiFetch.mockImplementation(async (path) => {
      if (path === "importacao/arquivo-retorno") {
        return historyPayload;
      }

      if (path === "importacao/arquivo-retorno/upload") {
        return {
          ...latestImport,
          status: "aguardando_confirmacao",
          dry_run_resultado: dryRunResultado,
        };
      }
      if (path === `importacao/arquivo-retorno/${latestImport.id}/cancelar`) {
        return undefined;
      }
      throw new Error(`Unexpected apiFetch path: ${path}`);
    });

    const { container } = renderPage();
    const input = container.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    const file = new File(["conteudo"], "retorno_dry_run.txt", {
      type: "text/plain",
    });

    await user.upload(input, file);
    await user.click(await screen.findByRole("button", { name: /^close$/i }));

    expect(mockedApiFetch).toHaveBeenCalledWith(
      `importacao/arquivo-retorno/${latestImport.id}/cancelar`,
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("evita chamadas duplicadas ao cancelar e fechar a previa em sequencia", async () => {
    const user = userEvent.setup();
    let resolveCancel: (() => void) | undefined;

    mockedApiFetch.mockImplementation(async (path) => {
      if (path === "importacao/arquivo-retorno") {
        return historyPayload;
      }

      if (path === "importacao/arquivo-retorno/upload") {
        return {
          ...latestImport,
          status: "aguardando_confirmacao",
          dry_run_resultado: dryRunResultado,
        };
      }
      if (path === `importacao/arquivo-retorno/${latestImport.id}/cancelar`) {
        return new Promise<void>((resolve) => {
          resolveCancel = resolve;
        });
      }
      throw new Error(`Unexpected apiFetch path: ${path}`);
    });

    const { container } = renderPage();
    const input = container.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    const file = new File(["conteudo"], "retorno_dry_run.txt", {
      type: "text/plain",
    });

    await user.upload(input, file);
    await user.click(
      await screen.findByRole("button", { name: /^cancelar$/i }),
    );
    await user.click(await screen.findByRole("button", { name: /^close$/i }));

    expect(
      mockedApiFetch.mock.calls.filter(
        ([path]) =>
          path === `importacao/arquivo-retorno/${latestImport.id}/cancelar`,
      ),
    ).toHaveLength(1);

    await act(async () => {
      resolveCancel?.();
    });
  });

  it("mantem o modal aberto quando cancelar falha e permite nova tentativa", async () => {
    const user = userEvent.setup();
    let cancelCalls = 0;

    mockedApiFetch.mockImplementation(async (path) => {
      if (path === "importacao/arquivo-retorno") {
        return historyPayload;
      }

      if (path === "importacao/arquivo-retorno/upload") {
        return {
          ...latestImport,
          status: "aguardando_confirmacao",
          dry_run_resultado: dryRunResultado,
        };
      }
      if (path === `importacao/arquivo-retorno/${latestImport.id}/cancelar`) {
        cancelCalls += 1;
        if (cancelCalls === 1) {
          throw new Error("Falha ao cancelar");
        }
        return undefined;
      }
      throw new Error(`Unexpected apiFetch path: ${path}`);
    });

    const { container } = renderPage();
    const input = container.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    const file = new File(["conteudo"], "retorno_dry_run.txt", {
      type: "text/plain",
    });

    await user.upload(input, file);
    await user.click(
      await screen.findByRole("button", { name: /^cancelar$/i }),
    );

    expect(await screen.findByText("Prévia da importação")).toBeInTheDocument();
    expect(cancelCalls).toBe(1);

    await user.click(await screen.findByRole("button", { name: /^close$/i }));

    expect(cancelCalls).toBe(2);
  });
});
