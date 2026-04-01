import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import TesourariaPage from "./page";
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

jest.mock("@/components/custom/searchable-select", () => ({
  __esModule: true,
  default: ({
    options,
    value,
    onChange,
    placeholder = "Selecione",
  }: {
    options: Array<{ value: string; label: string }>;
    value?: string;
    onChange?: (value: string) => void;
    placeholder?: string;
  }) => (
    <select
      aria-label={placeholder}
      value={value ?? ""}
      onChange={(event) => onChange?.(event.target.value)}
    >
      <option value="">{placeholder}</option>
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  ),
}));

jest.mock("@/components/shared/export-button", () => ({
  __esModule: true,
  default: ({
    onExport,
    label = "Exportar",
  }: {
    onExport: (format: "csv" | "pdf" | "excel" | "xlsx") => void;
    label?: string;
  }) => <button onClick={() => onExport("xlsx")}>{label}</button>,
}));

const mockedApiFetch = jest.mocked(apiFetch);
const windowOpenSpy = jest.spyOn(window, "open").mockImplementation(() => null);

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
  windowOpenSpy.mockClear();
  mockedApiFetch.mockImplementation(async (path) => {
    if (path === "tesouraria/contratos/agentes") {
      return [];
    }
    if (path === "tesouraria/contratos") {
      return {
        count: 0,
        next: null,
        previous: null,
        results: [],
      };
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
      <TesourariaPage />
    </QueryClientProvider>,
  );
}

function buildContrato(overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: overrides.id ?? 1,
    associado_id: overrides.associado_id ?? 11,
    nome: overrides.nome ?? "Associado Exemplo",
    cpf_cnpj: overrides.cpf_cnpj ?? "12345678901",
    matricula: overrides.matricula ?? "MAT-1",
    chave_pix: overrides.chave_pix ?? "pix@example.com",
    codigo: overrides.codigo ?? "CTR-1",
    data_assinatura: overrides.data_assinatura ?? "2026-04-01T12:00:00Z",
    data_solicitacao: overrides.data_solicitacao ?? "2026-04-01T12:00:00Z",
    status: overrides.status ?? "concluido",
    agente: overrides.agente ?? null,
    agente_nome: overrides.agente_nome ?? "Agente Padrão",
    percentual_repasse: overrides.percentual_repasse ?? "10.00",
    comissao_agente: overrides.comissao_agente ?? "50.00",
    margem_disponivel: overrides.margem_disponivel ?? "500.00",
    comprovantes:
      overrides.comprovantes ??
      [
        {
          id: "comp-associado",
          papel: "associado",
          tipo: "comprovante_pagamento_associado",
          arquivo: "/media/tesouraria/associado.pdf",
          arquivo_referencia: "tesouraria/associado.pdf",
          arquivo_disponivel_localmente: true,
          tipo_referencia: "local",
          nome_original: "associado.pdf",
          created_at: "2026-04-01T12:00:00Z",
        },
        {
          id: "comp-agente",
          papel: "agente",
          tipo: "comprovante_pagamento_agente",
          arquivo: "/media/tesouraria/agente.pdf",
          arquivo_referencia: "tesouraria/agente.pdf",
          arquivo_disponivel_localmente: true,
          tipo_referencia: "local",
          nome_original: "agente.pdf",
          created_at: "2026-04-01T12:00:00Z",
        },
      ],
    dados_bancarios: overrides.dados_bancarios ?? null,
    observacao_tesouraria: overrides.observacao_tesouraria ?? "",
    etapa_atual: overrides.etapa_atual ?? "concluido",
    situacao_esteira: overrides.situacao_esteira ?? "aprovado",
    cancelamento_tipo: overrides.cancelamento_tipo,
    cancelamento_motivo: overrides.cancelamento_motivo,
    cancelado_em: overrides.cancelado_em ?? null,
  };
}

