"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowUpRightIcon, SearchIcon, XIcon } from "lucide-react";
import { useRouter } from "next/navigation";

import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { apiFetch } from "@/lib/api/client";
import type { ContratoListItem, PaginatedResponse } from "@/lib/api/types";
import { maskCPFCNPJ } from "@/lib/masks";
import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";
import { Popover, PopoverAnchor, PopoverContent } from "@/components/ui/popover";
import { Spinner } from "@/components/ui/spinner";

type GlobalHeaderSearchProps = {
  className?: string;
};

type SearchSuggestion = {
  associadoId: number;
  nome: string;
  cpfCnpj: string;
  matricula: string;
  contratoCodigo: string;
  agenteNome?: string | null;
};

function dedupeSuggestions(rows: ContratoListItem[]) {
  const seen = new Set<number>();
  const suggestions: SearchSuggestion[] = [];

  rows.forEach((row) => {
    if (seen.has(row.associado.id)) {
      return;
    }

    seen.add(row.associado.id);
    suggestions.push({
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

export default function GlobalHeaderSearch({ className }: GlobalHeaderSearchProps) {
  const router = useRouter();
  const [query, setQuery] = React.useState("");
  const [open, setOpen] = React.useState(false);
  const inputRef = React.useRef<HTMLInputElement | null>(null);
  const debouncedQuery = useDebouncedValue(query.trim(), 250);

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

  const shouldShowPopover =
    open && (query.trim().length > 0 || suggestionsQuery.isFetching || suggestions.length > 0);

  const handleSelect = React.useCallback(
    (suggestion: SearchSuggestion) => {
      setOpen(false);
      setQuery(`${suggestion.nome} • ${maskCPFCNPJ(suggestion.cpfCnpj)}`);
      router.push(`/associados/${suggestion.associadoId}`);
    },
    [router],
  );

  return (
    <Popover open={shouldShowPopover} onOpenChange={setOpen}>
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

              if (event.key === "Enter" && suggestions[0]) {
                event.preventDefault();
                handleSelect(suggestions[0]);
              }
            }}
            placeholder="Buscar associado, CPF ou matricula"
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
      >
        {debouncedQuery.length < 2 ? (
          <div className="px-3 py-4 text-sm text-muted-foreground">
            Digite pelo menos 2 caracteres para buscar associados.
          </div>
        ) : suggestionsQuery.isFetching ? (
          <div className="flex items-center gap-2 px-3 py-4 text-sm text-muted-foreground">
            <Spinner />
            Buscando associados...
          </div>
        ) : suggestions.length ? (
          <div className="space-y-1">
            {suggestions.map((suggestion) => (
              <button
                key={suggestion.associadoId}
                type="button"
                className="flex w-full items-start justify-between gap-3 rounded-xl px-3 py-3 text-left transition-colors hover:bg-accent"
                onClick={() => handleSelect(suggestion)}
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-foreground">{suggestion.nome}</p>
                  <p className="mt-1 truncate text-xs text-muted-foreground">
                    {maskCPFCNPJ(suggestion.cpfCnpj)} • {suggestion.matricula || "Sem matricula"}
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
        ) : (
          <div className="px-3 py-4 text-sm text-muted-foreground">
            Nenhum associado encontrado para essa busca.
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
}
