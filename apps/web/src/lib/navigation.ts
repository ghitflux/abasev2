import type { Role } from "@abase/shared-types";
import type { LucideIcon } from "lucide-react";
import {
  BellRing,
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
  COORDENADOR: ["/coordenacao"],
  TESOUREIRO: ["/tesouraria", "/importacao", "/renovacao-ciclos"],
};

const ROUTE_SEARCH_ALIASES: Partial<Record<string, string[]>> = {
  "/dashboard": ["inicio", "painel", "visao geral"],
  "/agentes/meus-contratos": ["contratos", "meus contratos", "cadastros"],
  "/agentes/cadastrar-associado": [
    "novo associado",
    "cadastro associado",
    "cadastrar associado",
  ],
  "/associados": ["lista de associados", "cadastro de associados"],
  "/agentes/esteira-pendencias": ["esteira", "pendencias", "esteira de pendencias"],
  "/analise": ["dashboard analise", "analise"],
  "/coordenacao/refinanciamento": ["refinanciamento", "coordenacao refinanciamento"],
  "/coordenacao/refinanciados": ["coordenacao refinanciados", "refinanciados"],
  "/agentes/pagamentos": ["pagamentos", "meus pagamentos", "financeiro"],
  "/agentes/refinanciados": ["meus refinanciados", "refinanciados"],
  "/tesouraria": ["dashboard contratos", "tesouraria", "contratos"],
  "/tesouraria/confirmacoes": ["confirmacoes", "tesouraria confirmacoes"],
  "/tesouraria/refinanciamentos": ["refinanciamentos", "tesouraria refinanciamentos"],
  "/tesouraria/baixa-manual": ["baixa manual", "baixa", "manual"],
  "/tesouraria/despesas": ["despesas", "tesouraria despesas", "lancamento de despesas"],
  "/importacao": ["importacao", "arquivo retorno", "importar retorno"],
  "/renovacao-ciclos": [
    "renovacao de ciclos",
    "renovacao de ciclo",
    "ciclos",
    "renovacoes",
  ],
  "/relatorios": ["relatorios", "exportacoes"],
  "/configuracoes/usuarios": ["usuarios", "configuracoes usuarios", "gestao de usuarios"],
};

function isAgentAssociadoDetailPath(pathname: string) {
  return /^\/associados\/[^/]+$/.test(pathname);
}

function isTesoureiroPagamentosPath(pathname: string) {
  return matchesPathPrefix(pathname, "/agentes/pagamentos");
}

function isCoordenadorBaixaManualPath(pathname: string) {
  return matchesPathPrefix(pathname, "/tesouraria/baixa-manual");
}

export const navigationSections: NavigationSection[] = [
  {
    title: "Visão Geral",
    items: [
      {
        title: "Dashboard",
        href: "/dashboard",
        icon: LayoutDashboard,
        roles: ["ADMIN"],
      },
    ],
  },
  {
    title: "Operação",
    items: [
      {
        title: "Cadastros",
        icon: Users,
        roles: ["ADMIN", "AGENTE"],
        children: [
          {
            title: "Meus Contratos",
            href: "/agentes/meus-contratos",
            icon: BriefcaseBusiness,
            roles: ["AGENTE", "ADMIN"],
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
            roles: ["ADMIN"],
          },
          {
            title: "Esteira",
            href: "/agentes/esteira-pendencias",
            icon: ClipboardCheck,
            roles: ["AGENTE", "ADMIN"],
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
            roles: ["ANALISTA", "ADMIN"],
          },
          {
            title: "Aptos",
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
        roles: ["TESOUREIRO", "ADMIN", "AGENTE", "COORDENADOR"],
        children: [
          {
            title: "Meus Pagamentos",
            href: "/agentes/pagamentos",
            icon: ReceiptText,
            roles: ["AGENTE", "TESOUREIRO", "ADMIN"],
          },
          {
            title: "Refinanciados",
            href: "/agentes/refinanciados",
            icon: HandCoins,
            roles: ["AGENTE", "ADMIN"],
          },
          {
            title: "Dashboard Contratos",
            href: "/tesouraria",
            icon: BriefcaseBusiness,
            roles: ["TESOUREIRO", "ADMIN"],
          },
          {
            title: "Confirmações",
            href: "/tesouraria/confirmacoes",
            icon: BellRing,
            roles: ["TESOUREIRO", "ADMIN"],
          },
          {
            title: "Renovações",
            href: "/tesouraria/refinanciamentos",
            icon: HandCoins,
            roles: ["TESOUREIRO", "ADMIN"],
          },
          {
            title: "Baixa Manual",
            href: "/tesouraria/baixa-manual",
            icon: ArrowDownToLine,
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
        roles: ["ADMIN", "TESOUREIRO"],
      },
      {
        title: "Renovação de Ciclos",
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
        roles: ["ADMIN"],
        children: [
          {
            title: "Usuários",
            href: "/configuracoes/usuarios",
            icon: Users,
            roles: ["ADMIN"],
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

export function canAccessPath(path: string, roles: Role[] = []) {
  const normalized = normalizeRelativePath(path);
  if (!normalized || roles.length === 0) {
    return false;
  }

  const pathname = new URL(normalized, "http://localhost").pathname;
  if (roles.includes("ADMIN")) {
    return true;
  }

  if (SHARED_AUTH_PATHS.some((prefix) => matchesPathPrefix(pathname, prefix))) {
    return true;
  }

  if (roles.includes("AGENTE") && isAgentAssociadoDetailPath(pathname)) {
    return true;
  }

  if (roles.includes("TESOUREIRO") && isTesoureiroPagamentosPath(pathname)) {
    return true;
  }

  if (roles.includes("COORDENADOR") && isCoordenadorBaixaManualPath(pathname)) {
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
    if (role === "TESOUREIRO" || role === "AGENTE" || role === "ADMIN") {
      return "/agentes/pagamentos";
    }
    return getDefaultRouteForRole(role);
  }

  if (role === "TESOUREIRO" || role === "ADMIN") return "/renovacao-ciclos";
  if (role === "COORDENADOR") return "/coordenacao/refinanciamento";
  if (role === "AGENTE") return "/agentes/refinanciados";
  return getDefaultRouteForRole(role);
}
