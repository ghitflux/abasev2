import { render, screen } from "@testing-library/react";

import RenovacaoCiclosPage from "./page";

const useV1RenovacaoCiclosMesesList = jest.fn();
const useV1RenovacaoCiclosVisaoMensalRetrieve = jest.fn();
const useV1RenovacaoCiclosList = jest.fn();
const useV1RenovacaoCiclosExportarRetrieve = jest.fn();

jest.mock("@/gen", () => ({
  useV1RenovacaoCiclosMesesList: (...args: unknown[]) =>
    useV1RenovacaoCiclosMesesList(...args),
  useV1RenovacaoCiclosVisaoMensalRetrieve: (...args: unknown[]) =>
    useV1RenovacaoCiclosVisaoMensalRetrieve(...args),
  useV1RenovacaoCiclosList: (...args: unknown[]) =>
    useV1RenovacaoCiclosList(...args),
  useV1RenovacaoCiclosExportarRetrieve: (...args: unknown[]) =>
    useV1RenovacaoCiclosExportarRetrieve(...args),
}));

jest.mock("sonner", () => ({
  toast: {
    success: jest.fn(),
    error: jest.fn(),
  },
}));

describe("RenovacaoCiclosPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    useV1RenovacaoCiclosMesesList.mockReturnValue({
      data: [{ id: "2025-05", label: "05/2025" }],
    });
    useV1RenovacaoCiclosVisaoMensalRetrieve.mockReturnValue({
      data: {
        competencia: "05/2025",
        total_associados: 3,
        ciclo_renovado: 0,
        apto_a_renovar: 0,
        em_aberto: 1,
        ciclo_iniciado: 1,
        inadimplente: 1,
      },
    });
    useV1RenovacaoCiclosList.mockReturnValue({
      data: {
        count: 1,
        next: null,
        previous: null,
        results: [
          {
            id: 1,
            competencia: "05/2025",
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
            status_visual: "ciclo_iniciado",
            parcelas_pagas: 3,
            parcelas_total: 3,
            valor_mensalidade: "30.00",
            valor_parcela: "30.00",
            data_pagamento: "2025-05-15",
            orgao_pagto_nome: "SEC. EST. ADMIN. E PREVIDEN.",
            resultado_importacao: "baixa_efetuada",
            status_codigo_etipi: "1",
            gerou_encerramento: true,
            gerou_novo_ciclo: true,
          },
        ],
      },
    });
    useV1RenovacaoCiclosExportarRetrieve.mockReturnValue({
      refetch: jest.fn(),
      isFetching: false,
    });
  });

  it("renderiza cards e detalhamento da competência conciliada", () => {
    render(<RenovacaoCiclosPage />);

    expect(screen.getByText("Renovação de Ciclos")).toBeInTheDocument();
    expect(screen.getByText("Detalhamento mensal")).toBeInTheDocument();
    expect(screen.getByText("Maria de Jesus Santana Costa")).toBeInTheDocument();
    expect(screen.getByText("CTR-001")).toBeInTheDocument();
    expect(screen.getByText("Inadimplentes")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
  });
});
