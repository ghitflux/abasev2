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
  });

  it("expoe meus pagamentos para tesoureiro no modulo financeiro", () => {
    const sections = getNavigationForRole("TESOUREIRO");
    const hrefs = sections.flatMap((section) =>
      section.items.flatMap(
        (item) => item.children?.map((child) => child.href) ?? item.href ?? [],
      ),
    );

    expect(hrefs).toContain("/agentes/pagamentos");
    expect(canAccessPath("/agentes/pagamentos", ["TESOUREIRO"])).toBe(true);
    expect(getLegacyRouteTarget("/pagamentos", "TESOUREIRO")).toBe(
      "/agentes/pagamentos",
    );
  });

  it("expoe dashboard apenas para admin", () => {
    const adminSections = getNavigationForRole("ADMIN");
    const adminHrefs = adminSections.flatMap((section) =>
      section.items.flatMap(
        (item) => item.children?.map((child) => child.href) ?? item.href ?? [],
      ),
    );

    expect(adminHrefs).toContain("/dashboard");
    expect(canAccessPath("/dashboard", ["ADMIN"])).toBe(true);
    expect(canAccessPath("/dashboard", ["AGENTE"])).toBe(false);
  });

  it("gera entradas de busca apenas para rotas acessiveis do papel", () => {
    const agentEntries = getNavigationRouteSearchEntries(["AGENTE"]);
    const adminEntries = getNavigationRouteSearchEntries(["ADMIN"]);

    expect(agentEntries.map((entry) => entry.href)).toContain("/agentes/pagamentos");
    expect(agentEntries.map((entry) => entry.href)).not.toContain("/renovacao-ciclos");
    expect(adminEntries.map((entry) => entry.href)).toContain("/renovacao-ciclos");
    expect(
      adminEntries.find((entry) => entry.href === "/tesouraria/baixa-manual")?.searchTerms,
    ).toEqual(expect.arrayContaining(["Baixa Manual", "baixa manual", "manual"]));
  });
});
