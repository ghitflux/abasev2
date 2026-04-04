import type { Role } from "@abase/shared-types";
import type { LucideIcon } from "lucide-react";
import {
  BriefcaseBusiness,
  ClipboardCheck,
  FileBarChart2,
  FileCog,
  HandCoins,
  LayoutDashboard,
  ReceiptText,
  RefreshCcw,
  ShieldCheck,
  Users,
  Wallet,
  ArrowDownToLine,
} from "lucide-react";

export type NavigationItem = {
  title: string;
  href?: string;
  icon: LucideIcon;
  roles: Role[];
  children?: NavigationItem[];
};

export type NavigationSection = {
  title: string;
  items: NavigationItem[];
};

export type NavigationRouteSearchEntry = {
  title: string;
  href: string;
  sectionTitle: string;
  parentTitle?: string;
  searchTerms: string[];
};

const ALL_ROLES: Role[] = [
  "ADMIN",
  "AGENTE",
  "ANALISTA",
  "COORDENADOR",
  "TESOUREIRO",
];

const DEFAULT_ROUTE_BY_ROLE: Record<Role, string> = {
  ADMIN: "/dashboard",
  AGENTE: "/agentes/meus-contratos",
  ANALISTA: "/analise",
  COORDENADOR: "/coordenacao/refinanciamento",
  TESOUREIRO: "/tesouraria",
};

const SHARED_AUTH_PATHS = ["/pagamentos", "/renovacoes"] as const;

const ROLE_ROUTE_PREFIXES: Record<Role, string[]> = {
  ADMIN: ["/"],
  AGENTE: ["/agentes"],
  ANALISTA: ["/analise"],
  COORDENADOR: ["/dashboard", "/coordenacao", "/importacao"],
  TESOUREIRO: ["/tesouraria", "/renovacao-ciclos"],
};

const ROUTE_SEARCH_ALIASES: Partial<Record<string, string[]>> = {
  "/dashboard": ["inicio", "painel", "visao geral"],
  "/agentes/meus-contratos": ["contratos", "meus contratos", "cadastros"],
  "/associados/novo": ["novo associado", "cadastro associado", "cadastrar associado"],
  "/agentes/cadastrar-associado": [
    "novo associado",
    "cadastro associado",
    "cadastrar associado",
  ],
  "/associados": ["lista de associados", "cadastro de associados"],
  "/agentes/esteira-pendencias": [
    "esteira",
    "pendencias",
    "esteira de pendencias",
    "esteira de pendências",
  ],
  "/analise": ["dashboard analise", "analise"],
  "/analise/aptos": [
    "aptos",
    "contratos para renovacao",
    "contratos para renovação",
    "renovacao analise",
  ],
  "/coordenacao/refinanciamento": ["refinanciamento", "coordenacao refinanciamento"],
  "/coordenacao/refinanciados": ["coordenacao refinanciados", "refinanciados"],
  "/agentes/pagamentos": ["pagamentos", "meus pagamentos", "financeiro", "cadastros"],
  "/tesouraria/pagamentos": [
    "pagamentos",
    "tesouraria pagamentos",
    "financeiro",
    "repasse",
  ],
  "/agentes/refinanciados": [
    "minhas renovacoes",
    "minhas renovações",
    "renovacoes",
    "renovações",
    "refinanciados",
  ],
  "/tesouraria": ["novos contratos", "dashboard contratos", "tesouraria", "contratos"],
  "/tesouraria/refinanciamentos": [
    "refinanciamentos",
    "renovacoes",
    "renovações",
    "renovacoes de ciclo",
    "renovacoes de ciclos",
    "tesouraria refinanciamentos",
  ],
  "/tesouraria/baixa-manual": ["inadimplentes", "baixa manual", "baixa", "manual"],
  "/tesouraria/liquidacoes": [
    "liquidacao",
    "liquidação",
    "liquidacao de contratos",
    "liquidacao",
    "liquidar contrato",
    "encerramento de contrato",
  ],
  "/tesouraria/devolucoes": [
    "devolucoes",
    "devoluções",
    "devolucoes ao associado",
    "devolucao",
    "duplicidade",
    "duplicidades",
    "duplicidade financeira",
    "desconto indevido",
    "pagamento indevido",
  ],
  "/tesouraria/despesas": ["despesas", "tesouraria despesas", "lancamento de despesas"],
  "/importacao": ["importacao", "arquivo retorno", "importar retorno"],
  "/renovacao-ciclos": [
    "dashboard de ciclos",
    "renovacao de ciclos",
    "renovacao de ciclo",
    "ciclos",
    "renovacoes",
  ],
  "/relatorios": ["relatorios", "exportacoes"],
  "/configuracoes/usuarios": ["usuarios", "configuracoes usuarios", "gestao de usuarios"],
  "/configuracoes/comissoes": [
    "comissoes",
    "comissões",
    "configuracoes comissoes",
    "configurações comissões",
    "repasse de agentes",
  ],
};

