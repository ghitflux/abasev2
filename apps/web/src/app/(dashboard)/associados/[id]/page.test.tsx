import * as React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import AssociadoPage from "./page";
import { apiFetch } from "@/lib/api/client";

const mockReplace = jest.fn();
const mockUsePermissions = jest.fn();
let mockSearchParams = new URLSearchParams("");

jest.mock("@/lib/api/client", () => ({
  apiFetch: jest.fn(),
}));

jest.mock("@/hooks/use-permissions", () => ({
  usePermissions: () => mockUsePermissions(),
}));

jest.mock("@/components/auth/role-guard", () => {
  function RoleGuardMock({ children }: React.PropsWithChildren) {
    return <>{children}</>;
  }

  RoleGuardMock.displayName = "RoleGuardMock";
  return RoleGuardMock;
});

jest.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: mockReplace,
  }),
  useSearchParams: () => mockSearchParams,
}));

jest.mock("@/components/associados/associado-contracts-overview", () => ({
  AssociadoContractsOverview: () => <div>AssociadoContractsOverviewMock</div>,
  AssociadoDocumentsGrid: () => <div>AssociadoDocumentsGridMock</div>,
}));

jest.mock("@/components/associados/cadastro-origem-badge", () => {
  function CadastroOrigemBadgeMock() {
    return <div>CadastroOrigemBadgeMock</div>;
  }

  CadastroOrigemBadgeMock.displayName = "CadastroOrigemBadgeMock";
  return CadastroOrigemBadgeMock;
});

jest.mock("@/components/custom/status-badge", () => {
  function StatusBadgeMock({
    label,
    status,
  }: {
    label?: string;
    status?: string;
  }) {
    return <div>{label ?? status ?? "StatusBadgeMock"}</div>;
  }

  StatusBadgeMock.displayName = "StatusBadgeMock";
  return StatusBadgeMock;
});

jest.mock("@/components/associados/admin-contract-editor", () => {
  const React = require("react");

  const AdminContractEditorMock = React.forwardRef(
    function AdminContractEditorMock() {
      return <div>AdminContractEditorMock</div>;
    },
  );

  return {
    __esModule: true,
    default: AdminContractEditorMock,
  };
});

jest.mock("@/components/associados/admin-esteira-editor", () => {
  const React = require("react");

  const AdminEsteiraEditorMock = React.forwardRef(
    function AdminEsteiraEditorMock() {
      return <div>AdminEsteiraEditorMock</div>;
    },
  );

  return {
    __esModule: true,
    default: AdminEsteiraEditorMock,
  };
});

jest.mock("@/components/associados/admin-file-manager", () => {
  function AdminFileManagerMock() {
    return <div>AdminFileManagerMock</div>;
  }

  AdminFileManagerMock.displayName = "AdminFileManagerMock";
  return {
    __esModule: true,
    default: AdminFileManagerMock,
  };
});

jest.mock("@/components/associados/admin-override-history", () => {
  function AdminOverrideHistoryMock() {
    return <div>AdminOverrideHistoryMock</div>;
  }

  AdminOverrideHistoryMock.displayName = "AdminOverrideHistoryMock";
  return {
    __esModule: true,
    default: AdminOverrideHistoryMock,
  };
});

jest.mock("@/components/associados/admin-override-confirm-dialog", () => {
  const React = require("react");

  function AdminOverrideConfirmDialogMock({
    open,
    title,
    submitLabel,
    onConfirm,
  }: {
    open: boolean;
    title: string;
    submitLabel?: string;
    onConfirm: (motivo: string) => Promise<void> | void;
  }) {
    const [motivo, setMotivo] = React.useState("");
    const [confirmado, setConfirmado] = React.useState(false);

    if (!open) {
      return null;
    }

    return (
      <div>
        <h2>{title}</h2>
        <textarea
          aria-label="Motivo"
          value={motivo}
          onChange={(event: React.ChangeEvent<HTMLTextAreaElement>) => setMotivo(event.target.value)}
        />
        <input
          aria-label="Confirmação"
          type="checkbox"
          checked={confirmado}
          onChange={(event: React.ChangeEvent<HTMLInputElement>) =>
            setConfirmado(event.target.checked)
          }
        />
        <button
          type="button"
          onClick={() => {
            if (confirmado) {
              void onConfirm(motivo);
            }
          }}
        >
          {submitLabel ?? "Salvar alteração"}
        </button>
      </div>
    );
  }

  AdminOverrideConfirmDialogMock.displayName = "AdminOverrideConfirmDialogMock";
  return {
    __esModule: true,
    default: AdminOverrideConfirmDialogMock,
  };
});

jest.mock("@/components/contratos/parcela-detalhe-dialog", () => ({
  ParcelaDetalheDialog: () => null,
}));

