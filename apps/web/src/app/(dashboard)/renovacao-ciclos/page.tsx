"use client";

import * as React from "react";
import { useDeferredValue } from "react";
import { FileDownIcon } from "lucide-react";
import { toast } from "sonner";

import StatusBadge from "@/components/custom/status-badge";
import DataTable, { type DataTableColumn } from "@/components/shared/data-table";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  useV1RenovacaoCiclosExportarRetrieve,
  useV1RenovacaoCiclosList,
  useV1RenovacaoCiclosMesesList,
  useV1RenovacaoCiclosVisaoMensalRetrieve,
} from "@/gen";
import type { RenovacaoCicloItem } from "@/gen/models";
import { formatCurrency, formatDate } from "@/lib/formatters";
import { maskCPFCNPJ } from "@/lib/masks";

function totalPages(count?: number, pageSize = 10) {
  return Math.max(1, Math.ceil((count ?? 0) / pageSize));
}

const STATUS_OPTIONS = [
  { value: "todos", label: "Todos os status" },
  { value: "ciclo_renovado", label: "Ciclo renovado" },
  { value: "apto_a_renovar", label: "Apto a renovar" },
  { value: "em_aberto", label: "Em aberto" },
  { value: "ciclo_iniciado", label: "Ciclo iniciado" },
  { value: "inadimplente", label: "Inadimplente" },
];

