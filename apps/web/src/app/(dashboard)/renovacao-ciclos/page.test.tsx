import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
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

const cyclePayload = {
  count: 1,
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
      parcelas_pagas: 3,
      parcelas_total: 3,
      valor_mensalidade: "30.00",
      valor_parcela: "30.00",
      data_pagamento: "2026-02-10",
      orgao_pagto_nome: "SEC. EST. ADMIN. E PREVIDEN.",
      resultado_importacao: "baixa_efetuada",
      status_codigo_etipi: "1",
      gerou_encerramento: true,
      gerou_novo_ciclo: true,
    },
  ],
};

const importacaoPayload = {
  count: 1,
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
      uploaded_by_nome: "Tes ABASE",
      created_at: "2026-03-12T08:00:00Z",
      processado_em: "2026-03-12T08:10:00Z",
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
      associado_nome: "Maria de Jesus Santana Costa",
      contrato_codigo: "CTR-001",
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
    useV1ImportacaoArquivoRetornoList.mockReturnValue({ data: importacaoPayload });
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
      if (path === "associados/1") {
        return {
          id: 1,
          matricula: "MAT-10049",
          matricula_orgao: "MAT-10049",
          nome_completo: "Maria de Jesus Santana Costa",
          cpf_cnpj: "23993596315",
          status: "ativo",
          agente: {
            id: 7,
            full_name: "Carlos Mendes",
          },
          contratos: [],
          documentos: [],
        };
      }

      if (path === "associados" && options?.query?.search === "23993596315") {
        return {
          count: 1,
          next: null,
          previous: null,
          results: [
            {
              id: 1,
              nome_completo: "Maria de Jesus Santana Costa",
              matricula: "MAT-10049",
              cpf_cnpj: "23993596315",
              status: "ativo",
              agente: {
                id: 7,
                full_name: "Carlos Mendes",
              },
              ciclos_abertos: 0,
              ciclos_fechados: 3,
            },
          ],
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
    expect(screen.getByText("497")).toBeInTheDocument();
    expect(screen.getByText("71")).toBeInTheDocument();
    expect(screen.getByText("16")).toBeInTheDocument();
    expect(screen.getByText("55")).toBeInTheDocument();
  });

  it("faz parse local de YYYY-MM-DD sem deslocar fevereiro para janeiro", () => {
    const date = parseCompetenciaDate("2026-02-01");

    expect(date).toBeDefined();
    expect(date?.getFullYear()).toBe(2026);
    expect(date?.getMonth()).toBe(1);
    expect(date?.getDate()).toBe(1);
  });

  it("usa filtro server-side para arquivos retorno por competencia e periodo", async () => {
    renderPage();

    await waitFor(() =>
      expect(useV1ImportacaoArquivoRetornoList).toHaveBeenCalledWith(
        expect.objectContaining({
          competencia: "2026-02",
          periodo: "mes",
        }),
        expect.anything(),
      ),
    );
  });

  it("expande o detalhamento do arquivo retorno com a tabela do associado", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: /Detalhamento do arquivo/i }));

    expect((await screen.findAllByText("Agente responsável")).length).toBeGreaterThan(0);
    expect(screen.getByText("Esperado")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Ver detalhes do associado/i })).toBeInTheDocument();
  });
});
