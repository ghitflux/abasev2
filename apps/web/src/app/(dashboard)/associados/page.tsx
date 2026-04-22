"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  ChevronDownIcon,
  ChevronRightIcon,
  EyeIcon,
  FilterIcon,
  HandCoinsIcon,
  PencilIcon,
  SearchIcon,
  UserCheckIcon,
  UserRoundSearchIcon,
  UserXIcon,
  Users2Icon,
} from "lucide-react";

import type {
  AssociadoCyclesPayload,
  AssociadoListItem,
  AssociadoMetricas,
  PaginatedResponse,
  SimpleUser,
} from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import {
  MENSALIDADE_FAIXAS,
  PARCELAS_PAGAS_FAIXAS,
} from "@/lib/associado-filter-presets";
import {
  dashboardOptionsQueryOptions,
  dashboardRetainedQueryOptions,
} from "@/lib/dashboard-query";
import { formatDateValue, parseDateValue } from "@/lib/date-value";
import { formatCurrency, formatMetricDelta, formatMonthYear } from "@/lib/formatters";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { usePermissions } from "@/hooks/use-permissions";
import RoleGuard from "@/components/auth/role-guard";
import {
  ParcelaDetalheDialog,
  type ParcelaDetailTarget,
} from "@/components/contratos/parcela-detalhe-dialog";
import DatePicker from "@/components/custom/date-picker";
import StatusBadge from "@/components/custom/status-badge";
import CopySnippet from "@/components/shared/copy-snippet";
import DashboardDetailDialog from "@/components/shared/dashboard-detail-dialog";
import DataTable, { type DataTableColumn } from "@/components/shared/data-table";
import { InlinePanelSkeleton, MetricCardSkeleton } from "@/components/shared/page-skeletons";
import StatsCard from "@/components/shared/stats-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Sheet,
  SheetContent,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

type FiltersState = {
  status: string;
  orgao_publico: string;
  data_inicio: string;
  data_fim: string;
  agente: string;
  numero_ciclos: string;
  perfil_ciclo: string;
  faixa_mensalidade: string[];
  faixa_parcelas: string[];
};

type AssociadoMetricKey = "total" | "ativos" | "em_analise" | "inativos" | "liquidados";
const ALL_AGENTS_VALUE = "todos";
const ALL_STATUS_VALUE = "todos";
const ALL_CICLOS_VALUE = "todos";
const ALL_PERFIL_CICLO_VALUE = "todos";

const STATUS_OPTIONS = [
  { value: ALL_STATUS_VALUE, label: "Todos os status" },
  { value: "ativo", label: "Ativos" },
  { value: "em_analise", label: "Em análise" },
  { value: "inativo", label: "Inativos" },
  { value: "pendente", label: "Pendentes" },
  { value: "inadimplente", label: "Inadimplentes" },
  { value: "liquidado", label: "Liquidados" },
];

const PERFIL_CICLO_OPTIONS = [
  { value: ALL_PERFIL_CICLO_VALUE, label: "Todos os perfis" },
  { value: "novo", label: "Novos" },
  { value: "renovado", label: "Renovados" },
];

const CICLO_OPTIONS = [
  { value: ALL_CICLOS_VALUE, label: "Todos os ciclos" },
  { value: "1", label: "1 ciclo" },
  { value: "2", label: "2 ciclos" },
  { value: "3", label: "3 ciclos" },
  { value: "4", label: "4 ciclos" },
  { value: "5", label: "5 ciclos" },
];

const METRIC_STATUS_QUERY: Record<AssociadoMetricKey, string | undefined> = {
  total: undefined,
  ativos: "ativo",
  em_analise: "em_analise",
  inativos: "inativo",
  liquidados: "liquidado",
};

const METRIC_META: Record<
  AssociadoMetricKey,
  {
    title: string;
    tone: "positive" | "warning" | "neutral";
    icon: typeof Users2Icon;
  }
> = {
  total: { title: "Total de Associados", tone: "neutral", icon: Users2Icon },
  ativos: { title: "Associados Ativos", tone: "positive", icon: UserCheckIcon },
  em_analise: { title: "Em Análise", tone: "warning", icon: UserRoundSearchIcon },
  inativos: { title: "Inativos", tone: "warning", icon: UserXIcon },
  liquidados: { title: "Liquidados", tone: "positive", icon: HandCoinsIcon },
};

