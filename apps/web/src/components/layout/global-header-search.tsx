"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowUpRightIcon, SearchIcon, XIcon } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";

import { usePermissions } from "@/hooks/use-permissions";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { apiFetch } from "@/lib/api/client";
import type { ContratoListItem, PaginatedResponse } from "@/lib/api/types";
import { maskCPFCNPJ } from "@/lib/masks";
import {
  getNavigationRouteSearchEntries,
  type NavigationRouteSearchEntry,
} from "@/lib/navigation";
import { cn } from "@/lib/utils";
import { useRouteTransition } from "@/providers/route-transition-provider";
import { Input } from "@/components/ui/input";
import { Popover, PopoverAnchor, PopoverContent } from "@/components/ui/popover";
import { Spinner } from "@/components/ui/spinner";

type GlobalHeaderSearchProps = {
  className?: string;
};

type AssociadoSearchSuggestion = {
  type: "associado";
  associadoId: number;
  nome: string;
  cpfCnpj: string;
  matricula: string;
  contratoCodigo: string;
  agenteNome?: string | null;
};

type RouteSearchSuggestion = {
  type: "route";
  href: string;
  title: string;
  subtitle: string;
  score: number;
};

type SearchSuggestion = AssociadoSearchSuggestion | RouteSearchSuggestion;

function normalizeSearchValue(value?: string | null) {
  return (value ?? "")
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase()
    .trim();
}

function dedupeSuggestions(rows: ContratoListItem[]) {
  const seen = new Set<number>();
  const suggestions: AssociadoSearchSuggestion[] = [];

  rows.forEach((row) => {
    if (seen.has(row.associado.id)) {
      return;
    }

    seen.add(row.associado.id);
    suggestions.push({
      type: "associado",
      associadoId: row.associado.id,
      nome: row.associado.nome_completo,
      cpfCnpj: row.associado.cpf_cnpj,
      matricula: row.associado.matricula || row.associado.matricula_orgao,
      contratoCodigo: row.codigo,
      agenteNome: row.agente?.full_name,
    });
  });

  return suggestions;
}

function rankRouteSuggestions(
  routes: NavigationRouteSearchEntry[],
  query: string,
) {
  const normalizedQuery = normalizeSearchValue(query);
  if (normalizedQuery.length < 2) {
    return [] as RouteSearchSuggestion[];
  }

  const queryTokens = normalizedQuery.split(/\s+/).filter(Boolean);

  return routes
    .map((route) => {
      const normalizedTitle = normalizeSearchValue(route.title);
      const normalizedCompositeTitle = normalizeSearchValue(
        route.parentTitle ? `${route.parentTitle} ${route.title}` : route.title,
      );
      const normalizedTerms = route.searchTerms.map((term) =>
        normalizeSearchValue(term),
      );
      const haystack = normalizedTerms.join(" ");
      const matchesExactQuery = normalizedTerms.some((term) => term === normalizedQuery);
      const matchesPrefix = normalizedTerms.some((term) =>
        term.startsWith(normalizedQuery),
      );
      const matchesContains = haystack.includes(normalizedQuery);
      const matchesTokens = queryTokens.every((token) => haystack.includes(token));

      if (!matchesContains && !matchesTokens) {
        return null;
      }

      let score = 0;

      if (normalizedTitle === normalizedQuery) {
        score += 140;
      } else if (normalizedTitle.startsWith(normalizedQuery)) {
        score += 110;
      } else if (normalizedTitle.includes(normalizedQuery)) {
        score += 80;
      }

      if (normalizedCompositeTitle === normalizedQuery) {
        score += 90;
      } else if (normalizedCompositeTitle.startsWith(normalizedQuery)) {
        score += 70;
      } else if (normalizedCompositeTitle.includes(normalizedQuery)) {
        score += 40;
      }

      if (matchesExactQuery) {
        score += 70;
      } else if (matchesPrefix) {
        score += 45;
      }

      if (matchesTokens) {
        score += 25;
      }

      return {
        type: "route" as const,
        href: route.href,
        title: route.title,
        subtitle: route.parentTitle
          ? `${route.parentTitle} • ${route.sectionTitle}`
          : route.sectionTitle,
        score,
      };
    })
    .filter((route): route is RouteSearchSuggestion => Boolean(route))
    .sort((left, right) => right.score - left.score || left.title.localeCompare(right.title))
    .slice(0, 6);
}

