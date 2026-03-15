"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  ChevronRightIcon,
  EyeIcon,
  FilterIcon,
  PencilIcon,
  SearchIcon,
  Users2Icon,
  UserCheckIcon,
  UserRoundSearchIcon,
  UserXIcon,
} from "lucide-react";

import type { AssociadoListItem, AssociadoMetricas, Ciclo, PaginatedResponse } from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import { formatDateValue, parseDateValue } from "@/lib/date-value";
import { formatMetricDelta, formatMonthYear } from "@/lib/formatters";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import RoleGuard from "@/components/auth/role-guard";
import DatePicker from "@/components/custom/date-picker";
import StatusBadge from "@/components/custom/status-badge";
import CopySnippet from "@/components/shared/copy-snippet";
import DataTable, { type DataTableColumn } from "@/components/shared/data-table";
import { InlinePanelSkeleton, MetricCardSkeleton } from "@/components/shared/page-skeletons";
import StatsCard from "@/components/shared/stats-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Sheet, SheetContent, SheetFooter, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

type FiltersState = {
  status: string;
  orgao_publico: string;
  data_inicio: string;
  data_fim: string;
};

function AssociadoCiclosPanel({ associadoId }: { associadoId: number }) {
  const ciclosQuery = useQuery({
    queryKey: ["associado-ciclos", associadoId],
    queryFn: () => apiFetch<Ciclo[]>(`associados/${associadoId}/ciclos`),
  });

  if (ciclosQuery.isLoading) {
    return <InlinePanelSkeleton rows={2} className="pt-2" />;
  }

  const ciclos = ciclosQuery.data ?? [];
  if (!ciclos.length) {
    return <p className="text-sm text-muted-foreground">Nenhum ciclo encontrado.</p>;
  }

  return (
    <Tabs defaultValue={String(ciclos[0]?.id)}>
      <TabsList variant="line">
        {ciclos.map((ciclo) => (
          <TabsTrigger key={ciclo.id} value={String(ciclo.id)}>
            <div className="flex flex-col items-start">
              <span>Ciclo {ciclo.numero}</span>
              <span className="text-[10px] font-mono text-muted-foreground">
                {ciclo.contrato_codigo}
              </span>
            </div>
          </TabsTrigger>
        ))}
      </TabsList>
      {ciclos.map((ciclo) => (
        <TabsContent key={ciclo.id} value={String(ciclo.id)} className="pt-4">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-foreground">{ciclo.contrato_codigo}</p>
              <p className="text-sm text-muted-foreground">
                Referências de {formatMonthYear(ciclo.data_inicio)} até {formatMonthYear(ciclo.data_fim)}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <StatusBadge status={ciclo.contrato_status} label={ciclo.contrato_status} />
              <StatusBadge status={ciclo.status} />
            </div>
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            {ciclo.parcelas.map((parcela) => (
              <div key={parcela.id} className="rounded-2xl border border-border/60 bg-background/70 p-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="font-medium">Parcela {parcela.numero}/3</p>
                  <StatusBadge status={parcela.status} />
                </div>
                <p className="mt-2 text-sm text-muted-foreground">{formatMonthYear(parcela.referencia_mes)}</p>
              </div>
            ))}
          </div>
        </TabsContent>
      ))}
    </Tabs>
  );
}

