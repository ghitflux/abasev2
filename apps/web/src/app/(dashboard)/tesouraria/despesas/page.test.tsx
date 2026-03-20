import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import TesourariaDespesasPage from "./page";
import { apiFetch } from "@/lib/api/client";

jest.mock("@/lib/api/client", () => ({
  apiFetch: jest.fn(),
}));

jest.mock("sonner", () => ({
  toast: {
    success: jest.fn(),
    error: jest.fn(),
  },
}));

jest.mock("@/components/custom/calendar-competencia", () => ({
  __esModule: true,
  default: ({ value }: { value?: Date }) => (
    <button type="button">Competência {value?.toISOString().slice(0, 7)}</button>
  ),
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

jest.mock("@/components/custom/file-upload-dropzone", () => ({
  __esModule: true,
  default: ({
    onUpload,
    file,
  }: {
    onUpload?: (file: File) => void;
    file?: File | null;
  }) => (
    <button
      type="button"
      onClick={() =>
        onUpload?.(new File(["arquivo"], file?.name || "nota-fiscal.pdf", { type: "application/pdf" }))
      }
    >
      {file ? file.name : "Selecionar arquivo"}
    </button>
  ),
}));

const mockedApiFetch = jest.mocked(apiFetch);

type ExpenseRecord = {
  id: number;
  categoria: string;
  descricao: string;
  valor: string;
  data_despesa: string;
  data_pagamento: string | null;
  status: string;
  tipo: string;
  recorrencia: string;
  recorrencia_ativa: boolean;
  observacoes: string;
  status_anexo: string;
  anexo: {
    nome: string;
    url: string;
    arquivo_referencia: string;
    arquivo_disponivel_localmente: boolean;
    tipo_referencia: string;
  } | null;
  lancado_por: {
    id: number;
    full_name: string;
  } | null;
  created_at: string;
  updated_at: string;
};

function buildKpis(items: ExpenseRecord[]) {
  const total = items.reduce((acc, item) => acc + Number.parseFloat(item.valor), 0);
  const pago = items
    .filter((item) => item.status === "pago")
    .reduce((acc, item) => acc + Number.parseFloat(item.valor), 0);
  const pendente = items
    .filter((item) => item.status === "pendente")
    .reduce((acc, item) => acc + Number.parseFloat(item.valor), 0);

  return {
    total_despesas: items.length,
    valor_total: total.toFixed(2),
    valor_pago: pago.toFixed(2),
    valor_pendente: pendente.toFixed(2),
    pendentes_anexo: items.filter((item) => item.status_anexo === "pendente").length,
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
      <TesourariaDespesasPage />
    </QueryClientProvider>,
  );
}

describe("TesourariaDespesasPage", () => {
  let expenses: ExpenseRecord[];

  beforeEach(() => {
    expenses = [
      {
        id: 1,
        categoria: "Operacional",
        descricao: "Internet corporativa",
        valor: "149.90",
        data_despesa: "2026-03-05",
        data_pagamento: null,
        status: "pendente",
        tipo: "fixa",
        recorrencia: "mensal",
        recorrencia_ativa: true,
        observacoes: "Link principal da associação",
        status_anexo: "pendente",
        anexo: null,
        lancado_por: {
          id: 99,
          full_name: "Tesouraria ABASE",
        },
        created_at: "2026-03-05T10:00:00-03:00",
        updated_at: "2026-03-05T10:00:00-03:00",
      },
    ];

    mockedApiFetch.mockImplementation(async (path, options = {}) => {
      const method = options.method ?? "GET";

      if (path === "tesouraria/despesas" && method === "GET") {
        return {
          count: expenses.length,
          next: null,
          previous: null,
          results: expenses,
          kpis: buildKpis(expenses),
        } as never;
      }

      if (path === "tesouraria/despesas" && method === "POST") {
        const formData = options.formData as FormData;
        const attachment = formData.get("anexo");
        const hasAttachment = attachment instanceof File;
        const next: ExpenseRecord = {
          id: expenses.length + 1,
          categoria: String(formData.get("categoria") ?? ""),
          descricao: String(formData.get("descricao") ?? ""),
          valor: String(formData.get("valor") ?? "0.00"),
          data_despesa: String(formData.get("data_despesa") ?? ""),
          data_pagamento: (formData.get("data_pagamento") as string | null) || null,
          status: String(formData.get("status") ?? "pendente"),
          tipo: String(formData.get("tipo") ?? "fixa"),
          recorrencia: String(formData.get("recorrencia") ?? "nenhuma"),
          recorrencia_ativa: String(formData.get("recorrencia_ativa") ?? "true") === "true",
          observacoes: String(formData.get("observacoes") ?? ""),
          status_anexo: hasAttachment ? "anexado" : "pendente",
          anexo: hasAttachment
            ? {
                nome: (attachment as File).name,
                url: `/media/despesas/${(attachment as File).name}`,
                arquivo_referencia: `despesas/${(attachment as File).name}`,
                arquivo_disponivel_localmente: true,
                tipo_referencia: "local",
              }
            : null,
          lancado_por: {
            id: 99,
            full_name: "Tesouraria ABASE",
          },
          created_at: "2026-03-06T09:00:00-03:00",
          updated_at: "2026-03-06T09:00:00-03:00",
        };
        expenses = [next, ...expenses];
        return next as never;
      }

      const patchMatch = /^tesouraria\/despesas\/(\d+)\/$/.exec(path);
      if (patchMatch && method === "PATCH") {
        const id = Number.parseInt(patchMatch[1], 10);
        const formData = options.formData as FormData;
        const attachment = formData.get("anexo");
        const hasAttachment = attachment instanceof File;
        expenses = expenses.map((item) =>
          item.id === id
            ? {
                ...item,
                categoria: String(formData.get("categoria") ?? item.categoria),
                descricao: String(formData.get("descricao") ?? item.descricao),
                valor: String(formData.get("valor") ?? item.valor),
                data_despesa: String(formData.get("data_despesa") ?? item.data_despesa),
                data_pagamento:
                  (formData.get("data_pagamento") as string | null) ??
                  item.data_pagamento,
                status: String(formData.get("status") ?? item.status),
                tipo: String(formData.get("tipo") ?? item.tipo),
                recorrencia: String(formData.get("recorrencia") ?? item.recorrencia),
                recorrencia_ativa:
                  String(formData.get("recorrencia_ativa") ?? String(item.recorrencia_ativa)) ===
                  "true",
                observacoes: String(formData.get("observacoes") ?? item.observacoes),
                status_anexo: hasAttachment ? "anexado" : item.status_anexo,
                anexo: hasAttachment
                  ? {
                      nome: (attachment as File).name,
                      url: `/media/despesas/${(attachment as File).name}`,
                      arquivo_referencia: `despesas/${(attachment as File).name}`,
                      arquivo_disponivel_localmente: true,
                      tipo_referencia: "local",
                    }
                  : item.anexo,
              }
            : item,
        );
        return expenses.find((item) => item.id === id) as never;
      }

      const uploadMatch = /^tesouraria\/despesas\/(\d+)\/anexar$/.exec(path);
      if (uploadMatch && method === "POST") {
        const id = Number.parseInt(uploadMatch[1], 10);
        const formData = options.formData as FormData;
        const file = formData.get("anexo") as File;
        expenses = expenses.map((item) =>
          item.id === id
            ? {
                ...item,
                status_anexo: "anexado",
                anexo: {
                  nome: file.name,
                  url: `/media/despesas/${file.name}`,
                  arquivo_referencia: `despesas/${file.name}`,
                  arquivo_disponivel_localmente: true,
                  tipo_referencia: "local",
                },
              }
            : item,
        );
        return expenses.find((item) => item.id === id) as never;
      }

      if (/^tesouraria\/despesas\/\d+\/$/.test(path) && method === "DELETE") {
        const id = Number.parseInt(path.replace(/\D/g, ""), 10);
        expenses = expenses.filter((item) => item.id !== id);
        return "" as never;
      }

      throw new Error(`Unexpected apiFetch call: ${method} ${path}`);
    });
  });

  it("renderiza cards, filtros e tabela da visão de despesas", async () => {
    renderPage();

    expect(await screen.findByText("Despesas da associação")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Buscar por categoria ou descrição")).toBeInTheDocument();
    expect(screen.getByText("Total de despesas")).toBeInTheDocument();
    expect(screen.getByText("Pendentes de anexo")).toBeInTheDocument();
    expect(await screen.findByText("Internet corporativa")).toBeInTheDocument();
    expect(screen.getAllByText("Pendente de anexo").length).toBeGreaterThan(0);
  });

  it("cria despesa sem anexo e mantém o status pendente de anexo", async () => {
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Internet corporativa");

    await user.click(screen.getByRole("button", { name: /Nova despesa/i }));
    await user.type(screen.getByLabelText("Categoria"), "Infra");
    await user.type(screen.getByLabelText("Descrição"), "Hospedagem cloud");
    await user.type(screen.getByPlaceholderText("R$ 0,00"), "299.90");
    await user.type(screen.getAllByPlaceholderText("dd/mm/aaaa")[0], "2026-03-15");
    await user.type(screen.getByLabelText("Observações"), "Servidor principal");

    await user.click(screen.getByRole("button", { name: /Lançar despesa/i }));

    expect(await screen.findByText("Hospedagem cloud")).toBeInTheDocument();
    expect(screen.getAllByText("Pendente de anexo").length).toBeGreaterThan(0);
  });

  it("permite anexar o comprovante já no modal de lançamento", async () => {
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Internet corporativa");

    await user.click(screen.getByRole("button", { name: /Nova despesa/i }));
    await user.type(screen.getByLabelText("Categoria"), "Eventos");
    await user.type(screen.getByLabelText("Descrição"), "Coffee break assembleia");
    await user.type(screen.getByPlaceholderText("R$ 0,00"), "120.50");
    await user.type(screen.getAllByPlaceholderText("dd/mm/aaaa")[0], "2026-03-20");
    await user.click(screen.getByRole("button", { name: /Selecionar arquivo/i }));
    await user.click(screen.getByRole("button", { name: /Lançar despesa/i }));

    expect(await screen.findByText("Coffee break assembleia")).toBeInTheDocument();
    expect(screen.getAllByText("Anexado").length).toBeGreaterThan(0);
  });

  it("anexa comprovante depois do lançamento e atualiza a linha", async () => {
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Internet corporativa");

    await user.click(screen.getByRole("button", { name: /^Anexar$/i }));
    await user.click(screen.getByRole("button", { name: /Selecionar arquivo/i }));
    await user.click(screen.getByRole("button", { name: /Salvar anexo/i }));

    await waitFor(() => expect(screen.getAllByText("Anexado").length).toBeGreaterThan(0));
    expect(screen.getByRole("link", { name: /Ver anexo/i })).toBeInTheDocument();
  });
});
