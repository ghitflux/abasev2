"use client";

import * as React from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LockIcon, PrinterIcon } from "lucide-react";
import { toast } from "sonner";

import type { PaginatedResponse, RefinanciamentoItem } from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import { formatMonthYear } from "@/lib/formatters";
import { maskCPFCNPJ } from "@/lib/masks";
import StatusBadge from "@/components/custom/status-badge";
import DataTable, { type DataTableColumn } from "@/components/shared/data-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";

type DialogState =
  | { mode: "aprovar"; item: RefinanciamentoItem }
  | { mode: "bloquear"; item: RefinanciamentoItem }
  | null;

export default function CoordenacaoRefinanciamentoPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = React.useState(1);
  const [search, setSearch] = React.useState("");
  const [year, setYear] = React.useState(String(new Date().getFullYear()));
  const [dialogState, setDialogState] = React.useState<DialogState>(null);
  const [motivo, setMotivo] = React.useState("");

  const refinanciamentoQuery = useQuery({
    queryKey: ["coordenacao-refinanciamento", page, search, year],
    queryFn: () =>
      apiFetch<PaginatedResponse<RefinanciamentoItem>>("coordenacao/refinanciamento", {
        query: {
          page,
          page_size: 20,
          search: search || undefined,
          year,
        },
      }),
  });

  const actionMutation = useMutation({
    mutationFn: async ({
      id,
      action,
      body,
    }: {
      id: number;
      action: "aprovar" | "bloquear";
      body?: Record<string, string>;
    }) =>
      apiFetch<RefinanciamentoItem>(`refinanciamentos/${id}/${action}`, {
        method: "POST",
        body,
      }),
    onSuccess: () => {
      toast.success("Ação de coordenação concluída.");
      setDialogState(null);
      setMotivo("");
      void queryClient.invalidateQueries({ queryKey: ["coordenacao-refinanciamento"] });
      void queryClient.invalidateQueries({ queryKey: ["coordenacao-refinanciados"] });
      void queryClient.invalidateQueries({ queryKey: ["agente-refinanciados"] });
      void queryClient.invalidateQueries({ queryKey: ["tesouraria-refinanciamentos"] });
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Falha ao processar refinanciamento.");
    },
  });

  const rows = refinanciamentoQuery.data?.results ?? [];
  const aptos = rows.filter((item) => item.status === "pendente_apto").length;
  const totalCount = refinanciamentoQuery.data?.count ?? 0;

  const columns = React.useMemo<DataTableColumn<RefinanciamentoItem>[]>(
    () => [
      {
        id: "agente",
        header: "Agente",
        cell: (row) => row.agente?.full_name ?? "—",
      },
      {
        id: "associado",
        header: "Associado",
        cell: (row) => row.associado_nome,
      },
      {
        id: "cpf",
        header: "CPF/CNPJ",
        cell: (row) => maskCPFCNPJ(row.cpf_cnpj),
      },
      {
        id: "jan",
        header: "JAN/FEV/MAR",
        cell: (row) => (
          <div className="space-y-1">
            {row.referencias.map((referencia) => (
              <p key={referencia}>{formatMonthYear(referencia)}</p>
            ))}
          </div>
        ),
      },
      {
        id: "mensalidades",
        header: "Mensalidades",
        cell: (row) => `${row.mensalidades_pagas}/${row.mensalidades_total}`,
      },
      {
        id: "refin",
        header: "Refinanciamento",
        cell: (row) => (
          <Badge className="rounded-full bg-sky-500/15 text-sky-200">
            {row.refinanciamento_numero}
          </Badge>
        ),
      },
      {
        id: "acao",
        header: "Ação",
        cell: (row) =>
          row.status === "bloqueado" ? (
            <div className="space-y-2">
              <StatusBadge status="bloqueado" />
              <p className="text-xs text-muted-foreground">{row.motivo_bloqueio || "Sem motivo registrado."}</p>
            </div>
          ) : (
            <div className="flex flex-wrap gap-2">
              <Button size="sm" onClick={() => setDialogState({ mode: "aprovar", item: row })}>
                pendente — APTO
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="border-slate-500/40 text-slate-200"
                onClick={() => setDialogState({ mode: "bloquear", item: row })}
              >
                <LockIcon className="size-4" />
                Bloquear
              </Button>
            </div>
          ),
      },
    ],
    [],
  );

  return (
    <div className="space-y-6">
      <section className="rounded-[1.75rem] border border-border/60 bg-card/70 p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-2">
            <div className="flex flex-wrap gap-2">
              <Button asChild variant="outline">
                <Link href="/coordenacao/refinanciados">Refinanciados</Link>
              </Button>
              <Button asChild>
                <Link href="/coordenacao/refinanciamento">Refinanciamento</Link>
              </Button>
            </div>
            <h1 className="text-3xl font-semibold">Refinanciamento em aprovação</h1>
            <p className="text-sm text-muted-foreground">
              Condição: solicitação pendente + 3 mensalidades livres reais. Total: {totalCount} | Aptos: {aptos}
            </p>
          </div>
          <Button variant="outline" onClick={() => window.print()}>
            <PrinterIcon className="size-4" />
            Imprimir / PDF
          </Button>
        </div>
      </section>

      <section className="grid gap-3 rounded-[1.75rem] border border-border/60 bg-card/50 p-4 lg:grid-cols-[160px_minmax(0,1fr)_auto]">
        <Input
          value={year}
          onChange={(event) => {
            setYear(event.target.value);
            setPage(1);
          }}
          placeholder="Ano"
          className="rounded-2xl border-border/60 bg-card/60"
        />
        <Input
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
            setPage(1);
          }}
          placeholder="Buscar por associado, CPF ou agente"
          className="rounded-2xl border-border/60 bg-card/60"
        />
        <Button onClick={() => setPage(1)}>Aplicar</Button>
      </section>

      {refinanciamentoQuery.isLoading ? (
        <div className="flex items-center gap-3 rounded-[1.75rem] border border-border/60 bg-card/60 px-6 py-8 text-sm text-muted-foreground">
          <Spinner />
          Carregando refinanciamentos pendentes...
        </div>
      ) : (
        <DataTable
          data={rows}
          columns={columns}
          currentPage={page}
          totalPages={Math.max(1, Math.ceil(totalCount / 20))}
          onPageChange={setPage}
          emptyMessage="Nenhuma solicitação pendente para coordenação."
        />
      )}

      <Dialog open={!!dialogState} onOpenChange={(open) => !open && setDialogState(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {dialogState?.mode === "aprovar" ? "Aprovar refinanciamento" : "Bloquear refinanciamento"}
            </DialogTitle>
            <DialogDescription>
              {dialogState?.mode === "aprovar"
                ? "A aprovação ativa o novo ciclo do associado imediatamente."
                : "Informe o motivo do bloqueio para auditoria."}
            </DialogDescription>
          </DialogHeader>

          {dialogState?.mode === "bloquear" ? (
            <Textarea
              value={motivo}
              onChange={(event) => setMotivo(event.target.value)}
              placeholder="Motivo do bloqueio..."
              className="min-h-32"
            />
          ) : null}

          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogState(null)}>
              Cancelar
            </Button>
            <Button
              onClick={() => {
                if (!dialogState) return;
                if (dialogState.mode === "bloquear" && !motivo.trim()) {
                  toast.error("Informe um motivo para bloquear.");
                  return;
                }
                actionMutation.mutate({
                  id: dialogState.item.id,
                  action: dialogState.mode,
                  body: dialogState.mode === "bloquear" ? { motivo } : undefined,
                });
              }}
              disabled={actionMutation.isPending}
            >
              Confirmar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