function MultiSelectFilterField({
  label,
  placeholder,
  options,
  value,
  onChange,
}: {
  label: string;
  placeholder: string;
  options: ReadonlyArray<{ value: string; label: string }>;
  value: string[];
  onChange: React.Dispatch<React.SetStateAction<string[]>>;
}) {
  const [open, setOpen] = React.useState(false);
  const selectedOptions = options.filter((option) => value.includes(option.value));

  return (
    <div className="space-y-2">
      <p className="text-sm font-medium">{label}</p>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            variant="outline"
            className="h-11 w-full justify-between rounded-xl border-border/60 bg-card/60"
          >
            <span className="truncate text-left">
              {selectedOptions.length
                ? selectedOptions.map((option) => option.label).join(", ")
                : placeholder}
            </span>
            <ChevronDownIcon className="size-4 shrink-0 text-muted-foreground" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-[var(--radix-popover-trigger-width)] rounded-2xl border-border/60 p-3">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium">Selecione uma ou mais faixas</p>
              {value.length ? (
                <Button type="button" variant="ghost" size="sm" onClick={() => onChange([])}>
                  Limpar
                </Button>
              ) : null}
            </div>
            <div className="space-y-2">
              {options.map((option) => {
                const checked = value.includes(option.value);
                return (
                  <label
                    key={option.value}
                    className="flex cursor-pointer items-center gap-3 rounded-xl border border-border/40 px-3 py-2 hover:bg-accent/40"
                  >
                    <Checkbox
                      checked={checked}
                      onCheckedChange={(nextChecked) => {
                        onChange((current) =>
                          nextChecked
                            ? [...current, option.value]
                            : current.filter((item) => item !== option.value),
                        );
                      }}
                    />
                    <span className="text-sm">{option.label}</span>
                  </label>
                );
              })}
            </div>
          </div>
        </PopoverContent>
      </Popover>
      {selectedOptions.length ? (
        <div className="flex flex-wrap gap-2">
          {selectedOptions.map((option) => (
            <Badge
              key={option.value}
              className="rounded-full bg-primary/15 px-3 py-1 text-primary"
            >
              {option.label}
            </Badge>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function AssociadoCiclosPanel({ associadoId }: { associadoId: number }) {
  const [selectedTarget, setSelectedTarget] =
    React.useState<ParcelaDetailTarget | null>(null);
  const ciclosQuery = useQuery({
    queryKey: ["associado-ciclos", associadoId],
    queryFn: () => apiFetch<AssociadoCyclesPayload>(`associados/${associadoId}/ciclos`),
  });

  if (ciclosQuery.isLoading) {
    return <InlinePanelSkeleton rows={2} className="pt-2" />;
  }

  const payload = ciclosQuery.data;
  const ciclos = payload?.ciclos ?? [];
  const mesesNaoPagos = payload?.meses_nao_pagos ?? [];
  const parcelasNaoDescontadas = mesesNaoPagos.filter(
    (mes) => !["quitada", "descontado", "liquidada"].includes(String(mes.status)),
  );
  const parcelasQuitadasForaDoCiclo = mesesNaoPagos.filter((mes) =>
    ["quitada", "descontado", "liquidada"].includes(String(mes.status)),
  );
  if (!ciclos.length && !mesesNaoPagos.length) {
    return <p className="text-sm text-muted-foreground">Nenhum ciclo encontrado.</p>;
  }

  return (
    <>
      <Tabs defaultValue={String(ciclos[0]?.id ?? "nao-pagos")}>
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
          {parcelasNaoDescontadas.length ? (
            <TabsTrigger value="nao-pagos">
              <div className="flex flex-col items-start">
                <span>Parcelas não descontadas</span>
                <span className="text-[10px] font-mono text-muted-foreground">
                  {parcelasNaoDescontadas.length} registro(s)
                </span>
              </div>
            </TabsTrigger>
          ) : null}
          {parcelasQuitadasForaDoCiclo.length ? (
            <TabsTrigger value="quitadas-fora-do-ciclo">
              <div className="flex flex-col items-start">
                <span>Quitadas fora do ciclo</span>
                <span className="text-[10px] font-mono text-muted-foreground">
                  {parcelasQuitadasForaDoCiclo.length} registro(s)
                </span>
              </div>
            </TabsTrigger>
          ) : null}
        </TabsList>
        {ciclos.map((ciclo) => (
          <TabsContent key={ciclo.id} value={String(ciclo.id)} className="pt-4">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-foreground">{ciclo.contrato_codigo}</p>
                <p className="text-sm text-muted-foreground">
                  Meses do ciclo: {ciclo.resumo_referencias}
                </p>
              </div>
              <StatusBadge
                status={ciclo.status_visual_slug}
                label={ciclo.status_visual_label}
              />
            </div>
            <div className="grid gap-4 md:grid-cols-3">
              {ciclo.parcelas.map((parcela) => (
                <button
                  key={parcela.id}
                  type="button"
                  onClick={() =>
                    setSelectedTarget({
                      contratoId: ciclo.contrato_id,
                      referenciaMes: parcela.referencia_mes,
                      kind: "cycle",
                    })
                  }
                  className="rounded-2xl border border-border/60 bg-background/70 p-4 text-left transition hover:border-primary/50"
                >
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-medium">
                      Parcela {parcela.numero}/{ciclo.parcelas.length}
                    </p>
                    <StatusBadge status={parcela.status} />
                  </div>
                  <p className="mt-2 text-sm text-muted-foreground">
                    {formatMonthYear(parcela.referencia_mes)}
                  </p>
                </button>
              ))}
            </div>
          </TabsContent>
        ))}
        {parcelasNaoDescontadas.length ? (
          <TabsContent value="nao-pagos" className="pt-4">
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {parcelasNaoDescontadas.map((mes) => (
                <button
                  key={mes.id}
                  type="button"
                  onClick={() =>
                    setSelectedTarget({
                      contratoId: mes.contrato_id,
                      referenciaMes: mes.referencia_mes,
                      kind: "unpaid",
                    })
                  }
                  className="rounded-2xl border border-border/60 bg-background/70 p-4 text-left transition hover:border-primary/50"
                >
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-medium">{formatMonthYear(mes.referencia_mes)}</p>
                    <StatusBadge status={mes.status} />
                  </div>
                  <p className="mt-2 text-sm text-muted-foreground">{mes.contrato_codigo}</p>
                  <p className="text-sm text-muted-foreground">{formatCurrency(mes.valor)}</p>
                  <p className="mt-2 text-sm text-muted-foreground">
                    {mes.observacao || "Sem observação."}
                  </p>
                </button>
              ))}
            </div>
          </TabsContent>
        ) : null}
        {parcelasQuitadasForaDoCiclo.length ? (
          <TabsContent value="quitadas-fora-do-ciclo" className="pt-4">
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {parcelasQuitadasForaDoCiclo.map((mes) => (
                <button
                  key={mes.id}
                  type="button"
                  onClick={() =>
                    setSelectedTarget({
                      contratoId: mes.contrato_id,
                      referenciaMes: mes.referencia_mes,
                      kind: "unpaid",
                    })
                  }
                  className="rounded-2xl border border-border/60 bg-background/70 p-4 text-left transition hover:border-primary/50"
                >
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-medium">{formatMonthYear(mes.referencia_mes)}</p>
                    <StatusBadge status={mes.status} />
                  </div>
                  <p className="mt-2 text-sm text-muted-foreground">{mes.contrato_codigo}</p>
                  <p className="text-sm text-muted-foreground">{formatCurrency(mes.valor)}</p>
                  <p className="mt-2 text-sm text-muted-foreground">
                    {mes.observacao || "Sem observação."}
                  </p>
                </button>
              ))}
            </div>
          </TabsContent>
        ) : null}
      </Tabs>
      <ParcelaDetalheDialog
        associadoId={associadoId}
        target={selectedTarget}
        onOpenChange={(open) => {
          if (!open) {
            setSelectedTarget(null);
          }
        }}
      />
    </>
  );
}

function AssociadosPageContent() {
  const { hasRole } = usePermissions();
  const isAdmin = hasRole("ADMIN");
  const [page, setPage] = React.useState(1);
  const [search, setSearch] = React.useState("");
  const [detailMetric, setDetailMetric] = React.useState<AssociadoMetricKey | null>(null);
  const [filters, setFilters] = React.useState<FiltersState>({
    status: "",
    orgao_publico: "",
    data_inicio: "",
    data_fim: "",
    agente: "",
    numero_ciclos: "",
    perfil_ciclo: "",
    faixa_mensalidade: [],
    faixa_parcelas: [],
  });
  const debouncedSearch = useDebouncedValue(search, 300);

  const agentesQuery = useQuery({
    queryKey: ["associados-agentes"],
    queryFn: () => apiFetch<SimpleUser[]>("associados/agentes"),
    ...dashboardOptionsQueryOptions,
  });

  const baseQueryFilters = React.useMemo(
    () => ({
      search: debouncedSearch || undefined,
      orgao_publico: filters.orgao_publico || undefined,
      data_cadastro_inicio: filters.data_inicio || undefined,
      data_cadastro_fim: filters.data_fim || undefined,
      agente: filters.agente || undefined,
      numero_ciclos: filters.numero_ciclos || undefined,
      perfil_ciclo: filters.perfil_ciclo || undefined,
      faixa_mensalidade: filters.faixa_mensalidade.length
        ? filters.faixa_mensalidade
        : undefined,
      faixa_parcelas: filters.faixa_parcelas.length ? filters.faixa_parcelas : undefined,
    }),
    [debouncedSearch, filters],
  );

  const metricasQuery = useQuery({
    queryKey: ["associados-metricas", baseQueryFilters],
    queryFn: () =>
      apiFetch<AssociadoMetricas>("associados/metricas", {
        query: baseQueryFilters,
      }),
    ...dashboardRetainedQueryOptions,
  });

  const associadosQuery = useQuery({
    queryKey: ["associados", page, baseQueryFilters, filters.status],
    queryFn: () =>
      apiFetch<PaginatedResponse<AssociadoListItem>>("associados", {
        query: {
          page,
          page_size: 20,
          ...baseQueryFilters,
          status: filters.status || undefined,
        },
      }),
    ...dashboardRetainedQueryOptions,
  });

  const detailRowsQuery = useQuery({
    queryKey: ["associados-detail-metric", detailMetric, baseQueryFilters],
    enabled: detailMetric !== null,
    queryFn: () =>
      apiFetch<PaginatedResponse<AssociadoListItem>>("associados", {
        query: {
          page: 1,
          page_size: 100,
          ...baseQueryFilters,
          status: detailMetric ? METRIC_STATUS_QUERY[detailMetric] : undefined,
        },
      }),
    ...dashboardRetainedQueryOptions,
  });

  const metricas = metricasQuery.data;
  const associados = associadosQuery.data?.results ?? [];
  const totalPages = Math.max(1, Math.ceil((associadosQuery.data?.count ?? 0) / 20));
  const activeAdvancedFiltersCount = [
    Boolean(filters.status),
    Boolean(filters.orgao_publico),
    Boolean(filters.data_inicio),
    Boolean(filters.data_fim),
    Boolean(filters.agente),
    Boolean(filters.numero_ciclos),
    Boolean(filters.perfil_ciclo),
    filters.faixa_mensalidade.length > 0,
    filters.faixa_parcelas.length > 0,
  ].filter(Boolean).length;

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
          <CopySnippet
            label="Matrícula do Servidor"
            value={row.matricula_orgao || row.matricula}
            mono
            inline
          />
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
            <Badge className="rounded-full bg-emerald-500/15 text-emerald-200">
              {row.ciclos_abertos} abertos
            </Badge>
            <Badge className="rounded-full bg-slate-500/15 text-slate-200">
              {row.ciclos_fechados} fechados
            </Badge>
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
        accessor: "status_visual_label",
        cell: (row) => (
          <div className="space-y-2">
            <StatusBadge status={row.status_visual_slug} label={row.status_visual_label} />
            {row.possui_meses_nao_descontados ? (
              <p className="text-xs text-amber-200">
                {row.meses_nao_descontados_count} mês(es) não descontado(s)
              </p>
            ) : null}
          </div>
        ),
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
            {isAdmin ? (
              <Button variant="outline" size="icon-sm" asChild>
                <Link href={`/associados-editar/${row.id}`}>
                  <PencilIcon className="size-4" />
                </Link>
              </Button>
            ) : null}
          </div>
        ),
      },
    ],
    [],
  );

  const detailColumns = React.useMemo<DataTableColumn<AssociadoListItem>[]>(
    () => [
      {
        id: "nome",
        header: "Associado",
        cell: (row) => (
          <div>
            <p className="font-medium">{row.nome_completo}</p>
            <p className="text-xs text-muted-foreground">{row.agente?.full_name ?? "Sem agente"}</p>
          </div>
        ),
      },
      {
        id: "cpf",
        header: "CPF/CNPJ",
        cell: (row) => <CopySnippet label="CPF" value={row.cpf_cnpj} mono inline />,
      },
      {
        id: "matricula",
        header: "Matrícula",
        cell: (row) => row.matricula_display || row.matricula,
      },
      {
        id: "ciclos",
        header: "Ciclos",
        cell: (row) => `${row.ciclos_abertos + row.ciclos_fechados}`,
      },
      {
        id: "status",
        header: "Status",
        cell: (row) => (
          <div className="space-y-2">
            <StatusBadge status={row.status_visual_slug} label={row.status_visual_label} />
            {row.possui_meses_nao_descontados ? (
              <p className="text-xs text-amber-200">
                {row.meses_nao_descontados_count} mês(es) não descontado(s)
              </p>
            ) : null}
          </div>
        ),
      },
      {
        id: "abrir",
        header: "Ação",
        cell: (row) => (
          <Button variant="outline" size="sm" asChild>
            <Link href={`/associados/${row.id}`}>Abrir</Link>
          </Button>
        ),
      },
    ],
    [],
  );

  return (
    <div className="space-y-8">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        {metricasQuery.isLoading && !metricas ? (
          Array.from({ length: 5 }).map((_, index) => <MetricCardSkeleton key={index} />)
        ) : (
          (Object.keys(METRIC_META) as AssociadoMetricKey[]).map((key) => {
            const metric = metricas?.[key];
            const meta = METRIC_META[key];
            return (
              <StatsCard
                key={key}
                title={meta.title}
                value={(metric?.count ?? 0).toLocaleString("pt-BR")}
                delta={formatMetricDelta(metric?.variacao_percentual ?? 0)}
                tone={meta.tone}
                icon={meta.icon}
                onClick={() => setDetailMetric(key)}
              />
            );
          })
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
                {activeAdvancedFiltersCount ? (
                  <Badge className="ml-1 rounded-full bg-primary/15 px-2 py-0 text-primary">
                    {activeAdvancedFiltersCount}
                  </Badge>
                ) : null}
              </Button>
            </SheetTrigger>
            <SheetContent className="w-full border-l border-border/60 sm:max-w-md">
              <SheetHeader>
                <SheetTitle>Filtros avançados</SheetTitle>
              </SheetHeader>
              <div className="space-y-5 p-4">
                <div className="space-y-2">
                  <p className="text-sm font-medium">Status</p>
                  <Select
                    value={filters.status || ALL_STATUS_VALUE}
                    onValueChange={(value) =>
                      setFilters((current) => ({
                        ...current,
                        status: value === ALL_STATUS_VALUE ? "" : value,
                      }))
                    }
                  >
                    <SelectTrigger className="w-full rounded-xl bg-card/60">
                      <SelectValue placeholder="Todos os status" />
                    </SelectTrigger>
                    <SelectContent>
                      {STATUS_OPTIONS.map((option) => (
                        <SelectItem key={option.label} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <p className="text-sm font-medium">Agente</p>
                  <Select
                    value={filters.agente || ALL_AGENTS_VALUE}
                    onValueChange={(value) =>
                      setFilters((current) => ({
                        ...current,
                        agente: value === ALL_AGENTS_VALUE ? "" : value,
                      }))
                    }
                  >
                    <SelectTrigger className="w-full rounded-xl bg-card/60">
                      <SelectValue
                        placeholder={
                          agentesQuery.isLoading ? "Carregando agentes..." : "Todos os agentes"
                        }
                      />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value={ALL_AGENTS_VALUE}>Todos os agentes</SelectItem>
                      {(agentesQuery.data ?? []).map((agente) => (
                        <SelectItem key={agente.id} value={String(agente.id)}>
                          {agente.full_name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <p className="text-sm font-medium">Órgão público</p>
                  <Input
                    value={filters.orgao_publico}
                    onChange={(event) =>
                      setFilters((current) => ({
                        ...current,
                        orgao_publico: event.target.value,
                      }))
                    }
                    placeholder="Secretaria..."
                    className="rounded-xl bg-card/60"
                  />
                </div>
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <p className="text-sm font-medium">Número de ciclos</p>
                    <Select
                      value={filters.numero_ciclos || ALL_CICLOS_VALUE}
                      onValueChange={(value) =>
                        setFilters((current) => ({
                          ...current,
                          numero_ciclos: value === ALL_CICLOS_VALUE ? "" : value,
                        }))
                      }
                    >
                      <SelectTrigger className="w-full rounded-xl bg-card/60">
                        <SelectValue placeholder="Todos os ciclos" />
                      </SelectTrigger>
                      <SelectContent>
                        {CICLO_OPTIONS.map((option) => (
                          <SelectItem key={option.label} value={option.value}>
                            {option.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <p className="text-sm font-medium">Perfil</p>
                    <Select
                      value={filters.perfil_ciclo || ALL_PERFIL_CICLO_VALUE}
                      onValueChange={(value) =>
                        setFilters((current) => ({
                          ...current,
                          perfil_ciclo:
                            value === ALL_PERFIL_CICLO_VALUE ? "" : value,
                        }))
                      }
                    >
                      <SelectTrigger className="w-full rounded-xl bg-card/60">
                        <SelectValue placeholder="Todos os perfis" />
                      </SelectTrigger>
                      <SelectContent>
                        {PERFIL_CICLO_OPTIONS.map((option) => (
                          <SelectItem key={option.label} value={option.value}>
                            {option.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="grid gap-4 md:grid-cols-2">
                  <MultiSelectFilterField
                    label="Faixas de parcelas pagas"
                    placeholder="Todas as faixas"
                    options={PARCELAS_PAGAS_FAIXAS}
                    value={filters.faixa_parcelas}
                    onChange={(nextValue) =>
                      setFilters((current) => ({
                        ...current,
                        faixa_parcelas:
                          typeof nextValue === "function"
                            ? nextValue(current.faixa_parcelas)
                            : nextValue,
                      }))
                    }
                  />
                  <MultiSelectFilterField
                    label="Faixas de mensalidade"
                    placeholder="Todas as faixas"
                    options={MENSALIDADE_FAIXAS}
                    value={filters.faixa_mensalidade}
                    onChange={(nextValue) =>
                      setFilters((current) => ({
                        ...current,
                        faixa_mensalidade:
                          typeof nextValue === "function"
                            ? nextValue(current.faixa_mensalidade)
                            : nextValue,
                      }))
                    }
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
                    setFilters({
                      status: "",
                      orgao_publico: "",
                      data_inicio: "",
                      data_fim: "",
                      agente: "",
                      numero_ciclos: "",
                      perfil_ciclo: "",
                      faixa_mensalidade: [],
                      faixa_parcelas: [],
                    });
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

      <DashboardDetailDialog
        open={detailMetric !== null}
        onOpenChange={(open) => {
          if (!open) {
            setDetailMetric(null);
          }
        }}
        title={detailMetric ? METRIC_META[detailMetric].title : "Detalhamento"}
        description="Tabela operacional com associados, agente responsável, ciclos e acesso ao detalhe."
        rows={detailRowsQuery.data?.results ?? []}
        columns={detailColumns}
        exportColumns={[
          {
            header: "Associado",
            value: (row) => row.nome_completo,
          },
          {
            header: "CPF/CNPJ",
            value: (row) => row.cpf_cnpj,
          },
          {
            header: "Matrícula",
            value: (row) => row.matricula_display || row.matricula,
          },
          {
            header: "Agente",
            value: (row) => row.agente?.full_name ?? "",
          },
          {
            header: "Ciclos",
            value: (row) => String(row.ciclos_abertos + row.ciclos_fechados),
          },
          {
            header: "Status",
            value: (row) => row.status_visual_label,
          },
        ]}
        exportTitle={detailMetric ? METRIC_META[detailMetric].title : "Associados"}
        exportFilename={`associados-${detailMetric ?? "detalhe"}`}
        emptyMessage="Nenhum associado encontrado para o KPI selecionado."
        isLoading={detailRowsQuery.isLoading}
        matchesSearch={(row, normalized) =>
          [
            row.nome_completo,
            row.cpf_cnpj,
            row.matricula,
            row.matricula_display,
            row.agente?.full_name,
          ]
            .filter(Boolean)
            .some((value) => value!.toLowerCase().includes(normalized))
        }
      />
    </div>
  );
}

export default function AssociadosPage() {
  return (
    <RoleGuard allow={["ADMIN", "COORDENADOR"]}>
      <AssociadosPageContent />
    </RoleGuard>
  );
}
