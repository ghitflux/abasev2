type DashboardRouteKind = "analytics" | "list" | "worklist" | "form" | "detail";

const DASHBOARD_LEGACY_PATHS = new Set(["/pagamentos", "/renovacoes"]);

const ROUTE_PREFIXES: Array<{ kind: DashboardRouteKind; prefixes: string[] }> = [
  {
    kind: "worklist",
    prefixes: [
      "/analise",
      "/agentes/esteira-pendencias",
      "/tesouraria/baixa-manual",
    ],
  },
  {
    kind: "analytics",
    prefixes: ["/dashboard", "/importacao", "/renovacao-ciclos"],
  },
  {
    kind: "form",
    prefixes: ["/associados/novo", "/agentes/cadastrar-associado", "/associados-editar"],
  },
  {
    kind: "list",
    prefixes: [
      "/associados",
      "/agentes/meus-contratos",
      "/agentes/pagamentos",
      "/tesouraria/pagamentos",
      "/agentes/refinanciados",
      "/tesouraria",
      "/tesouraria/refinanciamentos",
      "/coordenacao/refinanciamento",
      "/coordenacao/refinanciados",
      "/configuracoes/usuarios",
      "/configuracoes/comissoes",
      "/relatorios",
    ],
  },
];

function matchesPathPrefix(pathname: string, prefix: string) {
  return pathname === prefix || pathname.startsWith(`${prefix}/`);
}

export function normalizePathname(value?: string | null) {
  if (!value) {
    return null;
  }

  if (value.startsWith("/")) {
    return value.split(/[?#]/, 1)[0] || "/";
  }

  try {
    const url = new URL(value);
    return url.pathname;
  } catch {
    return null;
  }
}

export function resolveDashboardRouteKind(pathname?: string | null): DashboardRouteKind {
  const normalizedPathname = normalizePathname(pathname);

  if (!normalizedPathname) {
    return "list";
  }

  if (
    /^\/associados\/[^/]+\/editar$/.test(normalizedPathname) ||
    /^\/associados\/editar\/[^/]+$/.test(normalizedPathname) ||
    /^\/associados-editar\/[^/]+$/.test(normalizedPathname)
  ) {
    return "form";
  }

  if (/^\/associados\/[^/]+$/.test(normalizedPathname)) {
    return "detail";
  }

  for (const group of ROUTE_PREFIXES) {
    if (group.prefixes.some((prefix) => matchesPathPrefix(normalizedPathname, prefix))) {
      return group.kind;
    }
  }

  return "list";
}

export function isDashboardRoute(pathname?: string | null) {
  const normalizedPathname = normalizePathname(pathname);

  if (!normalizedPathname) {
    return false;
  }

  if (DASHBOARD_LEGACY_PATHS.has(normalizedPathname)) {
    return true;
  }

  if (
    /^\/associados\/[^/]+(\/editar)?$/.test(normalizedPathname) ||
    /^\/associados\/editar\/[^/]+$/.test(normalizedPathname) ||
    /^\/associados-editar\/[^/]+$/.test(normalizedPathname)
  ) {
    return true;
  }

  return ROUTE_PREFIXES.some((group) =>
    group.prefixes.some((prefix) => matchesPathPrefix(normalizedPathname, prefix)),
  );
}

export type { DashboardRouteKind };
