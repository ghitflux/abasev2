import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import DevolucoesAssociadoPage from "./page";
import { apiFetch } from "@/lib/api/client";
import { usePermissions } from "@/hooks/use-permissions";

let mockSearchParams = new URLSearchParams();

jest.mock("@/lib/api/client", () => ({
  apiFetch: jest.fn(),
}));

jest.mock("@/hooks/use-permissions", () => ({
  usePermissions: jest.fn(),
}));

jest.mock("next/navigation", () => ({
  useSearchParams: () => mockSearchParams,
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
  }: {
    value?: Date;
    onChange?: (date?: Date) => void;
    placeholder?: string;
  }) => (
    <input
      value={value ? value.toISOString().slice(0, 10) : ""}
      placeholder={placeholder}
      onChange={(event) => {
        const nextValue = event.target.value;
        if (!nextValue.trim()) {
          onChange?.(undefined);
          return;
        }
        const [year, month, day] = nextValue.split("-").map(Number);
        onChange?.(new Date(year, month - 1, day, 12, 0, 0, 0));
      }}
    />
  ),
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
  }) => (
    <input
      value={value == null ? "" : (value / 100).toFixed(2)}
      placeholder={placeholder}
      onChange={(event) => {
        const normalized = Number.parseFloat(event.target.value.replace(",", "."));
        onChange?.(Number.isNaN(normalized) ? null : Math.round(normalized * 100));
      }}
    />
  ),
}));

jest.mock("@/components/custom/file-upload-dropzone", () => ({
  __esModule: true,
  default: ({
    onUpload,
    onUploadMany,
    file,
    files,
  }: {
    onUpload?: (file: File) => void;
    onUploadMany?: (files: File[]) => void;
    file?: File | null;
    files?: File[];
  }) => (
    <button
      type="button"
      onClick={() => {
        if (onUpload) {
          onUpload(new File(["principal"], file?.name || "comprovante.pdf", { type: "application/pdf" }));
          return;
        }
        onUploadMany?.([
          new File(["extra-1"], "extra-1.pdf", { type: "application/pdf" }),
          new File(["extra-2"], "extra-2.pdf", { type: "application/pdf" }),
        ]);
      }}
    >
      {file
        ? file.name
        : files?.length
          ? `${files.length} arquivo(s)`
          : "Selecionar arquivo"}
    </button>
  ),
}));

jest.mock("@/components/tesouraria/duplicidades-financeiras-panel", () => ({
  __esModule: true,
  default: () => <div>Duplicidades</div>,
}));

const mockedApiFetch = jest.mocked(apiFetch);
const mockedUsePermissions = jest.mocked(usePermissions);

const contratosPayload = {
  count: 1,
  next: null,
  previous: null,
  results: [
    {
      id: 1,
      contrato_id: 1,
      associado_id: 101,
      nome: "Maria Devolução",
      cpf_cnpj: "123.456.789-00",
      matricula: "MAT-001",
      agente_nome: "Agente Norte",
      contrato_codigo: "CTR-001",
      status_contrato: "ativo",
      data_contrato: "2026-03-01",
      mes_averbacao: "2026-03-01",
      tipo_sugerido: "pagamento_indevido",
    },
  ],
  kpis: {
    total_contratos: 1,
    associados_impactados: 1,
    ativos: 1,
    encerrados: 0,
    cancelados: 0,
    total_registros: 1,
    valor_total: "120.00",
    registradas: 1,
    revertidas: 0,
  },
};

