import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
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

jest.mock("@/components/ui/select", () => {
  const React = require("react");
  const SelectContext = React.createContext({
    value: "",
    onValueChange: (_value: string) => {},
  });

  return {
    Select: ({
      value,
      onValueChange,
      children,
    }: {
      value?: string;
      onValueChange?: (value: string) => void;
      children: React.ReactNode;
    }) => (
      <SelectContext.Provider
        value={{
          value: value ?? "",
          onValueChange: onValueChange ?? (() => {}),
        }}
      >
        <div>{children}</div>
      </SelectContext.Provider>
    ),
    SelectTrigger: ({
      children,
      "aria-label": ariaLabel,
    }: {
      children?: React.ReactNode;
      "aria-label"?: string;
    }) => (
      <button type="button" role="combobox" aria-label={ariaLabel}>
        {children}
      </button>
    ),
    SelectValue: ({ placeholder }: { placeholder?: string }) => {
      const { value } = React.useContext(SelectContext);
      return <span>{value || placeholder || ""}</span>;
    },
    SelectContent: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
    SelectItem: ({
      value,
      children,
    }: {
      value: string;
      children?: React.ReactNode;
    }) => {
      const { onValueChange } = React.useContext(SelectContext);
      return (
        <button type="button" role="option" onClick={() => onValueChange(value)}>
          {children}
        </button>
      );
    },
  };
});

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

jest.mock("@/components/ui/sheet", () => ({
  Sheet: ({ children }: { children?: unknown }) => <div>{children}</div>,
  SheetTrigger: ({ children }: { children?: unknown }) => <div>{children}</div>,
  SheetContent: ({ children }: { children?: unknown }) => <div>{children}</div>,
  SheetHeader: ({ children }: { children?: unknown }) => <div>{children}</div>,
  SheetTitle: ({ children }: { children?: unknown }) => <div>{children}</div>,
  SheetDescription: ({ children }: { children?: unknown }) => <div>{children}</div>,
  SheetFooter: ({ children }: { children?: unknown }) => <div>{children}</div>,
}));

const mockedApiFetch = jest.mocked(apiFetch);

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