export default function RenovacaoCiclosPage() {
  const [page, setPage] = React.useState(1);
  const [search, setSearch] = React.useState("");
  const [selectedStatus, setSelectedStatus] = React.useState("todos");
  const deferredSearch = useDeferredValue(search);

  const monthsQuery = useV1RenovacaoCiclosMesesList();
  const [selectedCompetencia, setSelectedCompetencia] = React.useState("");

  React.useEffect(() => {
    if (!selectedCompetencia && monthsQuery.data?.[0]?.id) {
      setSelectedCompetencia(monthsQuery.data[0].id);
    }
  }, [monthsQuery.data, selectedCompetencia]);

  const filters = {
    competencia: selectedCompetencia || undefined,
    page,
    page_size: 10,
    search: deferredSearch || undefined,
    status: selectedStatus === "todos" ? undefined : selectedStatus,
  };

  const resumoQuery = useV1RenovacaoCiclosVisaoMensalRetrieve(filters, {
    query: { enabled: Boolean(selectedCompetencia) },
  });
  const listQuery = useV1RenovacaoCiclosList(filters, {
    query: { enabled: Boolean(selectedCompetencia) },
  });
  const exportQuery = useV1RenovacaoCiclosExportarRetrieve(filters, {
    query: { enabled: false },
  });

  const columns: DataTableColumn<RenovacaoCicloItem>[] = [
    {
      id: "nome_associado",
      header: "Associado",
      cell: (row) => (
        <div>
          <p className="font-medium text-foreground">{row.nome_associado}</p>
          <p className="text-xs text-muted-foreground">{row.contrato_codigo}</p>
        </div>
      ),
    },
    {
      id: "cpf_cnpj",
      header: "CPF",
      cell: (row) => maskCPFCNPJ(row.cpf_cnpj),
    },
    {
      id: "orgao_pagto_nome",
      header: "Órgão pagador",
      cell: (row) => row.orgao_pagto_nome || row.orgao_publico || "-",
    },
    {
      id: "parcelas_pagas",
      header: "Parcial",
      cell: (row) => `${row.parcelas_pagas}/${row.parcelas_total}`,
    },
    {
      id: "valor_parcela",
      header: "Mensalidade",
      cell: (row) => formatCurrency(row.valor_parcela),
    },
    {
      id: "status_visual",
      header: "Status",
      cell: (row) => <StatusBadge status={row.status_visual} />,
    },
  ];

  async function handleExport() {
    const result = await exportQuery.refetch();
    if (!result.data) {
      toast.error("Não foi possível montar a exportação.");
      return;
    }
    const blob = new Blob([JSON.stringify(result.data, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `renovacao-ciclos-${selectedCompetencia ?? "atual"}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-6">
      <Card className="border-border/60 bg-card/80">
        <CardHeader className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <CardTitle className="text-2xl">Renovação de Ciclos</CardTitle>
            <CardDescription>
              Visão mensal alinhada à reconciliação do arquivo retorno, com meses disponíveis,
              status do ciclo e exportação administrativa.
            </CardDescription>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <Select value={selectedCompetencia} onValueChange={(value) => {
              setSelectedCompetencia(value);
              setPage(1);
            }}>
              <SelectTrigger className="w-full min-w-44">
                <SelectValue placeholder="Competência" />
              </SelectTrigger>
              <SelectContent>
                {monthsQuery.data?.map((month) => (
                  <SelectItem key={month.id} value={month.id}>
                    {month.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={selectedStatus} onValueChange={(value) => {
              setSelectedStatus(value);
              setPage(1);
            }}>
              <SelectTrigger className="w-full min-w-44">
                <SelectValue placeholder="Status" />
              </SelectTrigger>
              <SelectContent>
                {STATUS_OPTIONS.map((status) => (
                  <SelectItem key={status.value} value={status.value}>
                    {status.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Input
              placeholder="Buscar associado ou CPF"
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                setPage(1);
              }}
            />
          </div>
        </CardHeader>
      </Card>

      <div className="grid gap-4 md:grid-cols-5">
        <Card className="border-border/60 bg-card/80">
          <CardHeader>
            <CardDescription>Total</CardDescription>
            <CardTitle className="text-3xl">{resumoQuery.data?.total_associados ?? 0}</CardTitle>
          </CardHeader>
        </Card>
        <Card className="border-border/60 bg-card/80">
          <CardHeader>
            <CardDescription>Ciclo renovado</CardDescription>
            <CardTitle className="text-3xl">{resumoQuery.data?.ciclo_renovado ?? 0}</CardTitle>
          </CardHeader>
        </Card>
        <Card className="border-border/60 bg-card/80">
          <CardHeader>
            <CardDescription>Apto a renovar</CardDescription>
            <CardTitle className="text-3xl">{resumoQuery.data?.apto_a_renovar ?? 0}</CardTitle>
          </CardHeader>
        </Card>
        <Card className="border-border/60 bg-card/80">
          <CardHeader>
            <CardDescription>Em aberto</CardDescription>
            <CardTitle className="text-3xl">{resumoQuery.data?.em_aberto ?? 0}</CardTitle>
          </CardHeader>
        </Card>
        <Card className="border-border/60 bg-card/80">
          <CardHeader>
            <CardDescription>Inadimplentes</CardDescription>
            <CardTitle className="text-3xl">{resumoQuery.data?.inadimplente ?? 0}</CardTitle>
          </CardHeader>
        </Card>
      </div>

      <Card className="border-border/60 bg-card/80">
        <CardHeader className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <CardTitle>Detalhamento mensal</CardTitle>
            <CardDescription>
              Status do ciclo, órgão pagador, importação conciliada e abertura de novos ciclos.
            </CardDescription>
          </div>
          <Button variant="outline" onClick={handleExport} disabled={exportQuery.isFetching || !selectedCompetencia}>
            <FileDownIcon className="mr-2 size-4" />
            Exportar visão
          </Button>
        </CardHeader>
        <CardContent>
          <DataTable
            columns={columns}
            data={listQuery.data?.results ?? []}
            currentPage={page}
            totalPages={totalPages(listQuery.data?.count, 10)}
            onPageChange={setPage}
            emptyMessage="Nenhum ciclo encontrado para a competência selecionada."
            renderExpanded={(row) => (
              <div className="grid gap-3 md:grid-cols-4">
                <div>
                  <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">Status ETIPI</p>
                  <p className="mt-2 font-medium">{row.status_codigo_etipi || "-"}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">Resultado importação</p>
                  <div className="mt-2">
                    <StatusBadge status={row.resultado_importacao} />
                  </div>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">Pagamento</p>
                  <p className="mt-2 font-medium">{formatDate(row.data_pagamento)}</p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">Ciclo</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {row.gerou_encerramento ? <StatusBadge status="ciclo_renovado" /> : null}
                    {row.gerou_novo_ciclo ? <StatusBadge status="ciclo_iniciado" /> : null}
                    {!row.gerou_encerramento && !row.gerou_novo_ciclo ? (
                      <StatusBadge status={row.status_ciclo} />
                    ) : null}
                  </div>
                </div>
              </div>
            )}
          />
        </CardContent>
      </Card>
    </div>
  );
}
