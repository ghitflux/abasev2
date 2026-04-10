import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import TesourariaPagamentosPage from "./page";
import type { PagamentoAgenteItem } from "@/lib/api/types";
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

jest.mock("@/components/custom/calendar-competencia", () => ({
  __esModule: true,
  default: ({
    value,
    onChange,
  }: {
    value?: Date;
    onChange?: (value: Date) => void;
  }) => (
    <input
      aria-label="competencia"
      value={value ? value.toISOString().slice(0, 7) : ""}
      onChange={(event) => onChange?.(new Date(`${event.target.value}-01T12:00:00`))}
    />
  ),
}));

const mockedApiFetch = jest.mocked(apiFetch);

function buildRow(overrides: Partial<PagamentoAgenteItem> = {}): PagamentoAgenteItem {
  return {
    id: overrides.id ?? 1,
    associado_id: overrides.associado_id ?? 10,
    nome: overrides.nome ?? "Associado Tesouraria",
    cpf_cnpj: overrides.cpf_cnpj ?? "12345678900",
    contrato_codigo: overrides.contrato_codigo ?? "CTR-001",
    agente_nome: overrides.agente_nome ?? "Agente Teste",
    status_contrato: overrides.status_contrato ?? "ativo",
    status_visual_slug: overrides.status_visual_slug ?? "ativo",
    status_visual_label: overrides.status_visual_label ?? "Ativo",
    possui_meses_nao_descontados: overrides.possui_meses_nao_descontados ?? false,
    meses_nao_descontados_count: overrides.meses_nao_descontados_count ?? 0,
    data_contrato: overrides.data_contrato ?? "2026-03-01",
    data_solicitacao: overrides.data_solicitacao ?? "2026-03-10T10:00:00Z",
    auxilio_liberado_em: overrides.auxilio_liberado_em ?? "2026-03-10",
    pagamento_inicial_status: overrides.pagamento_inicial_status ?? "pago",
    pagamento_inicial_status_label: overrides.pagamento_inicial_status_label ?? "Pago",
    pagamento_inicial_valor: overrides.pagamento_inicial_valor ?? "1500.00",
    pagamento_inicial_paid_at: overrides.pagamento_inicial_paid_at ?? "2026-03-10T10:00:00Z",
    valor_mensalidade: overrides.valor_mensalidade ?? "250.00",
    comissao_agente: overrides.comissao_agente ?? "150.00",
    parcelas_total: overrides.parcelas_total ?? 4,
    parcelas_pagas: overrides.parcelas_pagas ?? 2,
    cancelamento_tipo: overrides.cancelamento_tipo,
    cancelamento_motivo: overrides.cancelamento_motivo,
    cancelado_em: overrides.cancelado_em ?? null,
    comprovantes_efetivacao: overrides.comprovantes_efetivacao ?? [],
    pagamento_inicial_evidencias: overrides.pagamento_inicial_evidencias ?? [],
    ciclos: overrides.ciclos ?? [],
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
  mockedApiFetch.mockImplementation(async (path) => {
    if (path === "tesouraria/pagamentos") {
      return {
        count: 1,
        next: null,
        previous: null,
        results: [buildRow()],
        resumo: {
          total: 1,
          efetivados: 1,
          com_anexos: 0,
          parcelas_pagas: 2,
          parcelas_total: 4,
        },
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
      <TesourariaPagamentosPage />
    </QueryClientProvider>,
  );
}

it("mantem apenas a busca fora do sheet e fixa page_size da tesouraria", async () => {
  const user = userEvent.setup();
  renderPage();

  await waitFor(() =>
    expect(mockedApiFetch).toHaveBeenCalledWith(
      "tesouraria/pagamentos",
      expect.objectContaining({
        query: expect.objectContaining({ page_size: 15 }),
      }),
    ),
  );

  expect(
    screen.getByPlaceholderText("Buscar por nome, CPF, matrícula ou código do contrato..."),
  ).toBeInTheDocument();
  expect(screen.queryByPlaceholderText("Filtrar por agente")).not.toBeInTheDocument();
  expect(screen.queryByText("15 / página")).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: /filtros avançados/i }));

  expect(screen.getByPlaceholderText("Nome ou e-mail do agente")).toBeInTheDocument();
  expect(screen.getAllByPlaceholderText("dd/mm/aaaa")).toHaveLength(2);
});