type ExpenseRecord = {
  id: number;
  categoria: string;
  descricao: string;
  valor: string;
  natureza: string;
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

function buildCurrentMonthIso() {
  const today = new Date();
  const year = String(today.getFullYear());
  const month = String(today.getMonth() + 1).padStart(2, "0");
  return `${year}-${month}-01`;
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
  const resultadoMensalPayload = {
    rows: [
      {
        mes: buildCurrentMonthIso(),
        receitas: "530.00",
        receitas_inadimplencia: "120.00",
        receitas_retorno: "330.00",
        complementos_receita: "80.00",
        despesas: "200.00",
        despesas_manuais: "150.00",
        devolucoes: "50.00",
        pagamentos_operacionais: "45.00",
        lucro: "330.00",
        lucro_liquido: "285.00",
      },
    ],
    totais: {
      receitas: "530.00",
      despesas: "200.00",
      lucro: "330.00",
      lucro_liquido: "285.00",
    },
  };
  const resultadoMensalDetalhePayload = {
    mes: buildCurrentMonthIso(),
    resumo: {
      receitas: "530.00",
      receitas_inadimplencia: "120.00",
      receitas_retorno: "330.00",
      complementos_receita: "80.00",
      despesas: "200.00",
      despesas_manuais: "150.00",
      devolucoes: "50.00",
      pagamentos_operacionais: "45.00",
      lucro: "330.00",
      lucro_liquido: "285.00",
    },
    receitas: [
      {
        id: 1,
        origem: "arquivo_retorno",
        origem_label: "Arquivo retorno",
        data: "2026-03-01",
        referencia: "2026-03-01",
        associado_nome: "Maria Receita",
        cpf_cnpj: "12312312312",
        matricula: "MAT-001",
        agente_nome: "Agente Norte",
        descricao: "Receita reconhecida via arquivo retorno.",
        valor: "330.00",
      },
      {
        id: 2,
        origem: "inadimplencia_manual",
        origem_label: "Inadimplência manual",
        data: "2026-03-12",
        referencia: "2026-03-01",
        associado_nome: "Carlos Manual",
        cpf_cnpj: "32132132132",
        matricula: "MAT-002",
        agente_nome: "Agente Sul",
        descricao: "Recebimento manual de inadimplência.",
        valor: "120.00",
      },
      {
        id: 3,
        origem: "complemento_receita",
        origem_label: "Complemento de receita",
        data: "2026-03-18",
        referencia: "2026-03-18",
        associado_nome: "",
        cpf_cnpj: "",
        matricula: "",
        agente_nome: "",
        descricao: "Compensação no caixa da associação.",
        valor: "80.00",
      },
    ],
    despesas: [
      {
        id: 11,
        origem: "despesa_manual",
        origem_label: "Despesa manual",
        data: "2026-03-05",
        titulo: "Operacional",
        subtitulo: "Internet corporativa",
        descricao: "Link principal da associação",
        referencia: "Pendente · Fixa",
        valor: "150.00",
      },
      {
        id: 12,
        origem: "devolucao",
        origem_label: "Devolução",
        data: "2026-03-09",
        titulo: "João Devolução",
        subtitulo: "CTR-2026-001",
        descricao: "Estorno financeiro",
        referencia: "Pagamento indevido",
        valor: "50.00",
      },
    ],
    pagamentos_operacionais: [
      {
        id: 21,
        data: "2026-03-10",
        favorecido: "Associado Operacional",
        cpf_cnpj: "99988877766",
        agente_nome: "Agente Centro",
        contrato_codigo: "CTR-2026-010",
        origem: "operacional",
        origem_label: "Operacional",
        valor_associado: "30.00",
        valor_agente: "15.00",
        valor_total: "45.00",
      },
    ],
  };

  beforeEach(() => {
    mockedApiFetch.mockReset();
    expenses = [
      {
        id: 1,
        categoria: "Operacional",
        descricao: "Internet corporativa",
        valor: "149.90",
        natureza: "despesa_operacional",
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

      if (path === "tesouraria/despesas/resultado-mensal" && method === "GET") {
        return resultadoMensalPayload as never;
      }

      if (path === "tesouraria/despesas/resultado-mensal/detalhe" && method === "GET") {
        return resultadoMensalDetalhePayload as never;
      }

      if (path === "associados/agentes" && method === "GET") {
        return [
          { id: 99, full_name: "Tesouraria ABASE" },
          { id: 7, full_name: "Agente Norte" },
          { id: 8, full_name: "Agente Sul" },
        ] as never;
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
          natureza: String(formData.get("natureza") ?? "despesa_operacional"),
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
                natureza: String(formData.get("natureza") ?? item.natureza),
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
    expect(screen.getByText("Total de lançamentos")).toBeInTheDocument();
    expect(screen.getAllByText("Sem anexo").length).toBeGreaterThan(0);
    expect(await screen.findByText("Internet corporativa")).toBeInTheDocument();
    expect(screen.getAllByText("Sem anexo").length).toBeGreaterThan(0);
  });

  it("aplica filtro avançado por agente no resultado mensal", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("tab", { name: "Resultado mensal" }));
    expect(await screen.findByText("Janela consolidada")).toBeInTheDocument();
    const resultadoFiltersPanel = screen.getByText("Filtros avançados do resultado")
      .parentElement?.parentElement as HTMLElement;

    await user.selectOptions(
      within(resultadoFiltersPanel).getByRole("combobox", { name: "Todos os agentes" }),
      "7",
    );
    await user.click(within(resultadoFiltersPanel).getByRole("button", { name: "Aplicar" }));

    await waitFor(() => {
      const resultadoCalls = mockedApiFetch.mock.calls.filter(
        ([path]) => path === "tesouraria/despesas/resultado-mensal",
      );
      expect(
        resultadoCalls.some(([, options]) => {
          const agente = options?.query?.agente;
          return agente === "Agente Norte" || agente === "7";
        }),
      ).toBe(true);
    });

    expect(screen.getByText("Agente: Agente Norte")).toBeInTheDocument();
  });

  it("cria despesa sem anexo e mantém o status financeiro escolhido", async () => {
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Internet corporativa");

    await user.click(screen.getByRole("button", { name: /Novo lançamento/i }));
    const dialog = await screen.findByRole("dialog");
    await user.type(screen.getByLabelText("Categoria"), "Infra");
    await user.type(screen.getByLabelText("Descrição"), "Hospedagem cloud");
    await user.type(screen.getByPlaceholderText("R$ 0,00"), "299.90");
    await user.type(screen.getAllByPlaceholderText("dd/mm/aaaa")[0], "2026-03-15");
    await user.click(within(dialog).getAllByRole("combobox")[1]);
    await user.click(await screen.findByRole("option", { name: "Pago" }));
    await user.type(screen.getAllByPlaceholderText("dd/mm/aaaa")[1], "2026-03-16");
    await user.type(screen.getByLabelText("Observações"), "Servidor principal");

    await user.click(screen.getByRole("button", { name: /^Lançar$/i }));

    expect(await screen.findByText("Hospedagem cloud")).toBeInTheDocument();
    expect(screen.getAllByText("Sem anexo").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Pago").length).toBeGreaterThan(0);
  });

  it("permite lançar complemento de receita com a classificação correta", async () => {
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Internet corporativa");

    await user.click(screen.getByRole("button", { name: /Novo lançamento/i }));
    const dialog = await screen.findByRole("dialog");
    await user.type(screen.getByLabelText("Categoria"), "Complementos");
    await user.click(within(dialog).getByRole("combobox", { name: "Natureza do lançamento" }));
    await user.click(await screen.findByRole("option", { name: "Complemento de receita" }));
    await user.type(screen.getByLabelText("Descrição"), "Doação emergencial");
    await user.type(screen.getByPlaceholderText("R$ 0,00"), "80.00");
    await user.type(screen.getAllByPlaceholderText("dd/mm/aaaa")[0], "2026-03-18");
    await user.click(within(dialog).getAllByRole("combobox")[1]);
    await user.click(await screen.findByRole("option", { name: "Pago" }));
    await user.type(screen.getAllByPlaceholderText("dd/mm/aaaa")[1], "2026-03-18");

    await user.click(screen.getByRole("button", { name: /^Lançar$/i }));

    expect(await screen.findByText("Doação emergencial")).toBeInTheDocument();
    expect(screen.getAllByText("Complemento de receita").length).toBeGreaterThan(0);
  });

  it("permite anexar o comprovante já no modal de lançamento", async () => {
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("Internet corporativa");

    await user.click(screen.getByRole("button", { name: /Novo lançamento/i }));
    await user.type(screen.getByLabelText("Categoria"), "Eventos");
    await user.type(screen.getByLabelText("Descrição"), "Coffee break assembleia");
    await user.type(screen.getByPlaceholderText("R$ 0,00"), "120.50");
    await user.type(screen.getAllByPlaceholderText("dd/mm/aaaa")[0], "2026-03-20");
    await user.click(screen.getByRole("button", { name: /Selecionar arquivo/i }));
    await user.click(screen.getByRole("button", { name: /^Lançar$/i }));

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

  it("abre o detalhamento geral, de receitas e de despesas no resultado mensal", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("tab", { name: "Resultado mensal" }));

    const lucroLiquidoButton = screen
      .getAllByRole("button")
      .find((button) => button.textContent?.includes("R$ 285,00"));
    expect(lucroLiquidoButton).toBeDefined();
    await user.click(lucroLiquidoButton as HTMLButtonElement);
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("Composição do mês")).toBeInTheDocument();
    expect(screen.getAllByText("Pagamentos operacionais").length).toBeGreaterThan(0);
    expect(screen.getByText("Complementos de receita")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Valor associado" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Valor agente" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Valor total" })).toBeInTheDocument();
    expect(screen.getByText("Receitas de arquivo retorno")).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Receitas" }));
    expect(await screen.findByText("Receitas do mês")).toBeInTheDocument();
    expect(screen.getByText("Maria Receita")).toBeInTheDocument();
    expect(screen.getByText("Carlos Manual")).toBeInTheDocument();
    expect(screen.getByText("Compensação no caixa da associação.")).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Despesas" }));
    expect(await screen.findByText("Despesas do mês")).toBeInTheDocument();
    expect(screen.getByText("Internet corporativa")).toBeInTheDocument();
    expect(screen.getByText("João Devolução")).toBeInTheDocument();
  });
});