it("usa date picker no filtro avancado e consulta sem competencia externa", async () => {
  const user = userEvent.setup();
  renderPage();

  await waitFor(() =>
    expect(
      mockedApiFetch.mock.calls.filter(([path]) => path === "tesouraria/contratos"),
    ).toHaveLength(4),
  );
  expect(mockedApiFetch.mock.calls[0]?.[1]).toEqual(
    expect.objectContaining({
      query: expect.objectContaining({
        data_inicio: undefined,
        data_fim: undefined,
      }),
    }),
  );
  expect(mockedApiFetch.mock.calls[0]?.[1]?.query).not.toHaveProperty("competencia");
  expect(screen.queryByLabelText("competencia")).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: /filtros avançados/i }));

  const dateInputs = screen.getAllByPlaceholderText("dd/mm/aaaa");
  expect(dateInputs).toHaveLength(2);
  expect(screen.queryByDisplayValue("2026-04-01")).not.toBeInTheDocument();

  fireEvent.change(dateInputs[0], { target: { value: "2026-04-01" } });
  fireEvent.change(dateInputs[1], { target: { value: "2026-04-30" } });

  await user.click(screen.getByRole("button", { name: /^Aplicar$/i }));

  await waitFor(() =>
    expect(
      mockedApiFetch.mock.calls.some(
        ([path, options]) =>
          path === "tesouraria/contratos" &&
          options?.query?.data_inicio === "2026-04-01" &&
          options?.query?.data_fim === "2026-04-30",
      ),
    ).toBe(true),
  );
});

it("permite visualizar comprovante existente e manter acao de substituir em contratos efetivados", async () => {
  const user = userEvent.setup();

  mockedApiFetch.mockImplementation(async (path, options) => {
    if (path === "tesouraria/contratos/agentes") {
      return [];
    }
    if (path !== "tesouraria/contratos") {
      throw new Error(`Unexpected path: ${String(path)}`);
    }

    if (options?.query?.pagamento === "concluido") {
      return {
        count: 1,
        next: null,
        previous: null,
        results: [buildContrato()],
      };
    }

    return {
      count: 0,
      next: null,
      previous: null,
      results: [],
    };
  });

  renderPage();

  const viewAssociadoButton = await screen.findByRole("button", { name: /ver associado/i });
  expect(screen.getByRole("button", { name: /substituir/i })).toBeInTheDocument();

  await user.click(viewAssociadoButton);

  expect(windowOpenSpy).toHaveBeenCalledWith(
    expect.stringContaining("/media/tesouraria/associado.pdf"),
    "_blank",
    "noopener,noreferrer",
  );
});

it("remove o limpar externo e atualiza os kpis conforme o periodo filtrado", async () => {
  const user = userEvent.setup();

  mockedApiFetch.mockImplementation(async (path, options) => {
    if (path === "tesouraria/contratos/agentes") {
      return [];
    }
    if (path !== "tesouraria/contratos") {
      throw new Error(`Unexpected path: ${String(path)}`);
    }

    const isFilteredDay =
      options?.query?.data_inicio === "2026-03-01" && options?.query?.data_fim === "2026-03-01";
    const counts = isFilteredDay
      ? {
          pendente: 1,
          concluido: 2,
          liquidado: 0,
          cancelado: 1,
        }
      : {
          pendente: 3,
          concluido: 4,
          liquidado: 1,
          cancelado: 2,
        };

    return {
      count: counts[options?.query?.pagamento as keyof typeof counts] ?? 0,
      next: null,
      previous: null,
      results: [],
    };
  });

  renderPage();

  await waitFor(() => expect(screen.getByLabelText("Pendentes: 3")).toBeInTheDocument());
  expect(screen.getByLabelText("Total no filtro: 10")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /^Limpar$/i })).not.toBeInTheDocument();
  expect(screen.getAllByRole("button", { name: "Exportar" })).toHaveLength(1);

  await user.click(screen.getByRole("button", { name: /filtros avançados/i }));

  const dateInputs = screen.getAllByPlaceholderText("dd/mm/aaaa");
  fireEvent.change(dateInputs[0], { target: { value: "2026-03-01" } });
  fireEvent.change(dateInputs[1], { target: { value: "2026-03-01" } });

  await user.click(screen.getByRole("button", { name: /^Aplicar$/i }));

  await waitFor(() => expect(screen.getByLabelText("Pendentes: 1")).toBeInTheDocument());
  expect(screen.getByLabelText("Efetivados: 2")).toBeInTheDocument();
  expect(screen.getByLabelText("Total no filtro: 4")).toBeInTheDocument();

  await user.click(screen.getByLabelText("Efetivados: 2"));

  expect(screen.getByText("Contratos efetivados")).toBeInTheDocument();
  expect(screen.queryByText("Aguardando efetivação PIX")).not.toBeInTheDocument();
});