function isAgentAssociadoDetailPath(pathname: string) {
  return /^\/associados\/[^/]+$/.test(pathname);
}

function isCoordenadorAssociadosPath(pathname: string) {
  return pathname === "/associados" || /^\/associados\/[^/]+$/.test(pathname);
}

function isCoordenadorUserManagementPath(pathname: string) {
  return matchesAnyPathPrefix(pathname, [
    "/configuracoes/usuarios",
    "/configuracoes/comissoes",
  ]);
}

function isTesoureiroPagamentosPath(pathname: string) {
  return matchesPathPrefix(pathname, "/tesouraria/pagamentos");
}

function isTesoureiroAssociadoDetailPath(pathname: string) {
  return /^\/associados\/[^/]+$/.test(pathname);
}

function isCoordenadorBaixaManualPath(pathname: string) {
  return matchesAnyPathPrefix(pathname, [
    "/tesouraria/baixa-manual",
    "/tesouraria/inadimplentes",
  ]);
}

function isCoordenadorLiquidacoesPath(pathname: string) {
  return matchesAnyPathPrefix(pathname, [
    "/tesouraria/liquidacoes",
    "/tesouraria/liquidacao",
  ]);
}

function isCoordenadorDevolucoesPath(pathname: string) {
  return matchesAnyPathPrefix(pathname, [
    "/tesouraria/devolucoes",
    "/tesouraria/devolucao",
  ]);
}

export const navigationSections: NavigationSection[] = [
  {
    title: "Visão Geral",
    items: [
      {
        title: "Dashboard",
        href: "/dashboard",
        icon: LayoutDashboard,
        roles: ["ADMIN", "COORDENADOR"],
      },
    ],
  },
  {
    title: "Operação",
    items: [
      {
        title: "Cadastros",
        icon: Users,
        roles: ["ADMIN", "AGENTE", "COORDENADOR", "ANALISTA"],
        children: [
          {
            title: "Meus Contratos",
            href: "/agentes/meus-contratos",
            icon: BriefcaseBusiness,
            roles: ["AGENTE", "ADMIN"],
          },
          {
            title: "Cadastrar Associado",
            href: "/associados/novo",
            icon: Users,
            roles: ["ADMIN", "COORDENADOR", "ANALISTA"],
          },
          {
            title: "Cadastrar Associado",
            href: "/agentes/cadastrar-associado",
            icon: Users,
            roles: ["AGENTE"],
          },
          {
            title: "Associados",
            href: "/associados",
            icon: Users,
            roles: ["ADMIN", "COORDENADOR"],
          },
          {
            title: "Esteira de pendências",
            href: "/agentes/esteira-pendencias",
            icon: ClipboardCheck,
            roles: ["AGENTE", "ADMIN"],
          },
          {
            title: "Renovações",
            href: "/agentes/refinanciados",
            icon: HandCoins,
            roles: ["AGENTE", "ADMIN"],
          },
          {
            title: "Pagamentos",
            href: "/agentes/pagamentos",
            icon: ReceiptText,
            roles: ["AGENTE"],
          },
        ],
      },
      {
        title: "Análise",
        icon: ShieldCheck,
        roles: ["ANALISTA", "COORDENADOR", "ADMIN"],
        children: [
          {
            title: "Dashboard Análise",
            href: "/analise",
            icon: ShieldCheck,
            roles: ["ANALISTA", "COORDENADOR", "ADMIN"],
          },
          {
            title: "Contratos para Renovação",
            href: "/analise/aptos",
            icon: RefreshCcw,
            roles: ["ANALISTA", "ADMIN"],
          },
          {
            title: "Aptos a Renovar",
            href: "/coordenacao/refinanciamento",
            icon: RefreshCcw,
            roles: ["COORDENADOR", "ADMIN"],
          },
          {
            title: "Refinanciados",
            href: "/coordenacao/refinanciados",
            icon: HandCoins,
            roles: ["COORDENADOR", "ADMIN"],
          },
        ],
      },
    ],
  },
  {
    title: "Financeiro",
    items: [
      {
        title: "Tesouraria",
        icon: Wallet,
        roles: ["TESOUREIRO", "ADMIN", "COORDENADOR"],
        children: [
          {
            title: "Novos Contratos",
            href: "/tesouraria",
            icon: BriefcaseBusiness,
            roles: ["TESOUREIRO", "ADMIN"],
          },
          {
            title: "Pagamentos",
            href: "/tesouraria/pagamentos",
            icon: ReceiptText,
            roles: ["TESOUREIRO", "ADMIN"],
          },
          {
            title: "Renovações",
            href: "/tesouraria/refinanciamentos",
            icon: HandCoins,
            roles: ["TESOUREIRO", "ADMIN"],
          },
          {
            title: "Inadimplentes",
            href: "/tesouraria/baixa-manual",
            icon: ArrowDownToLine,
            roles: ["TESOUREIRO", "COORDENADOR", "ADMIN"],
          },
          {
            title: "Liquidação",
            href: "/tesouraria/liquidacoes",
            icon: HandCoins,
            roles: ["TESOUREIRO", "COORDENADOR", "ADMIN"],
          },
          {
            title: "Devoluções",
            href: "/tesouraria/devolucoes",
            icon: ReceiptText,
            roles: ["TESOUREIRO", "COORDENADOR", "ADMIN"],
          },
          {
            title: "Despesas",
            href: "/tesouraria/despesas",
            icon: ClipboardCheck,
            roles: ["TESOUREIRO", "ADMIN"],
          },
        ],
      },
      {
        title: "Importação",
        href: "/importacao",
        icon: FileCog,
        roles: ["ADMIN", "COORDENADOR"],
      },
      {
        title: "Dashboard de Ciclos",
        href: "/renovacao-ciclos",
        icon: RefreshCcw,
        roles: ["ADMIN", "TESOUREIRO"],
      },
      {
        title: "Relatórios",
        href: "/relatorios",
        icon: FileBarChart2,
        roles: ["ADMIN"],
      },
    ],
  },
  {
    title: "Administração",
    items: [
      {
        title: "Configurações",
        icon: FileCog,
        roles: ["ADMIN", "COORDENADOR"],
        children: [
          {
            title: "Usuários",
            href: "/configuracoes/usuarios",
            icon: Users,
            roles: ["ADMIN", "COORDENADOR"],
          },
          {
            title: "Comissões",
            href: "/configuracoes/comissoes",
            icon: HandCoins,
            roles: ["ADMIN", "COORDENADOR"],
          },
        ],
      },
    ],
  },
];

