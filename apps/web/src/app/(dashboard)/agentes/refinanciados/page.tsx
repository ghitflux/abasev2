"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";

import type { PaginatedResponse, RefinanciamentoItem } from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import {
  formatCurrency,
  formatDateTime,
  formatMonthYear,
} from "@/lib/formatters";
import { maskCPFCNPJ } from "@/lib/masks";
import StatusBadge from "@/components/custom/status-badge";
import DataTable, { type DataTableColumn } from "@/components/shared/data-table";
import { SummaryCardSkeleton } from "@/components/shared/page-skeletons";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export default function AgenteRefinanciadosPage() {
  const [search, setSearch] = React.useState("");
  const [status, setStatus] = React.useState("todos");
  const [cycleKey, setCycleKey] = React.useState("");
  const [pageSize, setPageSize] = React.useState("15");
  const [page, setPage] = React.useState(1);

  const refinanciamentosQuery = useQuery({
    queryKey: ["agente-refinanciados", search, status, pageSize, page],
    queryFn: () =>
      apiFetch<PaginatedResponse<RefinanciamentoItem>>("refinanciamentos", {
        query: {
          page,
          page_size: Number(pageSize),
          search: search || undefined,
          status: status === "todos" ? undefined : status,
        },
      }),
  });

  const rows = React.useMemo(() => {
    const items = refinanciamentosQuery.data?.results ?? [];
    if (!cycleKey.trim()) return items;
    return items.filter((item) => item.ciclo_key.includes(cycleKey.trim()));
  }, [cycleKey, refinanciamentosQuery.data?.results]);

  const resumo = React.useMemo(() => {
    const base = refinanciamentosQuery.data?.results ?? [];
    return {
      total: refinanciamentosQuery.data?.count ?? 0,
      concluidos: base.filter((item) => item.status === "concluido" || item.status === "efetivado").length,
      falharam: base.filter((item) => item.status === "bloqueado").length,
      revertidos: base.filter((item) => item.status === "revertido").length,
    };
  }, [refinanciamentosQuery.data]);

  const columns = React.useMemo<DataTableColumn<RefinanciamentoItem>[]>(
    () => [
      {
        id: "contrato",
        header: "Contrato",
        cell: (row) => (
          <div>
            <p className="font-mono text-xs">{row.contrato_codigo}</p>
            <p className="text-xs text-muted-foreground">{maskCPFCNPJ(row.cpf_cnpj)}</p>
          </div>
        ),
      },
      {
        id: "ciclo",
        header: "Ciclo",
        cell: (row) => row.ciclo_key || "N/I",
      },
      {
        id: "refs",
        header: "Refs",
        cell: (row) => (
          <div className="space-y-1">
            {row.referencias.map((referencia) => (
              <p key={referencia} className="text-sm">
                {formatMonthYear(referencia)}
              </p>
            ))}
          </div>
        ),
      },
      {
        id: "executado",
        header: "Executado em",
        cell: (row) => formatDateTime(row.executado_em, "N/I"),
      },
      {
        id: "status",
        header: "Status",
        cell: (row) => <StatusBadge status={row.status} />,
      },
      {
        id: "repasse",
        header: "Repasse Agente",
        cell: (row) => (
          <span className="font-medium text-emerald-400">
            {formatCurrency(row.repasse_agente)}
          </span>
        ),
      },
      {
        id: "comprovantes",
        header: "Comprovantes",
        cell: (row) => (
          <div className="space-y-2">
            <Badge className="rounded-full bg-sky-500/15 text-sky-200">
              {row.comprovantes.length} anexo(s)
            </Badge>
            <div className="flex flex-wrap gap-2">
              {row.comprovantes.map((comprovante) => (
                <Button key={comprovante.id} size="sm" variant="outline" asChild>
                  <a href={comprovante.arquivo} target="_blank" rel="noreferrer">
                    Ver {comprovante.papel}
                  </a>
                </Button>
              ))}
            </div>
          </div>
        ),
      },
    ],
    [],
  );

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-4">
        {refinanciamentosQuery.isLoading && !refinanciamentosQuery.data ? (
          Array.from({ length: 4 }).map((_, index) => <SummaryCardSkeleton key={index} />)
        ) : (
          <>
            <ResumoCard label="Total" value={resumo.total} />
            <ResumoCard label="Concluídos" value={resumo.concluidos} />
            <ResumoCard label="Falharam" value={resumo.falharam} />
            <ResumoCard label="Revertidos" value={resumo.revertidos} />
          </>
        )}
      </section>

      <section className="grid gap-3 rounded-[1.75rem] border border-border/60 bg-card/50 p-4 xl:grid-cols-[minmax(0,1fr)_180px_minmax(0,1fr)_160px_auto_auto]">
        <Input
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
            setPage(1);
          }}
          placeholder="Buscar por nome, CPF, contrato ou ciclo..."
          className="rounded-2xl border-border/60 bg-card/60"
        />
        <Select value={status} onValueChange={setStatus}>
          <SelectTrigger className="rounded-2xl bg-card/60">
            <SelectValue placeholder="Todos status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="todos">Todos status</SelectItem>
            <SelectItem value="concluido">Concluído</SelectItem>
            <SelectItem value="efetivado">Efetivado</SelectItem>
            <SelectItem value="revertido">Revertido</SelectItem>
          </SelectContent>
        </Select>
        <Input
          value={cycleKey}
          onChange={(event) => setCycleKey(event.target.value)}
          placeholder="cycle_key (ex: 2026-03|2026-04|2026-05)"
          className="rounded-2xl border-border/60 bg-card/60"
        />
        <Select value={pageSize} onValueChange={setPageSize}>
          <SelectTrigger className="rounded-2xl bg-card/60">
            <SelectValue placeholder="15" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="15">15 / página</SelectItem>
            <SelectItem value="30">30 / página</SelectItem>
            <SelectItem value="50">50 / página</SelectItem>
          </SelectContent>
        </Select>
        <Button onClick={() => setPage(1)}>Aplicar</Button>
        <Button
          variant="outline"
          onClick={() => {
            setSearch("");
            setStatus("todos");
            setCycleKey("");
            setPage(1);
          }}
        >
          Limpar
        </Button>
      </section>

      <DataTable
        data={rows}
        columns={columns}
        currentPage={page}
        totalPages={Math.max(1, Math.ceil((refinanciamentosQuery.data?.count ?? 0) / Number(pageSize)))}
        onPageChange={setPage}
        emptyMessage="Nenhum refinanciamento encontrado."
        loading={refinanciamentosQuery.isLoading}
        skeletonRows={6}
      />
    </div>
  );
}

function ResumoCard({ label, value }: { label: string; value: number }) {
  return (
    <Card className="rounded-[1.75rem] border-border/60 bg-card/70">
      <CardContent className="space-y-2 p-6">
        <p className="text-sm text-muted-foreground">{label}</p>
        <p className="text-3xl font-semibold">{value.toLocaleString("pt-BR")}</p>
      </CardContent>
    </Card>
  );
}