it("carrega usuarios no filtro de agente e expõe ordem crescente, decrescente e congelados", async () => {
  const user = userEvent.setup();

  mockedApiFetch.mockImplementation(async (path, options) => {
    if (path === "tesouraria/contratos/agentes") {
      return [
        {
          id: 10,
          full_name: "Agente Padrão",
          email: "agente@abase.local",
          primary_role: "AGENTE",
        },
        {
          id: 20,
          full_name: "Coordenador Cadastro",
          email: "coord@abase.local",
          primary_role: "COORDENADOR",
        },
      ];
    }

    if (path === "tesouraria/contratos") {
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

  await user.click(await screen.findByRole("button", { name: /filtros avançados/i }));

  expect(screen.getByRole("option", { name: /agente padrão · agente · agente@abase.local/i })).toBeInTheDocument();
  expect(
    screen.getByRole("option", {
      name: /coordenador cadastro · coordenador · coord@abase.local/i,
    }),
  ).toBeInTheDocument();
  expect(screen.getByRole("option", { name: /ordem crescente/i })).toBeInTheDocument();
  expect(screen.getByRole("option", { name: /ordem decrescente/i })).toBeInTheDocument();
  expect(screen.getByRole("option", { name: /congelados/i })).toBeInTheDocument();

  await user.selectOptions(screen.getByLabelText("Todos os responsáveis"), "20");
  await user.click(screen.getByRole("button", { name: /^Aplicar$/i }));

  await waitFor(() =>
    expect(
      mockedApiFetch.mock.calls.some(
        ([path, requestOptions]) =>
          path === "tesouraria/contratos" && requestOptions?.query?.agente === "20",
      ),
    ).toBe(true),
  );
});

it("exporta com as mesmas colunas da secao da tesouraria", async () => {
  const user = userEvent.setup();

  mockedApiFetch.mockImplementation(async (path, options) => {
    if (path === "tesouraria/contratos/agentes") {
      return [];
    }
    if (path === "tesouraria/contratos") {
      if (options?.query?.pagamento === "pendente") {
        return {
          count: 1,
          next: null,
          previous: null,
          results: [
            buildContrato({
              status: "pendente",
              nome: "Francisca Teste",
              matricula: "3716961",
              cpf_cnpj: "00096819308",
              agente_nome: "Daniel Freire Bezerra",
              percentual_repasse: "10.00",
              margem_disponivel: "735.00",
              comissao_agente: "35.00",
              chave_pix: "00096819308",
              data_solicitacao: "2026-03-23T18:12:00Z",
              dados_bancarios: {
                banco: "Banco do Brasil",
                agencia: "1234",
                conta: "98765-0",
                tipo_conta: "corrente",
                chave_pix: "00096819308",
              },
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

    if (path === "relatorios/exportar") {
      expect(options?.body).toEqual(
        expect.objectContaining({
          rota: "/tesouraria",
          formato: "xlsx",
          filtros: expect.objectContaining({
            rows: [
              expect.objectContaining({
                anexos: expect.stringContaining("Associado: associado.pdf"),
                dados_bancarios: "Banco do Brasil | Ag 1234 | Conta 98765-0 | corrente",
                chave_pix: "00096819308",
                acao: "Ver detalhes | Congelar | Cancelar contrato",
                nome: "Francisca Teste",
                matricula_cpf: "3716961 | 000.968.193-08",
                agente: "Daniel Freire Bezerra | Repasse: 10.00%",
                auxilio_comissao: "Aux. liberado: R$ 735,00 | Comissão: R$ 35,00",
                data_solicitacao: "23/03/2026 15:12",
                status: "Pendente",
              }),
            ],
          }),
        }),
      );
      return {
        id: 99,
        formato: "xlsx",
        download_url: "/api/v1/relatorios/99/download/",
      };
    }

    throw new Error(`Unexpected path: ${String(path)}`);
  });

  renderPage();

  await waitFor(() =>
    expect(
      mockedApiFetch.mock.calls.filter(([path]) => path === "tesouraria/contratos"),
    ).toHaveLength(4),
  );
  await user.click(screen.getByRole("button", { name: "Exportar" }));

  await waitFor(() =>
    expect(mockedApiFetch).toHaveBeenCalledWith(
      "relatorios/exportar",
      expect.objectContaining({
        method: "POST",
      }),
    ),
  );
});