export function getNavigationForRoles(roles: Role[] = []) {
  if (!roles.length) return [];

  const roleSet = new Set(roles);

  return navigationSections
    .map((section) => ({
      ...section,
      items: section.items
        .filter((item) => item.roles.some((itemRole) => roleSet.has(itemRole)))
        .map((item) => ({
          ...item,
          children: item.children?.filter((child) =>
            child.roles.some((childRole) => roleSet.has(childRole)),
          ),
        }))
        .filter((item) => !item.children || item.children.length > 0),
    }))
    .filter((section) => section.items.length > 0);
}

export function getNavigationForRole(role?: Role) {
  return getNavigationForRoles(role ? [role] : []);
}

function buildRouteSearchTerms({
  href,
  title,
  sectionTitle,
  parentTitle,
}: Omit<NavigationRouteSearchEntry, "searchTerms">) {
  return Array.from(
    new Set(
      [
        title,
        sectionTitle,
        parentTitle,
        parentTitle ? `${parentTitle} ${title}` : null,
        parentTitle ? `${sectionTitle} ${parentTitle} ${title}` : `${sectionTitle} ${title}`,
        href.replaceAll("/", " ").replaceAll("-", " ").trim(),
        ...(ROUTE_SEARCH_ALIASES[href] ?? []),
      ].filter((value): value is string => Boolean(value)),
    ),
  );
}

export function getNavigationRouteSearchEntries(roles: Role[] = []) {
  const seen = new Set<string>();
  const entries: NavigationRouteSearchEntry[] = [];

  getNavigationForRoles(roles).forEach((section) => {
    section.items.forEach((item) => {
      if (item.href && !seen.has(item.href)) {
        seen.add(item.href);
        entries.push({
          title: item.title,
          href: item.href,
          sectionTitle: section.title,
          searchTerms: buildRouteSearchTerms({
            title: item.title,
            href: item.href,
            sectionTitle: section.title,
          }),
        });
      }

      item.children?.forEach((child) => {
        if (!child.href || seen.has(child.href)) {
          return;
        }

        seen.add(child.href);
        entries.push({
          title: child.title,
          href: child.href,
          sectionTitle: section.title,
          parentTitle: item.title,
          searchTerms: buildRouteSearchTerms({
            title: child.title,
            href: child.href,
            sectionTitle: section.title,
            parentTitle: item.title,
          }),
        });
      });
    });
  });

  return entries;
}

