"use client";

import * as React from "react";

import type { DryRunItem } from "@/gen/models/DryRunResultado";
import CopySnippet from "@/components/shared/copy-snippet";
import StatusBadge from "@/components/custom/status-badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { formatCurrency } from "@/lib/formatters";
import { maskCPFCNPJ } from "@/lib/masks";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  items: DryRunItem[];
};

const PAGE_SIZE = 15;

export default function DryRunDetailDialog({ open, onOpenChange, title, items }: Props) {
  const [page, setPage] = React.useState(1);

  const totalPages = Math.max(1, Math.ceil(items.length / PAGE_SIZE));
  const pageItems = items.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  React.useEffect(() => {
    setPage(1);
  }, [open]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[85vh] max-w-4xl flex-col gap-0 p-0">
        <DialogHeader className="border-b border-border/60 px-6 py-4">
          <DialogTitle className="text-base">{title}</DialogTitle>
          <p className="text-xs text-muted-foreground">
            {items.length} associado{items.length !== 1 ? "s" : ""}
          </p>
        </DialogHeader>

        <ScrollArea className="flex-1">
          <div className="overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/60 bg-muted/20">
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
                </tr>
              </thead>
              <tbody>
                {pageItems.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-8 text-center text-sm text-muted-foreground">
                      Nenhum registro nesta categoria.
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
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </ScrollArea>

        {totalPages > 1 && (
          <div className="flex items-center justify-between border-t border-border/60 px-6 py-3">
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
