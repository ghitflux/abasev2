import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import GlobalHeaderSearch from "./global-header-search";
import { apiFetch } from "@/lib/api/client";

const push = jest.fn();
const startRouteTransition = jest.fn();

jest.mock("next/navigation", () => ({
  useRouter: () => ({
    push,
  }),
  usePathname: () => "/dashboard",
}));

jest.mock("@/hooks/use-permissions", () => ({
  usePermissions: () => ({
    roles: ["ADMIN"],
  }),
}));

jest.mock("@/providers/route-transition-provider", () => ({
  useRouteTransition: () => ({
    startRouteTransition,
  }),
}));

jest.mock("@/lib/api/client", () => ({
  apiFetch: jest.fn(),
}));

jest.mock("@/hooks/use-debounced-value", () => ({
  useDebouncedValue: (value: string) => value,
}));

const mockedApiFetch = jest.mocked(apiFetch);

function renderSearch() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <GlobalHeaderSearch />
    </QueryClientProvider>,
  );
}

describe("GlobalHeaderSearch", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    startRouteTransition.mockReset();
    mockedApiFetch.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [
        {
          id: 1,
          codigo: "CTR-001",
          associado: {
            id: 1,
            nome_completo: "Maria de Jesus Santana Costa",
            cpf_cnpj: "23993596315",
            matricula: "MAT-10049",
            matricula_orgao: "MAT-10049",
          },
          agente: {
            id: 99,
            full_name: "Carlos Mendes",
          },
        },
      ],
    } as never);
  });

  it("mantém o foco e aceita digitação contínua enquanto as sugestões são abertas", async () => {
    const user = userEvent.setup();
    renderSearch();

    const input = screen.getByPlaceholderText("Buscar rota, associado, CPF ou matrícula");

    await user.click(input);
    await user.keyboard("2");

    expect(input).toHaveValue("2");
    expect(input).toHaveFocus();

    await user.keyboard("3");

    expect(input).toHaveValue("23");
    expect(input).toHaveFocus();

    await waitFor(() =>
      expect(mockedApiFetch).toHaveBeenCalledWith("contratos", {
        query: {
          associado: "23",
          page_size: 8,
        },
      }),
    );

    expect(await screen.findByText("Maria de Jesus Santana Costa")).toBeInTheDocument();
    expect(input).toHaveFocus();
  });

  it("limpa a busca e fecha as sugestões ao selecionar um associado", async () => {
    const user = userEvent.setup();
    renderSearch();

    const input = screen.getByPlaceholderText("Buscar rota, associado, CPF ou matrícula");

    await user.click(input);
    await user.type(input, "maria");

    const option = await screen.findByRole("button", { name: /Maria de Jesus Santana Costa/i });

    await user.click(option);

    await waitFor(() => expect(push).toHaveBeenCalledWith("/associados/1"));
    expect(startRouteTransition).toHaveBeenCalledWith("/associados/1");
    expect(input).toHaveValue("");
    expect(screen.queryByText("Maria de Jesus Santana Costa")).not.toBeInTheDocument();
  });

  it("permite buscar e navegar para rotas do dashboard", async () => {
    const user = userEvent.setup();
    mockedApiFetch.mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    } as never);

    renderSearch();

    const input = screen.getByPlaceholderText("Buscar rota, associado, CPF ou matrícula");

    await user.click(input);
    await user.type(input, "baixa manual");

    expect(await screen.findByText("Rotas")).toBeInTheDocument();

    const option = await screen.findByRole("button", { name: /Baixa Manual/i });
    await user.click(option);

    await waitFor(() =>
      expect(startRouteTransition).toHaveBeenCalledWith("/tesouraria/baixa-manual"),
    );
    expect(push).toHaveBeenCalledWith("/tesouraria/baixa-manual");
    expect(input).toHaveValue("");
  });

  it("reconhece a rota de despesas da tesouraria na busca global", async () => {
    const user = userEvent.setup();
    mockedApiFetch.mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    } as never);

    renderSearch();

    const input = screen.getByPlaceholderText("Buscar rota, associado, CPF ou matrícula");

    await user.click(input);
    await user.type(input, "despesas");

    const option = await screen.findByRole("button", { name: /Despesas/i });
    await user.click(option);

    await waitFor(() =>
      expect(startRouteTransition).toHaveBeenCalledWith("/tesouraria/despesas"),
    );
    expect(push).toHaveBeenCalledWith("/tesouraria/despesas");
  });
});
