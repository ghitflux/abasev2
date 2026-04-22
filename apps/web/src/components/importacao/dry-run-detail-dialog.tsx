"use client";

import * as React from "react";
import { DownloadIcon } from "lucide-react";

import type { DryRunItem } from "@/gen/models/DryRunItem";
import CopySnippet from "@/components/shared/copy-snippet";
import StatusBadge from "@/components/custom/status-badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { formatCurrency } from "@/lib/formatters";
import { maskCPFCNPJ } from "@/lib/masks";
import { exportRows, type TableExportColumn } from "@/lib/table-export";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  items: DryRunItem[];
};

const PAGE_SIZE = 15;

function normalizeSearchValue(value: unknown) {
  return String(value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

function formatStatusText(value: string | null | undefined) {
  if (!value) {
    return "—";
  }
  return value.replaceAll("_", " ");
}

function describeItemAction(item: DryRunItem) {
  if (item.desconto_em_associado_inativo) {
    return "Retorno descontou associado inativo";
  }
  if (item.ficara_apto_renovar) {
    return "Entrará em Aptos a renovar após confirmar";
  }
  return "Sem ação automática";
}

function buildSearchHaystack(item: DryRunItem) {
  return normalizeSearchValue(
    [
      item.associado_nome,
      item.nome_servidor,
      item.cpf_cnpj,
      maskCPFCNPJ(item.cpf_cnpj),
      item.matricula_servidor,
      item.orgao_pagto_nome,
      item.associado_status_antes,
      item.associado_status_depois,
      item.ciclo_status_antes,
      item.ciclo_status_depois,
      describeItemAction(item),
    ].join(" "),
  );
}

function slugifyFilename(value: string) {
  return normalizeSearchValue(value)
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export default function DryRunDetailDialog({ open, onOpenChange, title, items }: Props) {
  const [page, setPage] = React.useState(1);
  const [search, setSearch] = React.useState("");
  const deferredSearch = React.useDeferredValue(search);

  const filteredItems = React.useMemo(() => {
    const terms = normalizeSearchValue(deferredSearch)
      .split(/\s+/)
      .filter(Boolean);
    if (!terms.length) {
      return items;
    }
    return items.filter((item) => {
      const haystack = buildSearchHaystack(item);
      return terms.every((term) => haystack.includes(term));
    });
  }, [deferredSearch, items]);

  const totalPages = Math.max(1, Math.ceil(filteredItems.length / PAGE_SIZE));
  const pageItems = filteredItems.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const exportColumns = React.useMemo<TableExportColumn<DryRunItem>[]>(
    () => [
      {
        header: "Associado",
        value: (item) => item.associado_nome || item.nome_servidor || "—",
      },
      {
        header: "CPF",
        value: (item) => maskCPFCNPJ(item.cpf_cnpj),
      },
      {
        header: "Matricula",
        value: (item) => item.matricula_servidor || "—",
      },
      {
        header: "Orgao",
        value: (item) => item.orgao_pagto_nome || "—",
      },
      {
        header: "Valor",
        value: (item) => item.valor_descontado,
      },
      {
        header: "Status Associado Antes",
        value: (item) => formatStatusText(item.associado_status_antes),
      },
      {
        header: "Status Associado Depois",
        value: (item) => formatStatusText(item.associado_status_depois),
      },
      {
        header: "Ciclo Antes",
        value: (item) => formatStatusText(item.ciclo_status_antes),
      },
      {
        header: "Ciclo Depois",
        value: (item) => formatStatusText(item.ciclo_status_depois),
      },
      {
        header: "Acao",
        value: (item) => describeItemAction(item),
      },
    ],
    [],
  );

  const handleExport = React.useCallback(
    (format: "csv" | "pdf" | "excel" | "xlsx") => {
      exportRows(
        format,
        title,
        `${slugifyFilename(title) || "detalhes-previa-importacao"}-${new Date()
          .toISOString()
          .slice(0, 10)}`,
        exportColumns,
        filteredItems,
      );
    },
    [exportColumns, filteredItems, title],
  );

  React.useEffect(() => {
    if (!open) {
      setSearch("");
    }
    setPage(1);
  }, [open, search, title]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="grid max-h-[calc(100vh-2rem)] w-[96vw] max-w-[96vw] grid-rows-[auto_minmax(0,1fr)_auto] overflow-hidden border-border/60 bg-background/95 p-0 sm:max-w-none 2xl:max-w-[100rem]">
        <div className="sticky top-0 z-20 shrink-0 border-b border-border/60 bg-background/95 px-6 py-4 backdrop-blur">
          <DialogHeader className="gap-1">
            <DialogTitle className="text-base">{title}</DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              {search.trim()
                ? `${filteredItems.length} de ${items.length} associado${items.length !== 1 ? "s" : ""}`
                : `${items.length} associado${items.length !== 1 ? "s" : ""}`}
            </DialogDescription>
          </DialogHeader>
          <div className="mt-3 flex flex-col gap-3 border-t border-border/40 pt-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex min-w-0 flex-1 gap-3">
              <Input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Buscar por associado, CPF, matrícula ou órgão..."
                aria-label="Buscar associados da prévia"
                className="rounded-2xl bg-card/60"
              />
              {search.trim() ? (
                <Button
                  type="button"
                  variant="outline"
                  className="rounded-2xl"
                  onClick={() => setSearch("")}
                >
                  Limpar
                </Button>
              ) : null}
            </div>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  type="button"
                  variant="outline"
                  className="rounded-2xl"
                  disabled={filteredItems.length === 0}
                >
                  <DownloadIcon className="size-4" />
                  Exportar
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="rounded-xl">
                <DropdownMenuItem onClick={() => handleExport("csv")}>
                  CSV
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => handleExport("xlsx")}>
                  XLS
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => handleExport("pdf")}>
                  PDF
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>

        <div className="min-h-0 overflow-y-auto">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[72rem] text-sm">
              <thead className="sticky top-0 z-10">
                <tr className="border-b border-border/60 bg-background/95">
                  <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Associado
                  </th>
                  <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Órgão
                  </th>
                  <th className="px-4 py-2.5 text-right text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Valor
                  </th>
                  <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Status Assoc. Antes
                  </th>
                  <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Status Assoc. Depois
                  </th>
                  <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Ciclo Antes
                  </th>
                  <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Ciclo Depois
                  </th>
                  <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Ação
                  </th>
                </tr>
              </thead>
              <tbody>
                {pageItems.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="px-4 py-8 text-center text-sm text-muted-foreground">
                      {search.trim()
                        ? "Nenhum registro encontrado para essa busca."
                        : "Nenhum registro nesta categoria."}
                    </td>
                  </tr>
                ) : (
                  pageItems.map((item, i) => (
                    <tr
                      key={`${item.cpf_cnpj}-${i}`}
                      className="border-b border-border/40 last:border-0 hover:bg-white/3"
                    >
                      <td className="px-4 py-3">
                        <p className="font-medium text-foreground">
                          {item.associado_nome || item.nome_servidor || "—"}
                        </p>
                        <CopySnippet label="CPF" value={maskCPFCNPJ(item.cpf_cnpj)} mono />
                        {item.matricula_servidor && (
                          <CopySnippet
                            label="Matrícula do Servidor"
                            value={item.matricula_servidor}
                            mono
                          />
                        )}
                      </td>
                      <td className="px-4 py-3 text-sm text-muted-foreground">
                        {item.orgao_pagto_nome || "—"}
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-sm">
                        {formatCurrency(item.valor_descontado)}
                      </td>
                      <td className="px-4 py-3">
                        {item.associado_status_antes ? (
                          <StatusBadge status={item.associado_status_antes} />
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {item.associado_status_depois ? (
                          <StatusBadge status={item.associado_status_depois} />
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {item.ciclo_status_antes ? (
                          <StatusBadge status={item.ciclo_status_antes} />
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {item.ciclo_status_depois ? (
                          <StatusBadge status={item.ciclo_status_depois} />
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {item.desconto_em_associado_inativo ? (
                          <span className="inline-flex max-w-[14rem] rounded-full border border-amber-400/25 bg-amber-400/10 px-3 py-1 text-xs font-medium text-amber-200">
                            Retorno descontou associado inativo
                          </span>
                        ) : item.ficara_apto_renovar ? (
                          <span className="inline-flex max-w-[14rem] rounded-full border border-emerald-400/25 bg-emerald-400/10 px-3 py-1 text-xs font-medium text-emerald-200">
                            Entrará em Aptos a renovar após confirmar
                          </span>
                        ) : (
                          <span className="text-xs text-muted-foreground">
                            Sem ação automática
                          </span>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {totalPages > 1 && (
          <div className="flex shrink-0 items-center justify-between border-t border-border/60 px-6 py-3">
            <span className="text-xs text-muted-foreground">
              Página {page} de {totalPages}
            </span>
            <div className="flex gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="rounded px-2 py-1 text-xs text-muted-foreground hover:bg-muted/40 disabled:opacity-40"
              >
                Anterior
              </button>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="rounded px-2 py-1 text-xs text-muted-foreground hover:bg-muted/40 disabled:opacity-40"
              >
                Próximo
              </button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
