"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { FileSearchIcon, PrinterIcon } from "lucide-react";

import type { PaginatedResponse, RefinanciamentoItem } from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import { formatDateTime, formatMonthYear } from "@/lib/formatters";
import { maskCPFCNPJ } from "@/lib/masks";
import StatusBadge from "@/components/custom/status-badge";
import DataTable, { type DataTableColumn } from "@/components/shared/data-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";

export default function CoordenacaoRefinanciadosPage() {
  const [page, setPage] = React.useState(1);
  const [search, setSearch] = React.useState("");
  const [year, setYear] = React.useState(String(new Date().getFullYear()));
  const [auditTarget, setAuditTarget] = React.useState<RefinanciamentoItem | null>(null);

  const refinanciadosQuery = useQuery({
    queryKey: ["coordenacao-refinanciados", page, search, year],
    queryFn: () =>
      apiFetch<PaginatedResponse<RefinanciamentoItem>>("coordenacao/refinanciados", {
        query: {
          page,
          page_size: 20,
          search: search || undefined,
          year,
        },
      }),
  });

  const rows = refinanciadosQuery.data?.results ?? [];
  const totalCount = refinanciadosQuery.data?.count ?? 0;

  const columns = React.useMemo<DataTableColumn<RefinanciamentoItem>[]>(
    () => [
      {
        id: "seq",
        header: "#",
        cell: (row) => (
          <span className="font-mono text-xs">
            {rows.findIndex((item) => item.id === row.id) + 1 + (page - 1) * 20}
          </span>
        ),
      },
      {
        id: "associado",
        header: "Associado",
        cell: (row) => (
          <div>
            <p className="font-semibold tracking-[0.08em]">{row.associado_nome.toUpperCase()}</p>
            <p className="text-xs text-muted-foreground">{row.agente?.full_name ?? "Sem agente"}</p>
          </div>
        ),
      },
      {
        id: "cpf",
        header: "CPF/CNPJ",
        cell: (row) => maskCPFCNPJ(row.cpf_cnpj),
      },
      {
        id: "ref1",
        header: "1ª",
        cell: (row) => formatMonthYear(row.referencias[0]),
      },
      {
        id: "ref2",
        header: "2ª",
        cell: (row) => formatMonthYear(row.referencias[1]),
      },
      {
        id: "ref3",
        header: "3ª",
        cell: (row) => formatMonthYear(row.referencias[2]),
      },
      {
        id: "data_ciclo",
        header: "Data do Ciclo",
        cell: (row) => formatDateTime(row.created_at),
      },
      {
        id: "mensalidades",
        header: "Mensalidades",
        cell: (row) => `${row.mensalidades_pagas}/${row.mensalidades_total}`,
      },
      {
        id: "refinanciamento",
        header: "Refinanciamento",
        cell: (row) => (
          <Badge className="rounded-full bg-emerald-500/15 text-emerald-200">
            {row.refinanciamento_numero}
          </Badge>
        ),
      },
      {
        id: "status",
        header: "Status",
        cell: (row) => <StatusBadge status={row.status} />,
      },
      {
        id: "auditoria",
        header: "Auditoria",
        cell: (row) => (
          <Button size="sm" variant="outline" onClick={() => setAuditTarget(row)}>
            <FileSearchIcon className="size-4" />
            Ver
          </Button>
        ),
      },
    ],
    [page, rows],
  );

  return (
    <div className="space-y-6">
      <section className="rounded-[1.75rem] border border-border/60 bg-card/70 p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-2">
            <div className="flex flex-wrap gap-2">
              <Button asChild>
                <Link href="/coordenacao/refinanciados">Refinanciados</Link>
              </Button>
              <Button asChild variant="outline">
                <Link href="/coordenacao/refinanciamento">Refinanciamento</Link>
              </Button>
            </div>
            <h1 className="text-3xl font-semibold">
              Refinanciados — {year}-01|{year}-02|{year}-03
            </h1>
            <p className="text-sm text-muted-foreground">
              Modo: somente refinanciados. Total: {totalCount} | Filtrados: {totalCount} | Exibindo: {rows.length}
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
          placeholder="Buscar por nome ou CPF/CI"
          className="rounded-2xl border-border/60 bg-card/60"
        />
        <Button onClick={() => setPage(1)}>Aplicar</Button>
      </section>

      {refinanciadosQuery.isLoading ? (
        <div className="flex items-center gap-3 rounded-[1.75rem] border border-border/60 bg-card/60 px-6 py-8 text-sm text-muted-foreground">
          <Spinner />
          Carregando refinanciados...
        </div>
      ) : (
        <DataTable
          data={rows}
          columns={columns}
          currentPage={page}
          totalPages={Math.max(1, Math.ceil(totalCount / 20))}
          onPageChange={setPage}
          emptyMessage="Nenhum refinanciado encontrado."
        />
      )}

      <Dialog open={!!auditTarget} onOpenChange={(open) => !open && setAuditTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Auditoria do refinanciamento</DialogTitle>
            <DialogDescription>
              Linha de auditoria consolidada do fluxo de coordenação e tesouraria.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-3 rounded-2xl border border-border/60 bg-card/60 p-4 text-sm">
            <InfoLine label="Contrato" value={auditTarget?.contrato_codigo} />
            <InfoLine label="Solicitado por" value={auditTarget?.auditoria.solicitado_por?.full_name} />
            <InfoLine label="Aprovado por" value={auditTarget?.auditoria.aprovado_por?.full_name} />
            <InfoLine label="Efetivado por" value={auditTarget?.auditoria.efetivado_por?.full_name} />
            <InfoLine label="Observação" value={auditTarget?.auditoria.observacao || "—"} />
            <InfoLine label="Motivo de bloqueio" value={auditTarget?.auditoria.motivo_bloqueio || "—"} />
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function InfoLine({ label, value }: { label: string; value?: string }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium">{value || "—"}</span>
    </div>
  );
}
