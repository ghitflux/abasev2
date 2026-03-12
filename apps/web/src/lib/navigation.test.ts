import {
  canAccessPath,
  getLegacyRouteTarget,
  getNavigationForRole,
} from "./navigation";

describe("navigation", () => {
  it("nao expoe a rota de associados para agente", () => {
    const sections = getNavigationForRole("AGENTE");
    const hrefs = sections.flatMap((section) =>
      section.items.flatMap((item) => item.children?.map((child) => child.href) ?? item.href ?? []),
    );

    expect(hrefs).not.toContain("/associados");
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
      section.items.flatMap((item) => item.children?.map((child) => child.href) ?? item.href ?? []),
    );

    expect(hrefs).toContain("/agentes/pagamentos");
    expect(canAccessPath("/agentes/pagamentos", ["TESOUREIRO"])).toBe(true);
    expect(getLegacyRouteTarget("/pagamentos", "TESOUREIRO")).toBe("/agentes/pagamentos");
  });
});