function AssociadosPageContent() {
  const [page, setPage] = React.useState(1);
  const [search, setSearch] = React.useState("");
  const [filters, setFilters] = React.useState<FiltersState>({
    status: "",
    orgao_publico: "",
    data_inicio: "",
    data_fim: "",
  });
  const debouncedSearch = useDebouncedValue(search, 300);

  const metricasQuery = useQuery({
    queryKey: ["associados-metricas"],
    queryFn: () => apiFetch<AssociadoMetricas>("associados/metricas"),
  });

  const associadosQuery = useQuery({
    queryKey: ["associados", page, debouncedSearch, filters],
    queryFn: () =>
      apiFetch<PaginatedResponse<AssociadoListItem>>("associados", {
        query: {
          page,
          page_size: 20,
          search: debouncedSearch,
          status: filters.status || undefined,
          orgao_publico: filters.orgao_publico || undefined,
          data_cadastro_inicio: filters.data_inicio || undefined,
          data_cadastro_fim: filters.data_fim || undefined,
        },
      }),
  });

  const metricas = metricasQuery.data;
  const associados = associadosQuery.data?.results ?? [];
  const totalPages = Math.max(1, Math.ceil((associadosQuery.data?.count ?? 0) / 20));

  const columns = React.useMemo<DataTableColumn<AssociadoListItem>[]>(
    () => [
      {
        id: "nome",
        header: "Nome",
        accessor: "nome_completo",
        sortable: true,
        cell: (row) => (
          <div className="flex items-center gap-3">
            <ChevronRightIcon className="size-4 text-muted-foreground" />
            <div>
              <p className="font-medium">{row.nome_completo}</p>
              <p className="text-xs text-muted-foreground">Clique na linha para ver ciclos</p>
            </div>
          </div>
        ),
      },
      {
        id: "matricula",
        header: "Matrícula do Servidor",
        cell: (row) => (
          <CopySnippet label="Matrícula do Servidor" value={row.matricula_orgao || row.matricula} mono inline />
        ),
      },
      {
        id: "cpf_cnpj",
        header: "CPF/CNPJ",
        cell: (row) => <CopySnippet label="CPF" value={row.cpf_cnpj} mono inline />,
      },
      {
        id: "ciclos",
        header: "Ciclos",
        cell: (row) => (
          <div className="flex flex-wrap gap-2">
            <Badge className="rounded-full bg-emerald-500/15 text-emerald-200">{row.ciclos_abertos} abertos</Badge>
            <Badge className="rounded-full bg-slate-500/15 text-slate-200">{row.ciclos_fechados} fechados</Badge>
          </div>
        ),
      },
      {
        id: "agente",
        header: "Agente",
        cell: (row) => row.agente?.full_name ?? "-",
      },
      {
        id: "status",
        header: "Status",
        accessor: "status",
        cell: (row) => <StatusBadge status={row.status} />,
      },
      {
        id: "acoes",
        header: "Ações",
        cell: (row) => (
          <div className="flex items-center gap-2">
            <Button variant="outline" size="icon-sm" asChild>
              <Link href={`/associados/${row.id}`}>
                <EyeIcon className="size-4" />
              </Link>
            </Button>
            <Button variant="outline" size="icon-sm" asChild>
              <Link href={`/associados/${row.id}/editar`}>
                <PencilIcon className="size-4" />
              </Link>
            </Button>
          </div>
        ),
      },
    ],
    [],
  );

  return (
    <div className="space-y-8">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {metricasQuery.isLoading && !metricas ? (
          Array.from({ length: 4 }).map((_, index) => <MetricCardSkeleton key={index} />)
        ) : (
          <>
            <StatsCard
              title="Total de Associados"
              value={(metricas?.total.count ?? 0).toLocaleString("pt-BR")}
              delta={formatMetricDelta(metricas?.total.variacao_percentual ?? 0)}
              tone={(metricas?.total.variacao_percentual ?? 0) >= 0 ? "positive" : "warning"}
              icon={Users2Icon}
            />
            <StatsCard
              title="Associados Ativos"
              value={(metricas?.ativos.count ?? 0).toLocaleString("pt-BR")}
              delta={formatMetricDelta(metricas?.ativos.variacao_percentual ?? 0)}
              tone={(metricas?.ativos.variacao_percentual ?? 0) >= 0 ? "positive" : "warning"}
              icon={UserCheckIcon}
            />
            <StatsCard
              title="Em Análise"
              value={(metricas?.em_analise.count ?? 0).toLocaleString("pt-BR")}
              delta={formatMetricDelta(metricas?.em_analise.variacao_percentual ?? 0)}
              tone={(metricas?.em_analise.variacao_percentual ?? 0) >= 0 ? "positive" : "warning"}
              icon={UserRoundSearchIcon}
            />
            <StatsCard
              title="Inativos"
              value={(metricas?.inativos.count ?? 0).toLocaleString("pt-BR")}
              delta={formatMetricDelta(metricas?.inativos.variacao_percentual ?? 0)}
              tone={(metricas?.inativos.variacao_percentual ?? 0) >= 0 ? "positive" : "warning"}
              icon={UserXIcon}
            />
          </>
        )}
      </section>

      <section className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="relative w-full max-w-xl">
          <SearchIcon className="pointer-events-none absolute top-1/2 left-4 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
            placeholder="Buscar associados..."
            className="rounded-2xl border-border/60 bg-card/60 pl-11"
          />
        </div>
        <div className="flex flex-wrap gap-3">
          <Sheet>
            <SheetTrigger asChild>
              <Button variant="outline">
                <FilterIcon className="size-4" />
                Filtros avançados
              </Button>
            </SheetTrigger>
            <SheetContent className="w-full border-l border-border/60 sm:max-w-md">
              <SheetHeader>
                <SheetTitle>Filtros avançados</SheetTitle>
              </SheetHeader>
              <div className="space-y-5 p-4">
                <div className="space-y-2">
                  <p className="text-sm font-medium">Status</p>
                  <Input
                    value={filters.status}
                    onChange={(event) => setFilters((current) => ({ ...current, status: event.target.value }))}
                    placeholder="ativo, em_analise..."
                    className="rounded-xl bg-card/60"
                  />
                </div>
                <div className="space-y-2">
                  <p className="text-sm font-medium">Órgão público</p>
                  <Input
                    value={filters.orgao_publico}
                    onChange={(event) => setFilters((current) => ({ ...current, orgao_publico: event.target.value }))}
                    placeholder="Secretaria..."
                    className="rounded-xl bg-card/60"
                  />
                </div>
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <p className="text-sm font-medium">Data inicial</p>
                    <DatePicker
                      value={parseDateValue(filters.data_inicio)}
                      onChange={(value) =>
                        setFilters((current) => ({
                          ...current,
                          data_inicio: formatDateValue(value),
                        }))
                      }
                      className="rounded-xl"
                    />
                  </div>
                  <div className="space-y-2">
                    <p className="text-sm font-medium">Data final</p>
                    <DatePicker
                      value={parseDateValue(filters.data_fim)}
                      onChange={(value) =>
                        setFilters((current) => ({
                          ...current,
                          data_fim: formatDateValue(value),
                        }))
                      }
                      className="rounded-xl"
                    />
                  </div>
                </div>
              </div>
              <SheetFooter>
                <Button
                  variant="outline"
                  onClick={() => {
                    setFilters({ status: "", orgao_publico: "", data_inicio: "", data_fim: "" });
                    setPage(1);
                  }}
                >
                  Limpar
                </Button>
                <Button onClick={() => setPage(1)}>Aplicar</Button>
              </SheetFooter>
            </SheetContent>
          </Sheet>
          <Button asChild>
            <Link href="/associados/novo">+ Novo Associado</Link>
          </Button>
        </div>
      </section>

      <DataTable
        data={associados}
        columns={columns}
        currentPage={page}
        totalPages={totalPages}
        onPageChange={setPage}
        emptyMessage="Nenhum associado encontrado para os filtros informados."
        renderExpanded={(row) => <AssociadoCiclosPanel associadoId={row.id} />}
        loading={associadosQuery.isLoading}
        skeletonRows={6}
      />
    </div>
  );
}

export default function AssociadosPage() {
  return (
    <RoleGuard allow={["ADMIN"]}>
      <AssociadosPageContent />
    </RoleGuard>
  );
}
