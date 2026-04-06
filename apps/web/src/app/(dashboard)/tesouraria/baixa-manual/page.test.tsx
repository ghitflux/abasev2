import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import BaixaManualPage from "./page";
import { apiFetch } from "@/lib/api/client";

const push = jest.fn();

jest.mock("@/lib/api/client", () => ({
  apiFetch: jest.fn(),
}));

jest.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
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
    onChange?: (date?: Date) => void;
  }) => (
    <input
      aria-label="competencia"
      value={value ? value.toISOString().slice(0, 7) : ""}
      onChange={(event) =>
        onChange?.(event.target.value ? new Date(`${event.target.value}-01T12:00:00`) : undefined)
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

jest.mock("@/components/custom/file-upload-dropzone", () => ({
  __esModule: true,
  default: () => <div>dropzone</div>,
}));

jest.mock("@/components/shared/data-table", () => ({
  __esModule: true,
  default: ({
    data,
    emptyMessage,
  }: {
    data: Array<{ id: number; nome: string }>;
    emptyMessage: string;
  }) => (
    <div>
      {data.length ? data.map((row) => <div key={row.id}>{row.nome}</div>) : <div>{emptyMessage}</div>}
    </div>
  ),
}));

const mockedApiFetch = jest.mocked(apiFetch);

function buildResponse(listing: "pendentes" | "quitados") {
  if (listing === "quitados") {
    return {
      count: 1,
      results: [
        {
          id: 99,
          parcela_id: 12,
          associado_id: 1,
          nome: "Marcianita Michele Ramos Mendes",
          cpf_cnpj: "05201186343",
          matricula: "MAT-001",
          agente_nome: "Agente Alpha",
          contrato_id: 10,
          contrato_codigo: "CTR-001",
          referencia_mes: "2026-03-01",
          valor: "300.00",
          status: "descontado",
          data_vencimento: "2026-03-10",
          observacao: "",
          data_baixa: "2026-04-02",
          valor_pago: "300.00",
          realizado_por_nome: "Tesouraria ABASE",
          nome_comprovante: "comprovante.pdf",
        },
      ],
      kpis: {
        total_quitados: 1,
        valor_total_quitado: "300.00",
        quitados_este_mes: 1,
        valor_quitado_este_mes: "300.00",
      },
    };
  }

  return {
    count: 1,
    results: [
      {
        id: 12,
        parcela_id: 12,
        associado_id: 1,
        nome: "Marcianita Michele Ramos Mendes",
        cpf_cnpj: "05201186343",
        matricula: "MAT-001",
        agente_nome: "Agente Alpha",
        contrato_id: 10,
        contrato_codigo: "CTR-001",
        referencia_mes: "2026-03-01",
        valor: "300.00",
        status: "nao_descontado",
        data_vencimento: "2026-03-10",
        observacao: "",
        data_baixa: null,
        valor_pago: null,
        realizado_por_nome: "",
        nome_comprovante: "",
      },
    ],
    kpis: {
      total_pendentes: 1,
      em_aberto: 0,
      nao_descontado: 1,
      valor_total_pendente: "300.00",
      baixas_realizadas_mes: 0,
    },
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
  push.mockReset();
  mockedApiFetch.mockImplementation(async (path, options) => {
    if (path === "associados/agentes") {
      return [{ id: 10, full_name: "Agente Alpha" }];
    }
    if (path === "tesouraria/baixa-manual") {
      const listing = options?.query?.listing === "quitados" ? "quitados" : "pendentes";
      return buildResponse(listing);
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
      <BaixaManualPage />
    </QueryClientProvider>,
  );
}

it("consulta a aba de quitados ao trocar de tab", async () => {
  const user = userEvent.setup();

  renderPage();

  await waitFor(() =>
    expect(
      mockedApiFetch.mock.calls.some(
        ([path, options]) =>
          path === "tesouraria/baixa-manual" && options?.query?.listing === "pendentes",
      ),
    ).toBe(true),
  );

  await user.click(screen.getByRole("tab", { name: "Quitados" }));

  await waitFor(() =>
    expect(
      mockedApiFetch.mock.calls.some(
        ([path, options]) =>
          path === "tesouraria/baixa-manual" && options?.query?.listing === "quitados",
      ),
    ).toBe(true),
  );

  expect(screen.getByText("Total Quitados")).toBeInTheDocument();
  expect(screen.getByText("Marcianita Michele Ramos Mendes")).toBeInTheDocument();
});

it("aplica filtros avancados por agente, data e busca na aba de quitados", async () => {
  const user = userEvent.setup();

  renderPage();

  await user.click(await screen.findByRole("tab", { name: "Quitados" }));
  await user.type(screen.getByPlaceholderText("Buscar por nome, CPF, matrícula ou contrato..."), "MAT-001");
  await user.click(screen.getByRole("button", { name: /filtros avançados/i }));

  await user.selectOptions(screen.getByLabelText("Todos os agentes"), "10");
  const dateInputs = screen.getAllByPlaceholderText("dd/mm/aaaa");
  fireEvent.change(dateInputs[0], { target: { value: "2026-04-01" } });
  fireEvent.change(dateInputs[1], { target: { value: "2026-04-30" } });

  await user.click(screen.getByRole("button", { name: /^Aplicar$/i }));

  await waitFor(() =>
    expect(
      mockedApiFetch.mock.calls.some(
        ([path, options]) =>
          path === "tesouraria/baixa-manual" &&
          options?.query?.listing === "quitados" &&
          options?.query?.agente === "10" &&
          options?.query?.data_inicio === "2026-04-01" &&
          options?.query?.data_fim === "2026-04-30" &&
          options?.query?.search === "MAT-001",
      ),
    ).toBe(true),
  );
});