jest.mock("@/components/shared/page-skeletons", () => ({
  DetailRouteSkeleton: () => <div>DetailRouteSkeletonMock</div>,
}));

beforeAll(() => {
  Object.defineProperties(HTMLElement.prototype, {
    hasPointerCapture: {
      configurable: true,
      value: jest.fn(() => false),
    },
    setPointerCapture: {
      configurable: true,
      value: jest.fn(),
    },
    releasePointerCapture: {
      configurable: true,
      value: jest.fn(),
    },
  });
});

const mockedApiFetch = jest.mocked(apiFetch);

const associadoFixture = {
  id: 26,
  nome_completo: "MARIA DO AMPARO VASCONCELOS",
  matricula: "3563090",
  matricula_display: "3563090",
  cpf_cnpj: "73858951315",
  tipo_documento: "CPF",
  rg: "123456",
  orgao_expedidor: "SSP",
  data_nascimento: "1960-01-01",
  profissao: "Aposentada",
  estado_civil: "Casada",
  status: "ativo",
  status_visual_slug: "apto_a_renovacao",
  status_visual_label: "Apto Para Renovação",
  origem_cadastro_slug: "web",
  origem_cadastro_label: "Web",
  mobile_sessions: [],
  agente: { id: 5, full_name: "Agente Teste" },
  endereco: {
    cep: "64000000",
    endereco: "Rua Teste",
    numero: "100",
    complemento: "",
    bairro: "Centro",
    cidade: "Teresina",
    uf: "PI",
  },
  dados_bancarios: {
    banco: "Banco Teste",
    agencia: "0001",
    conta: "12345-6",
    tipo_conta: "corrente",
    chave_pix: "",
  },
  contato: {
    celular: "86999999999",
    email: "teste@example.com",
    orgao_publico: "SSSPI",
    situacao_servidor: "Pensionista",
    matricula_servidor: "3563090",
  },
  contratos: [],
  documentos: [],
  esteira: {
    etapa_atual: "analise",
    status: "aguardando",
    transicoes: [],
  },
};

const editorFixture = {
  associado: {
    id: 26,
    matricula: "3563090",
    tipo_documento: "CPF",
    nome_completo: "MARIA DO AMPARO VASCONCELOS",
    cpf_cnpj: "73858951315",
    status: "ativo",
  },
  contratos: [{ id: 9001 }],
  esteira: {
    etapa_atual: "analise",
    status: "aguardando",
    transicoes: [],
  },
  documentos: [],
  inactivation_reversal: {
    event_id: null,
    available: false,
    previous_status: "",
    target_status: "",
    event_created_at: null,
    realizado_por: null,
  },
  warnings: [],
};

async function renderPage() {
  const client = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
      mutations: {
        retry: false,
      },
    },
  });

  let rendered: ReturnType<typeof render> | undefined;
  await act(async () => {
    rendered = render(
      <QueryClientProvider client={client}>
        <React.Suspense fallback={<div>SuspenseFallback</div>}>
          <AssociadoPage params={Promise.resolve({ id: "26" })} />
        </React.Suspense>
      </QueryClientProvider>,
    );
  });

  return rendered!;
}

beforeEach(() => {
  mockSearchParams = new URLSearchParams("");
  mockReplace.mockReset();
  mockUsePermissions.mockReturnValue({
    hasRole: (role: string) => role === "ADMIN",
  });
  mockedApiFetch.mockImplementation(async (path) => {
    if (path === "associados/26") {
      return associadoFixture;
    }
    if (path === "admin-overrides/associados/26/editor/") {
      return editorFixture;
    }
    if (path === "admin-overrides/associados/26/history/") {
      return [];
    }

    throw new Error(`Unexpected path: ${String(path)}`);
  });
});