export default function GlobalHeaderSearch({ className }: GlobalHeaderSearchProps) {
  const router = useRouter();
  const pathname = usePathname();
  const { roles } = usePermissions();
  const { startRouteTransition } = useRouteTransition();
  const [query, setQuery] = React.useState("");
  const [open, setOpen] = React.useState(false);
  const inputRef = React.useRef<HTMLInputElement | null>(null);
  const debouncedQuery = useDebouncedValue(query.trim(), 250);
  const routeEntries = React.useMemo(
    () => getNavigationRouteSearchEntries(roles),
    [roles],
  );

  const suggestionsQuery = useQuery({
    queryKey: ["global-header-search", debouncedQuery],
    queryFn: () =>
      apiFetch<PaginatedResponse<ContratoListItem>>("contratos", {
        query: {
          associado: debouncedQuery,
          page_size: 8,
        },
      }),
    enabled: debouncedQuery.length >= 2,
    staleTime: 30 * 1000,
    placeholderData: (previousData) => previousData,
  });

  const suggestions = React.useMemo(
    () => dedupeSuggestions(suggestionsQuery.data?.results ?? []),
    [suggestionsQuery.data?.results],
  );
  const routeSuggestions = React.useMemo(
    () => rankRouteSuggestions(routeEntries, debouncedQuery),
    [debouncedQuery, routeEntries],
  );
  const topSuggestion =
    routeSuggestions.find((suggestion) => suggestion.score >= 70) ??
    suggestions[0] ??
    routeSuggestions[0];

  const shouldShowPopover =
    open &&
    (query.trim().length > 0 ||
      suggestionsQuery.isFetching ||
      routeSuggestions.length > 0 ||
      suggestions.length > 0);

  const handleSelect = React.useCallback(
    (suggestion: SearchSuggestion) => {
      const targetPath =
        suggestion.type === "route"
          ? suggestion.href
          : `/associados/${suggestion.associadoId}`;

      setOpen(false);
      setQuery("");
      inputRef.current?.blur();

      if (pathname !== targetPath) {
        startRouteTransition(targetPath);
        router.push(targetPath);
      }
    },
    [pathname, router, startRouteTransition],
  );

  React.useEffect(() => {
    setQuery("");
    setOpen(false);
  }, [pathname]);

  return (
    <Popover open={shouldShowPopover} onOpenChange={setOpen} modal={false}>
      <PopoverAnchor asChild>
        <div className={cn("relative w-full", className)}>
          <SearchIcon className="pointer-events-none absolute top-1/2 left-4 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            ref={inputRef}
            value={query}
            onFocus={() => setOpen(true)}
            onChange={(event) => {
              setQuery(event.target.value);
              if (!open) {
                setOpen(true);
              }
            }}
            onKeyDown={(event) => {
              if (event.key === "Escape") {
                setOpen(false);
              }

              if (event.key === "Enter" && topSuggestion) {
                event.preventDefault();
                handleSelect(topSuggestion);
              }
            }}
            placeholder="Buscar rota, associado, CPF ou matrícula"
            className="h-12 rounded-2xl border-border/60 bg-card/60 pl-11 pr-12 text-sm"
            autoComplete="off"
          />
          {query ? (
            <button
              type="button"
              aria-label="Limpar busca global"
              className="absolute top-1/2 right-3 -translate-y-1/2 rounded-full p-1 text-muted-foreground transition-colors hover:bg-white/5 hover:text-foreground"
              onClick={() => {
                setQuery("");
                setOpen(false);
                inputRef.current?.focus();
              }}
            >
              <XIcon className="size-4" />
            </button>
          ) : null}
        </div>
      </PopoverAnchor>

      <PopoverContent
        align="start"
        className="w-[var(--radix-popover-anchor-width)] rounded-2xl border-border/60 bg-background/96 p-2"
        onOpenAutoFocus={(event) => event.preventDefault()}
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          inputRef.current?.focus();
        }}
      >
        {debouncedQuery.length < 2 ? (
          <div className="px-3 py-4 text-sm text-muted-foreground">
            Digite pelo menos 2 caracteres para buscar rotas e associados.
          </div>
        ) : routeSuggestions.length || suggestions.length || suggestionsQuery.isFetching ? (
          <div className="space-y-1">
            {routeSuggestions.length ? (
              <div className="space-y-1 pb-1">
                <p className="px-3 pt-1 text-[10px] uppercase tracking-[0.22em] text-muted-foreground">
                  Rotas
                </p>
                {routeSuggestions.map((suggestion) => (
                  <button
                    key={suggestion.href}
                    type="button"
                    className="flex w-full items-start justify-between gap-3 rounded-xl px-3 py-3 text-left transition-colors hover:bg-accent"
                    onClick={() => handleSelect(suggestion)}
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-foreground">
                        {suggestion.title}
                      </p>
                      <p className="mt-1 truncate text-xs text-muted-foreground">
                        {suggestion.subtitle}
                      </p>
                    </div>
                    <ArrowUpRightIcon className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                  </button>
                ))}
              </div>
            ) : null}

            {suggestions.length ? (
              <div className="space-y-1">
                <p className="px-3 pt-1 text-[10px] uppercase tracking-[0.22em] text-muted-foreground">
                  Associados
                </p>
                {suggestions.map((suggestion) => (
                  <button
                    key={suggestion.associadoId}
                    type="button"
                    className="flex w-full items-start justify-between gap-3 rounded-xl px-3 py-3 text-left transition-colors hover:bg-accent"
                    onClick={() => handleSelect(suggestion)}
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-foreground">
                        {suggestion.nome}
                      </p>
                      <p className="mt-1 truncate text-xs text-muted-foreground">
                        {maskCPFCNPJ(suggestion.cpfCnpj)} •{" "}
                        {suggestion.matricula || "Sem matricula"}
                      </p>
                      <p className="mt-1 truncate text-[11px] text-muted-foreground">
                        {suggestion.contratoCodigo}
                        {suggestion.agenteNome ? ` • ${suggestion.agenteNome}` : ""}
                      </p>
                    </div>
                    <ArrowUpRightIcon className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                  </button>
                ))}
              </div>
            ) : null}

            {suggestionsQuery.isFetching ? (
              <div className="flex items-center gap-2 px-3 py-2 text-xs text-muted-foreground">
                <Spinner />
                Buscando associados...
              </div>
            ) : null}
          </div>
        ) : (
          <div className="px-3 py-4 text-sm text-muted-foreground">
            Nenhuma rota ou associado encontrado para essa busca.
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
}