const historicoPayload = {
  count: 1,
  next: null,
  previous: null,
  results: [
    {
      id: 11,
      devolucao_id: 11,
      contrato_id: 1,
      associado_id: 101,
      tipo: "pagamento_indevido",
      status_devolucao: "registrada",
      data_devolucao: "2026-03-20",
      quantidade_parcelas: 1,
      valor: "120.00",
      motivo: "Depósito em duplicidade.",
      competencia_referencia: null,
      nome: "Maria Devolução",
      cpf_cnpj: "123.456.789-00",
      matricula: "MAT-001",
      agente_nome: "Agente Norte",
      contrato_codigo: "CTR-001",
      status_contrato: "ativo",
      realizado_por: {
        id: 7,
        full_name: "Tesouraria ABASE",
      },
      revertida_em: null,
      revertida_por: null,
      motivo_reversao: "",
      comprovante: {
        id: null,
        nome: "comprovante.pdf",
        url: "/media/devolucoes/comprovante.pdf",
        arquivo_referencia: "devolucoes/comprovante.pdf",
        arquivo_disponivel_localmente: true,
        tipo_referencia: "local",
      },
      anexos: [
        {
          id: null,
          nome: "comprovante.pdf",
          url: "/media/devolucoes/comprovante.pdf",
          arquivo_referencia: "devolucoes/comprovante.pdf",
          arquivo_disponivel_localmente: true,
          tipo_referencia: "local",
        },
      ],
      pode_reverter: true,
    },
  ],
  kpis: contratosPayload.kpis,
};

function buildPermissions(roles: string[]) {
  return {
    role: roles[0],
    status: "authenticated",
    roles,
    hasRole: (role: string) => roles.includes(role),
    hasAnyRole: (allowed: string[]) => allowed.some((role) => roles.includes(role)),
    user: {
      id: 1,
      email: "tesouraria@abase.local",
      first_name: "Tesouraria",
      last_name: "ABASE",
      full_name: "Tesouraria ABASE",
      primary_role: roles[0],
      roles,
    },
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
      <DevolucoesAssociadoPage />
    </QueryClientProvider>,
  );
}

describe("DevolucoesAssociadoPage", () => {
  beforeEach(() => {
    mockSearchParams = new URLSearchParams();
    mockedUsePermissions.mockReturnValue(buildPermissions(["TESOUREIRO"]));
    mockedApiFetch.mockImplementation(async (path, options = {}) => {
      const method = options.method ?? "GET";

      if (path === "tesouraria/devolucoes/contratos" && method === "GET") {
        return contratosPayload as never;
      }

      if (path === "tesouraria/devolucoes" && method === "GET") {
        return historicoPayload as never;
      }

      if (path === "tesouraria/devolucoes/11/" && method === "PATCH") {
        return historicoPayload.results[0] as never;
      }

      throw new Error(`Unexpected apiFetch call: ${method} ${path}`);
    });
  });

  it("abre o lançamento manual exigindo seleção de contrato elegível", async () => {
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByText("Maria Devolução")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Lançar devolução manual/i }));

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByRole("heading", { name: "Registrar devolução" })).toBeInTheDocument();
    expect(within(dialog).getByLabelText("Buscar contrato elegível")).toBeInTheDocument();
    expect(
      within(dialog).getByText("Selecione um contrato elegível para continuar o lançamento manual."),
    ).toBeInTheDocument();
    expect(within(dialog).getByText("Selecione um contrato")).toBeInTheDocument();
    expect(within(dialog).getAllByRole("combobox").length).toBeGreaterThan(0);
    expect(within(dialog).getByRole("button", { name: "Registrar devolução" })).toBeDisabled();
  });

  it("mostra editar no histórico para tesouraria e mantém ações admin-only ocultas", async () => {
    const user = userEvent.setup();
    renderPage();

    await user.click(await screen.findByRole("tab", { name: "Histórico" }));

    expect(await screen.findByText("Maria Devolução")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Editar/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Reverter/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Excluir/i })).not.toBeInTheDocument();
  });

  it("exibe reverter e excluir no histórico quando o usuário é admin", async () => {
    const user = userEvent.setup();
    mockedUsePermissions.mockReturnValue(buildPermissions(["ADMIN"]));
    renderPage();

    await user.click(await screen.findByRole("tab", { name: "Histórico" }));

    expect(await screen.findByRole("button", { name: /Editar/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Reverter/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Excluir/i })).toBeInTheDocument();
  });
});