describe("AssociadoPage admin editor", () => {
  it("ativa o editor, abre os blocos administrativos e preserva admin=1 no link de edição", async () => {
    const user = userEvent.setup();

    await renderPage();

    expect(
      await screen.findByText("MARIA DO AMPARO VASCONCELOS"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Inativar associado/i }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Excluir associado/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Remover da fila/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Editar cadastro" }),
    ).toHaveAttribute("href", "/associados-editar/26");

    await user.click(
      screen.getByRole("switch", { name: /modo editor avançado/i }),
    );

    expect(
      await screen.findByText("Editor avançado ativo"),
    ).toBeInTheDocument();
    expect(screen.getByText("AdminContractEditorMock")).toBeInTheDocument();
    expect(screen.getByText("AdminFileManagerMock")).toBeInTheDocument();
    expect(screen.getByText("AdminEsteiraEditorMock")).toBeInTheDocument();
    expect(screen.getByText("AdminOverrideHistoryMock")).toBeInTheDocument();
    expect(
      screen
        .getAllByRole("link", { name: "Editar cadastro" })
        .every((link) => link.getAttribute("href") === "/associados-editar/26?admin=1"),
    ).toBe(true);

    expect(mockReplace).toHaveBeenCalledWith("/associados/26?admin=1", {
      scroll: false,
    });
  });

  it("confirma a inativacao informando o tipo operacional escolhido", async () => {
    const user = userEvent.setup();
    mockedApiFetch.mockImplementation(async (path, options) => {
      if (path === "associados/26") {
        return associadoFixture;
      }
      if (path === "associados/26/inativar") {
        expect(options).toEqual(
          expect.objectContaining({
            method: "POST",
            body: { status_destino: "inativo_passivel_renovacao" },
          }),
        );
        return {
          ...associadoFixture,
          status: "apto_a_renovar",
          status_visual_slug: "apto_a_renovar",
          status_visual_label: "Apto a renovar",
        };
      }
      if (path === "admin-overrides/associados/26/editor/") {
        return editorFixture;
      }
      if (path === "admin-overrides/associados/26/history/") {
        return [];
      }

      throw new Error(`Unexpected path: ${String(path)}`);
    });

    await renderPage();

    await user.click(
      await screen.findByRole("button", { name: /Inativar associado/i }),
    );
    expect(screen.getByText("Inativo inadimplente")).toBeInTheDocument();
    await user.click(screen.getByRole("combobox"));
    await user.click(screen.getByRole("option", { name: "Inativo passível de renovação" }));

    await user.click(screen.getByRole("button", { name: /Confirmar inativação/i }));

    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith(
        "associados/26/inativar",
        expect.objectContaining({
          method: "POST",
          body: { status_destino: "inativo_passivel_renovacao" },
        }),
      ),
    );
  });

  it("mostra erro explícito quando o payload do editor falha ao carregar", async () => {
    const user = userEvent.setup();
    mockedApiFetch.mockImplementation(async (path) => {
      if (path === "associados/26") {
        return associadoFixture;
      }
      if (path === "admin-overrides/associados/26/editor/") {
        throw new Error("Editor indisponível");
      }
      if (path === "admin-overrides/associados/26/history/") {
        return [];
      }

      throw new Error(`Unexpected path: ${String(path)}`);
    });

    await renderPage();

    expect(
      await screen.findByText("MARIA DO AMPARO VASCONCELOS"),
    ).toBeInTheDocument();

    await user.click(
      screen.getByRole("switch", { name: /modo editor avançado/i }),
    );

    expect(
      await screen.findByText("Falha ao carregar o editor avançado"),
    ).toBeInTheDocument();
    expect(screen.getAllByText("Editor indisponível").length).toBeGreaterThan(0);
    expect(
      screen.getByRole("button", { name: "Tentar novamente" }),
    ).toBeInTheDocument();

    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith(
        "admin-overrides/associados/26/editor/",
      ),
    );
  });

  it("reverte a inativacao pelo editor avancado sem iniciar reativacao", async () => {
    const user = userEvent.setup();
    mockedApiFetch.mockImplementation(async (path, options) => {
      if (path === "associados/26") {
        return associadoFixture;
      }
      if (path === "admin-overrides/associados/26/editor/") {
        return {
          ...editorFixture,
          associado: {
            ...editorFixture.associado,
            status: "inadimplente",
          },
          inactivation_reversal: {
            event_id: 77,
            available: true,
            previous_status: "ativo",
            target_status: "inadimplente",
            event_created_at: "2026-04-22T12:00:00Z",
            realizado_por: { id: 9, full_name: "Coordenador Teste" },
          },
        };
      }
      if (path === "admin-overrides/associados/26/history/") {
        return [];
      }
      if (path === "admin-overrides/events/77/reverter/") {
        expect(options).toEqual(
          expect.objectContaining({
            method: "POST",
            body: { motivo_reversao: "Inativação acidental" },
          }),
        );
        return { id: 77 };
      }

      throw new Error(`Unexpected path: ${String(path)}`);
    });

    await renderPage();
    expect(
      await screen.findByText("MARIA DO AMPARO VASCONCELOS"),
    ).toBeInTheDocument();
    await user.click(
      screen.getByRole("switch", { name: /modo editor avançado/i }),
    );

    await user.click(
      await screen.findByRole("button", { name: /Reverter inativação/i }),
    );
    await user.type(screen.getByRole("textbox"), "Inativação acidental");
    await user.click(screen.getByRole("checkbox"));
    await user.click(
      screen.getAllByRole("button", { name: "Reverter inativação" })[1],
    );

    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith(
        "admin-overrides/events/77/reverter/",
        expect.objectContaining({
          method: "POST",
          body: { motivo_reversao: "Inativação acidental" },
        }),
      ),
    );
  });
});
