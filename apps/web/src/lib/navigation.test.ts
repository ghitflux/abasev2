import {
  canAccessPath,
  getLegacyRouteTarget,
  getNavigationForRole,
  getNavigationRouteSearchEntries,
} from "./navigation";

describe("navigation", () => {
  it("nao expoe a rota de associados para agente", () => {
    const sections = getNavigationForRole("AGENTE");
    const hrefs = sections.flatMap((section) =>
      section.items.flatMap(
        (item) => item.children?.map((child) => child.href) ?? item.href ?? [],
      ),
    );

    expect(hrefs).not.toContain("/associados");
    expect(hrefs).not.toContain("/dashboard");
    expect(hrefs).toEqual(
      expect.arrayContaining([
        "/agentes/cadastrar-associado",
        "/agentes/meus-contratos",
        "/agentes/pagamentos",
        "/agentes/esteira-pendencias",
        "/agentes/refinanciados",
      ]),
    );

    const cadastros = sections.find((section) => section.title === "Operação");
    const financeiro = sections.find(
      (section) => section.title === "Financeiro",
    );
    const cadastroChildren =
      cadastros?.items.find((item) => item.title === "Cadastros")?.children ??
      [];
    const financeiroChildren =
      financeiro?.items.flatMap((item) => item.children ?? []) ?? [];

    expect(cadastroChildren.map((entry) => entry.href)).toContain(
      "/agentes/pagamentos",
    );
    expect(financeiroChildren.map((entry) => entry.href)).not.toContain(
      "/agentes/pagamentos",
    );
    expect(
      cadastroChildren.find((entry) => entry.href === "/agentes/refinanciados")
        ?.title,
    ).toBe("Aptos a renovar");
    expect(
      cadastroChildren.find((entry) => entry.href === "/agentes/pagamentos")
        ?.title,
    ).toBe("Pagamentos");
  });

  it("expoe pagamentos da tesouraria para tesoureiro no modulo financeiro", () => {
    const sections = getNavigationForRole("TESOUREIRO");
    const hrefs = sections.flatMap((section) =>
      section.items.flatMap(
        (item) => item.children?.map((child) => child.href) ?? item.href ?? [],
      ),
    );

    expect(hrefs).toContain("/tesouraria/pagamentos");
    expect(hrefs).toContain("/tesouraria/liquidacoes");
    expect(hrefs).toContain("/tesouraria/devolucoes");
    expect(hrefs).toContain("/tesouraria/despesas");
    expect(hrefs).not.toContain("/importacao");
    expect(canAccessPath("/agentes/pagamentos", ["TESOUREIRO"])).toBe(false);
    expect(canAccessPath("/tesouraria/pagamentos", ["TESOUREIRO"])).toBe(true);
    expect(canAccessPath("/associados/123", ["TESOUREIRO"])).toBe(true);
    expect(canAccessPath("/tesouraria/liquidacoes", ["TESOUREIRO"])).toBe(true);
    expect(canAccessPath("/tesouraria/devolucoes", ["TESOUREIRO"])).toBe(true);
    expect(canAccessPath("/tesouraria/despesas", ["TESOUREIRO"])).toBe(true);
    expect(canAccessPath("/importacao", ["TESOUREIRO"])).toBe(false);
    expect(getLegacyRouteTarget("/pagamentos", "TESOUREIRO")).toBe(
      "/tesouraria/pagamentos",
    );
  });

  it("expoe dashboard para admin e coordenador", () => {
    const adminSections = getNavigationForRole("ADMIN");
    const adminHrefs = adminSections.flatMap((section) =>
      section.items.flatMap(
        (item) => item.children?.map((child) => child.href) ?? item.href ?? [],
      ),
    );
    const coordinatorSections = getNavigationForRole("COORDENADOR");
    const coordinatorHrefs = coordinatorSections.flatMap((section) =>
      section.items.flatMap(
        (item) => item.children?.map((child) => child.href) ?? item.href ?? [],
      ),
    );

    expect(adminHrefs).toContain("/dashboard");
    expect(coordinatorHrefs).toContain("/dashboard");
    expect(canAccessPath("/dashboard", ["ADMIN"])).toBe(true);
    expect(canAccessPath("/dashboard", ["COORDENADOR"])).toBe(true);
    expect(canAccessPath("/dashboard", ["AGENTE"])).toBe(false);
  });

  it("libera a rota de renovacoes do agente para analista e coordenador em modo global", () => {
    const coordinatorSections = getNavigationForRole("COORDENADOR");
    const analystSections = getNavigationForRole("ANALISTA");

    const coordinatorHrefs = coordinatorSections.flatMap((section) =>
      section.items.flatMap(
        (item) => item.children?.map((child) => child.href) ?? item.href ?? [],
      ),
    );
    const analystHrefs = analystSections.flatMap((section) =>
      section.items.flatMap(
        (item) => item.children?.map((child) => child.href) ?? item.href ?? [],
      ),
    );

    expect(coordinatorHrefs).toContain("/agentes/refinanciados");
    expect(analystHrefs).toContain("/agentes/refinanciados");
    expect(canAccessPath("/agentes/refinanciados", ["COORDENADOR"])).toBe(true);
    expect(canAccessPath("/agentes/refinanciados", ["ANALISTA"])).toBe(true);
  });

  it("gera entradas de busca apenas para rotas acessiveis do papel", () => {
    const agentEntries = getNavigationRouteSearchEntries(["AGENTE"]);
    const adminEntries = getNavigationRouteSearchEntries(["ADMIN"]);

    expect(agentEntries.map((entry) => entry.href)).toContain(
      "/agentes/pagamentos",
    );
    expect(adminEntries.map((entry) => entry.href)).toContain(
      "/tesouraria/pagamentos",
    );
    expect(agentEntries.map((entry) => entry.href)).not.toContain(
      "/renovacao-ciclos",
    );
    expect(adminEntries.map((entry) => entry.href)).toContain(
      "/renovacao-ciclos",
    );
    expect(adminEntries.map((entry) => entry.href)).toContain(
      "/tesouraria/despesas",
    );
    expect(
      adminEntries.find((entry) => entry.href === "/tesouraria/baixa-manual")
        ?.searchTerms,
    ).toEqual(
      expect.arrayContaining([
        "Inadimplentes",
        "inadimplentes",
        "baixa manual",
      ]),
    );
    expect(
      adminEntries.find((entry) => entry.href === "/tesouraria/despesas")
        ?.searchTerms,
    ).toEqual(
      expect.arrayContaining([
        "Despesas",
        "despesas",
        "lancamento de despesas",
      ]),
    );
    expect(
      adminEntries.find((entry) => entry.href === "/tesouraria/liquidacoes")
        ?.searchTerms,
    ).toEqual(
      expect.arrayContaining([
        "Liquidação",
        "liquidação",
        "liquidacao de contratos",
        "liquidar contrato",
      ]),
    );
    expect(
      adminEntries.find((entry) => entry.href === "/tesouraria/devolucoes")
        ?.searchTerms,
    ).toEqual(
      expect.arrayContaining([
        "Devoluções",
        "devoluções",
        "duplicidades",
        "duplicidade financeira",
        "devolucoes ao associado",
        "desconto indevido",
      ]),
    );
  });

  it("renomeia a rota aptos do analista e libera detalhe de associado", () => {
    const analystSections = getNavigationForRole("ANALISTA");
    const analiseChildren =
      analystSections
        .find((section) => section.title === "Operação")
        ?.items.find((item) => item.title === "Análise")?.children ?? [];

    expect(analiseChildren.map((item) => item.href)).toEqual([
      "/analise",
      "/analise/aptos",
    ]);
    expect(
      analiseChildren.find((item) => item.href === "/analise/aptos")?.title,
    ).toBe("Esteira de Renovação");
    expect(canAccessPath("/associados/123", ["ANALISTA"])).toBe(true);
    expect(canAccessPath("/analise/aptos", ["COORDENADOR"])).toBe(true);
  });

  it("renomeia as filas da tesouraria e libera liquidacoes para coordenacao", () => {
    const financeSections = getNavigationForRole("TESOUREIRO");
    const tesourariaChildren =
      financeSections
        .find((section) => section.title === "Financeiro")
        ?.items.find((item) => item.title === "Tesouraria")?.children ?? [];

    expect(
      tesourariaChildren.find((item) => item.href === "/tesouraria")?.title,
    ).toBe("Novos Contratos");
    expect(
      tesourariaChildren.find((item) => item.href === "/tesouraria/pagamentos")
        ?.title,
    ).toBe("Pagamentos");
    expect(
      tesourariaChildren.find(
        (item) => item.href === "/tesouraria/confirmacoes",
      )?.title,
    ).toBe("Confirmações");
    expect(
      tesourariaChildren.find(
        (item) => item.href === "/tesouraria/refinanciamentos",
      )?.title,
    ).toBe("Contratos para Renovação");
    expect(
      tesourariaChildren.find(
        (item) => item.href === "/tesouraria/baixa-manual",
      )?.title,
    ).toBe("Inadimplentes");
    expect(
      tesourariaChildren.find((item) => item.href === "/tesouraria/liquidacoes")
        ?.title,
    ).toBe("Liquidação");
    expect(
      tesourariaChildren.find((item) => item.href === "/tesouraria/devolucoes")
        ?.title,
    ).toBe("Devoluções");
    expect(canAccessPath("/tesouraria/inadimplentes", ["COORDENADOR"])).toBe(
      true,
    );
    expect(canAccessPath("/tesouraria/liquidacoes", ["COORDENADOR"])).toBe(
      true,
    );
    expect(canAccessPath("/tesouraria/liquidacao", ["COORDENADOR"])).toBe(true);
    expect(canAccessPath("/tesouraria/devolucoes", ["COORDENADOR"])).toBe(true);
    expect(canAccessPath("/tesouraria/devolucao", ["COORDENADOR"])).toBe(true);
    expect(canAccessPath("/tesouraria/confirmacoes", ["COORDENADOR"])).toBe(
      true,
    );
    expect(canAccessPath("/tesouraria/confirmacoes", ["TESOUREIRO"])).toBe(
      true,
    );
  });

  it("libera associados, usuarios e importacao para coordenador", () => {
    const coordinatorSections = getNavigationForRole("COORDENADOR");
    const hrefs = coordinatorSections.flatMap((section) =>
      section.items.flatMap(
        (item) => item.children?.map((child) => child.href) ?? item.href ?? [],
      ),
    );

    expect(hrefs).toContain("/associados");
    expect(hrefs).toContain("/dashboard");
    expect(hrefs).toContain("/configuracoes/usuarios");
    expect(hrefs).toContain("/configuracoes/comissoes");
    expect(hrefs).toContain("/importacao");
    expect(hrefs).toContain("/analise");
    expect(hrefs).toContain("/tesouraria");
    expect(hrefs).toContain("/tesouraria/pagamentos");
    expect(hrefs).toContain("/tesouraria/confirmacoes");
    expect(hrefs).toContain("/tesouraria/refinanciamentos");
    expect(hrefs).toContain("/tesouraria/despesas");
    expect(canAccessPath("/dashboard", ["COORDENADOR"])).toBe(true);
    expect(canAccessPath("/associados", ["COORDENADOR"])).toBe(true);
    expect(canAccessPath("/associados/123", ["COORDENADOR"])).toBe(true);
    expect(canAccessPath("/associados/123/editar", ["COORDENADOR"])).toBe(
      false,
    );
    expect(canAccessPath("/configuracoes/usuarios", ["COORDENADOR"])).toBe(
      true,
    );
    expect(canAccessPath("/configuracoes/comissoes", ["COORDENADOR"])).toBe(
      true,
    );
    expect(canAccessPath("/importacao", ["COORDENADOR"])).toBe(true);
    expect(canAccessPath("/analise", ["COORDENADOR"])).toBe(true);
    expect(canAccessPath("/tesouraria", ["COORDENADOR"])).toBe(true);
    expect(canAccessPath("/tesouraria/pagamentos", ["COORDENADOR"])).toBe(true);
    expect(canAccessPath("/tesouraria/confirmacoes", ["COORDENADOR"])).toBe(
      true,
    );
    expect(canAccessPath("/tesouraria/refinanciamentos", ["COORDENADOR"])).toBe(
      true,
    );
    expect(canAccessPath("/tesouraria/despesas", ["COORDENADOR"])).toBe(true);
  });

  it("separa a secao de coordenacao da visao de analise na sidebar", () => {
    const coordinatorSections = getNavigationForRole("COORDENADOR");
    const operacaoItems =
      coordinatorSections.find((section) => section.title === "Operação")
        ?.items ?? [];

    expect(operacaoItems.map((item) => item.title)).toContain("Coordenação");
    expect(operacaoItems.map((item) => item.title)).not.toContain("Análise");

    const coordenacaoChildren =
      operacaoItems.find((item) => item.title === "Coordenação")?.children ??
      [];

    expect(
      coordenacaoChildren.find(
        (item) => item.href === "/coordenacao/refinanciamento",
      )?.title,
    ).toBe("Validação de Renovação");
    expect(
      coordenacaoChildren.find(
        (item) => item.href === "/coordenacao/refinanciados",
      )?.title,
    ).toBe("Refinanciados");
  });

  it("renomeia dashboard de ciclos para tesouraria e admin", () => {
    const adminEntries = getNavigationRouteSearchEntries(["ADMIN"]);
    expect(
      adminEntries.find((entry) => entry.href === "/renovacao-ciclos")?.title,
    ).toBe("Dashboard de Ciclos");
  });
});