export function getDefaultRouteForRole(role?: Role) {
  return role ? DEFAULT_ROUTE_BY_ROLE[role] : "/dashboard";
}

function normalizeRelativePath(value?: string | null) {
  if (!value || !value.startsWith("/") || value.startsWith("//")) {
    return null;
  }

  try {
    const url = new URL(value, "http://localhost");
    if (url.origin !== "http://localhost") {
      return null;
    }
    return `${url.pathname}${url.search}${url.hash}`;
  } catch {
    return null;
  }
}

function matchesPathPrefix(pathname: string, prefix: string) {
  if (prefix === "/") return true;
  return pathname === prefix || pathname.startsWith(`${prefix}/`);
}

function matchesAnyPathPrefix(pathname: string, prefixes: string[]) {
  return prefixes.some((prefix) => matchesPathPrefix(pathname, prefix));
}

export function canAccessPath(path: string, roles: Role[] = []) {
  const normalized = normalizeRelativePath(path);
  if (!normalized || roles.length === 0) {
    return false;
  }

  const pathname = new URL(normalized, "http://localhost").pathname;
  if (matchesPathPrefix(pathname, "/tesouraria/confirmacoes")) {
    return false;
  }
  if (roles.includes("ADMIN")) {
    return true;
  }

  if (SHARED_AUTH_PATHS.some((prefix) => matchesPathPrefix(pathname, prefix))) {
    return true;
  }

  if (
    (roles.includes("AGENTE") || roles.includes("ANALISTA")) &&
    isAgentAssociadoDetailPath(pathname)
  ) {
    return true;
  }

  if (
    pathname === "/associados/novo" &&
    (roles.includes("ANALISTA") || roles.includes("COORDENADOR"))
  ) {
    return true;
  }

  if (pathname === "/analise" && roles.includes("COORDENADOR")) {
    return true;
  }

  if (roles.includes("COORDENADOR") && isCoordenadorAssociadosPath(pathname)) {
    return true;
  }

  if (roles.includes("COORDENADOR") && isCoordenadorUserManagementPath(pathname)) {
    return true;
  }

  if (roles.includes("TESOUREIRO") && isTesoureiroPagamentosPath(pathname)) {
    return true;
  }

  if (roles.includes("TESOUREIRO") && isTesoureiroAssociadoDetailPath(pathname)) {
    return true;
  }

  if (roles.includes("COORDENADOR") && isCoordenadorBaixaManualPath(pathname)) {
    return true;
  }

  if (roles.includes("COORDENADOR") && isCoordenadorLiquidacoesPath(pathname)) {
    return true;
  }

  if (roles.includes("COORDENADOR") && isCoordenadorDevolucoesPath(pathname)) {
    return true;
  }

  return roles.some((role) =>
    (ROLE_ROUTE_PREFIXES[role] ?? []).some((prefix) =>
      matchesPathPrefix(pathname, prefix),
    ),
  );
}

export function resolvePostLoginPath(
  next: string | undefined,
  roles: Role[] = [],
  role?: Role,
) {
  const fallback = getDefaultRouteForRole(role ?? roles[0]);
  const normalized = normalizeRelativePath(next);

  if (!normalized) {
    return fallback;
  }

  return canAccessPath(normalized, roles) ? normalized : fallback;
}

export function getLegacyRouteTarget(
  legacyPath: "/pagamentos" | "/renovacoes",
  role?: Role,
) {
  if (legacyPath === "/pagamentos") {
    if (role === "TESOUREIRO" || role === "ADMIN") {
      return "/tesouraria/pagamentos";
    }
    if (role === "AGENTE") {
      return "/agentes/pagamentos";
    }
    return getDefaultRouteForRole(role);
  }

  if (role === "TESOUREIRO" || role === "ADMIN") return "/renovacao-ciclos";
  if (role === "COORDENADOR") return "/coordenacao/refinanciamento";
  if (role === "AGENTE") return "/agentes/refinanciados";
  return getDefaultRouteForRole(role);
}
