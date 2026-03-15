import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import ImportacaoPage from "./page";
import { apiFetch } from "@/lib/api/client";

const useV1ImportacaoArquivoRetornoList = jest.fn();
const useV1ImportacaoArquivoRetornoUltimaRetrieve = jest.fn();
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
  nao_encontrados: 1,
  erros: 0,
  status: "processando",
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

describe("ImportacaoPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();

    useV1ImportacaoArquivoRetornoList.mockReturnValue({ data: historyPayload });
    useV1ImportacaoArquivoRetornoUltimaRetrieve.mockReturnValue({ data: latestImport });
    useV1ImportacaoArquivoRetornoDescontadosList.mockReturnValue({ data: itemPayload });
    useV1ImportacaoArquivoRetornoNaoDescontadosList.mockReturnValue({ data: itemPayload });
    useV1ImportacaoArquivoRetornoPendenciasManuaisList.mockReturnValue({ data: itemPayload });
    useV1ImportacaoArquivoRetornoEncerramentosList.mockReturnValue({ data: itemPayload });
    useV1ImportacaoArquivoRetornoNovosCiclosList.mockReturnValue({ data: itemPayload });
    mockedApiFetch.mockImplementation(async (path, options) => {
      if (path === "importacao/arquivo-retorno/upload") {
        const arquivo = options?.formData?.get("arquivo") as File | null;
        return {
          ...latestImport,
          status: "processando",
          arquivo_nome: arquivo?.name ?? latestImport.arquivo_nome,
        };
      }

      if (path === `importacao/arquivo-retorno/${latestImport.id}/reprocessar`) {
        return {
          ...latestImport,
          status: "processando",
        };
      }

      throw new Error(`Unexpected apiFetch path: ${path}`);
    });
  });

  it("renderiza cards e histórico da última importação", () => {
    renderPage();

    expect(screen.getByText("Histórico de importações")).toBeInTheDocument();
    expect(screen.getByText("retorno_etipi_052025.txt")).toBeInTheDocument();
    expect(screen.getByText("Competência detectada: 05/2025")).toBeInTheDocument();
    expect(screen.getByText("Quitados")).toBeInTheDocument();
    expect(screen.getByText("Mensalidades Recebidas")).toBeInTheDocument();
    expect(screen.getByText("Valores 30/50 Recebidos")).toBeInTheDocument();
  });

  it("entra em polling visual após upload", async () => {
    const user = userEvent.setup();
    const { container } = renderPage();
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["conteudo"], "retorno_etipi_052025.txt", {
      type: "text/plain",
    });

    await user.upload(input, file);

    expect(await screen.findByText("Processando arquivo retorno...")).toBeInTheDocument();
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
      if (path === "importacao/arquivo-retorno/upload") {
        options?.onUploadProgress?.({ loaded: 10, total: 20, percent: 50 });
        return new Promise((resolve) => {
          resolveUpload = resolve as (value: typeof latestImport) => void;
        });
      }

      if (path === `importacao/arquivo-retorno/${latestImport.id}/reprocessar`) {
        return Promise.resolve({
          ...latestImport,
          status: "processando",
        });
      }

      throw new Error(`Unexpected apiFetch path: ${path}`);
    });

    const { container } = renderPage();
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["conteudo"], "retorno_etipi_052025.txt", {
      type: "text/plain",
    });

    await user.upload(input, file);

    expect(await screen.findByText("50%")).toBeInTheDocument();
    expect(screen.getByText(/Enviando retorno_etipi_052025.txt/i)).toBeInTheDocument();

    await act(async () => {
      resolveUpload?.({
        ...latestImport,
        status: "processando",
      });
    });
  });
});
