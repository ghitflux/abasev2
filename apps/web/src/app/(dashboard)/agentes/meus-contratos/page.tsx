"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  BellRingIcon,
  BriefcaseBusiness,
  ChevronRightIcon,
  EyeIcon,
  FilterIcon,
  HandCoinsIcon,
  TriangleAlertIcon,
  WalletIcon,
} from "lucide-react";
import { toast } from "sonner";

import type {
  AssociadoCyclesPayload,
  ContratoListItem,
  ContratoResumoCards,
  PaginatedResponse,
  SimpleUser,
} from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import {
  formatDateValue,
  formatMonthValue,
  parseDateValue,
  parseMonthValue,
} from "@/lib/date-value";
import { formatCurrency, formatDate, formatMonthYear } from "@/lib/formatters";
import { cn } from "@/lib/utils";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { usePermissions } from "@/hooks/use-permissions";
import CalendarCompetencia from "@/components/custom/calendar-competencia";
import {
  ParcelaDetalheDialog,
  type ParcelaDetailTarget,
} from "@/components/contratos/parcela-detalhe-dialog";
import DatePicker from "@/components/custom/date-picker";
import StatusBadge from "@/components/custom/status-badge";
import CopySnippet from "@/components/shared/copy-snippet";
import DashboardDetailDialog from "@/components/shared/dashboard-detail-dialog";
import DataTable, {
  type DataTableColumn,
} from "@/components/shared/data-table";
import ExportButton from "@/components/shared/export-button";
import { InlinePanelSkeleton, MetricCardSkeleton } from "@/components/shared/page-skeletons";
import StatsCard from "@/components/shared/stats-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { exportPaginatedRouteReport } from "@/lib/reports";

const ETAPA_FLUXO_LABELS: Record<string, string> = {
  analise: "Análise",
  tesouraria: "Tesouraria",
  concluido: "Concluído",
};

const STATUS_FILTER_OPTIONS = [
  { value: "todos", label: "Todos os status" },
  { value: "pendente", label: "Pendente" },
  { value: "ativo", label: "Ativo" },
  { value: "desativado", label: "Desativado" },
  { value: "inadimplente", label: "Inadimplente" },
  { value: "liquidado", label: "Liquidado" },
];

const ETAPA_FILTER_OPTIONS = [
  { value: "todas", label: "Todas as etapas" },
  { value: "analise", label: "Análise" },
  { value: "tesouraria", label: "Tesouraria" },
  { value: "concluido", label: "Concluído" },
];

const PAGE_SIZE_OPTIONS = [
  { value: "10", label: "10 por página" },
  { value: "20", label: "20 por página" },
  { value: "50", label: "50 por página" },
  { value: "100", label: "100 por página" },
  { value: "all", label: "Todos" },
];

const PERFIL_CICLO_OPTIONS = [
  { value: "todos", label: "Todos os perfis" },
  { value: "novo", label: "Novos" },
  { value: "renovado", label: "Renovados" },
];

const CICLO_OPTIONS = [
  { value: "todos", label: "Todos os ciclos" },
  { value: "1", label: "1 ciclo" },
  { value: "2", label: "2 ciclos" },
  { value: "3", label: "3 ciclos" },
  { value: "4", label: "4 ciclos" },
  { value: "5", label: "5 ciclos" },
];

const ALL_AGENTS_VALUE = "todos";

type ContratoMetricKey =
  | "total"
  | "ativos"
  | "pendentes"
  | "inadimplentes"
  | "liquidados";

const METRIC_STATUS_QUERY: Record<ContratoMetricKey, string | undefined> = {
  total: undefined,
  ativos: "ativo",
  pendentes: "pendente",
  inadimplentes: "inadimplente",
  liquidados: "liquidado",
};

const METRIC_META: Record<
  ContratoMetricKey,
  {
    title: string;
    tone: "positive" | "warning" | "neutral";
    icon: typeof BriefcaseBusiness;
    delta: (resumo: ContratoResumoCards | undefined) => string;
  }
> = {
  total: {
    title: "Contratos cadastrados",
    tone: "neutral",
    icon: BriefcaseBusiness,
    delta: (resumo) => `${resumo?.pendentes ?? 0} pendentes no recorte atual`,
  },
  ativos: {
    title: "Contratos ativos",
    tone: "positive",
    icon: WalletIcon,
    delta: () => "Liberados para acompanhamento mensal",
  },
  pendentes: {
    title: "Contratos pendentes",
    tone: "warning",
    icon: BellRingIcon,
    delta: () => "Aguardando análise ou tesouraria",
  },
  inadimplentes: {
    title: "Contratos inadimplentes",
    tone: "warning",
    icon: TriangleAlertIcon,
    delta: () => "Associados com pendência de desconto",
  },
  liquidados: {
    title: "Liquidados",
    tone: "positive",
    icon: HandCoinsIcon,
    delta: () => "Contratos encerrados no fluxo",
  },
};

function normalizeEtapaFluxo(stage: string) {
  if (stage === "tesouraria") return "tesouraria";
  if (stage === "concluido") return "concluido";
  return "analise";
}

function ContratoCiclosPanel({ associadoId }: { associadoId: number }) {
  const [selectedTarget, setSelectedTarget] =
    React.useState<ParcelaDetailTarget | null>(null);
  const ciclosQuery = useQuery({
    queryKey: ["contrato-associado-ciclos", associadoId],
    queryFn: () => apiFetch<AssociadoCyclesPayload>(`associados/${associadoId}/ciclos`),
  });

  if (ciclosQuery.isLoading) {
    return <InlinePanelSkeleton rows={2} className="pt-2" />;
  }

  const payload = ciclosQuery.data;
  const ciclos = payload?.ciclos ?? [];
  const mesesNaoPagos = payload?.meses_nao_pagos ?? [];
  if (!ciclos.length && !mesesNaoPagos.length) {
    return (
      <p className="text-sm text-muted-foreground">Nenhum ciclo encontrado.</p>
    );
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
          {mesesNaoPagos.length ? (
            <TabsTrigger value="nao-pagos">
              <div className="flex flex-col items-start">
                <span>Parcelas não descontadas</span>
                <span className="text-[10px] font-mono text-muted-foreground">
                  {mesesNaoPagos.length} registro(s)
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
        {mesesNaoPagos.length ? (
          <TabsContent value="nao-pagos" className="pt-4">
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {mesesNaoPagos.map((mes) => (
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
                  <p className="text-sm text-muted-foreground">
                    {formatCurrency(mes.valor)}
                  </p>
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

export default function MeusContratosPage() {
  const { hasRole } = usePermissions();
  const isAdmin = hasRole("ADMIN");
  const [associadoFilter, setAssociadoFilter] = React.useState("");
  const [agenteFilter, setAgenteFilter] = React.useState(ALL_AGENTS_VALUE);
  const [statusFilter, setStatusFilter] = React.useState("todos");
  const [etapaFilter, setEtapaFilter] = React.useState("todas");
  const [competenciaFilter, setCompetenciaFilter] = React.useState("");
  const [dataInicio, setDataInicio] = React.useState("");
  const [dataFim, setDataFim] = React.useState("");
  const [numeroCiclosFilter, setNumeroCiclosFilter] = React.useState("todos");
  const [perfilCicloFilter, setPerfilCicloFilter] = React.useState("todos");
  const [detailMetric, setDetailMetric] =
    React.useState<ContratoMetricKey | null>(null);
  const [page, setPage] = React.useState(1);
  const [isExporting, setIsExporting] = React.useState(false);
  const [pageSize, setPageSize] = React.useState("10");
  const [mensalidadesFilter, setMensalidadesFilter] = React.useState("todas");
  const debouncedAssociadoFilter = useDebouncedValue(associadoFilter, 300);
  const isAllPageSize = pageSize === "all";

  const agentesQuery = useQuery({
    queryKey: ["contratos-agentes", isAdmin],
    enabled: isAdmin,
    queryFn: () => apiFetch<SimpleUser[]>("associados/agentes"),
  });

  const resetAdvancedFilters = React.useCallback(() => {
    setAgenteFilter(ALL_AGENTS_VALUE);
    setStatusFilter("todos");
    setEtapaFilter("todas");
    setCompetenciaFilter("");
    setDataInicio("");
    setDataFim("");
    setNumeroCiclosFilter("todos");
    setPerfilCicloFilter("todos");
    setMensalidadesFilter("todas");
    setPageSize("10");
    setPage(1);
  }, []);

  const baseQueryFilters = React.useMemo(
    () => ({
      associado: debouncedAssociadoFilter || undefined,
      agente:
        isAdmin && agenteFilter !== ALL_AGENTS_VALUE ? agenteFilter : undefined,
      status_visual: statusFilter === "todos" ? undefined : statusFilter,
      etapa_fluxo: etapaFilter === "todas" ? undefined : etapaFilter,
      competencia: competenciaFilter || undefined,
      data_inicio: dataInicio || undefined,
      data_fim: dataFim || undefined,
      mensalidades:
        mensalidadesFilter === "todas"
          ? undefined
          : Number(mensalidadesFilter),
      numero_ciclos:
        numeroCiclosFilter === "todos"
          ? undefined
          : Number(numeroCiclosFilter),
      perfil_ciclo:
        perfilCicloFilter === "todos" ? undefined : perfilCicloFilter,
    }),
    [
      agenteFilter,
      competenciaFilter,
      dataFim,
      dataInicio,
      debouncedAssociadoFilter,
      etapaFilter,
      isAdmin,
      mensalidadesFilter,
      numeroCiclosFilter,
      perfilCicloFilter,
      statusFilter,
    ],
  );

  const resumoQuery = useQuery({
    queryKey: [
      "contratos-resumo",
      baseQueryFilters,
    ],
    queryFn: () =>
      apiFetch<ContratoResumoCards>("contratos/resumo", {
        query: baseQueryFilters,
      }),
  });

  const contratosQuery = useQuery({
    queryKey: [
      "contratos-lista",
      page,
      pageSize,
      baseQueryFilters,
    ],
    queryFn: () =>
      apiFetch<PaginatedResponse<ContratoListItem>>("contratos", {
        query: {
          page,
          page_size: isAllPageSize ? "all" : Number(pageSize),
          ...baseQueryFilters,
        },
      }),
  });

  const detailRowsQuery = useQuery({
    queryKey: ["contratos-detail-metric", detailMetric, baseQueryFilters],
    enabled: detailMetric !== null,
    queryFn: () =>
      apiFetch<PaginatedResponse<ContratoListItem>>("contratos", {
        query: {
          page: 1,
          page_size: "all",
          ...baseQueryFilters,
          status_visual: detailMetric ? METRIC_STATUS_QUERY[detailMetric] : undefined,
        },
      }),
  });

  const rows = contratosQuery.data?.results ?? [];
  const totalCount = contratosQuery.data?.count ?? 0;
  const totalPages = Math.max(
    1,
    isAllPageSize ? 1 : Math.ceil(totalCount / Number(pageSize)),
  );
  const activeAdvancedFiltersCount = React.useMemo(
    () =>
      [
        isAdmin && agenteFilter !== ALL_AGENTS_VALUE,
        statusFilter !== "todos",
        etapaFilter !== "todas",
        Boolean(competenciaFilter),
        Boolean(dataInicio),
        Boolean(dataFim),
        numeroCiclosFilter !== "todos",
        perfilCicloFilter !== "todos",
        mensalidadesFilter !== "todas",
        pageSize !== "10",
      ].filter(Boolean).length,
    [
      agenteFilter,
      statusFilter,
      etapaFilter,
      competenciaFilter,
      dataInicio,
      dataFim,
      isAdmin,
      numeroCiclosFilter,
      perfilCicloFilter,
      mensalidadesFilter,
      pageSize,
    ],
  );

  const handleExport = React.useCallback(
    async (format: "csv" | "pdf" | "excel" | "xlsx") => {
      if (format !== "pdf" && format !== "xlsx") {
        return;
      }

      setIsExporting(true);
      try {
        await exportPaginatedRouteReport<ContratoListItem>({
          route: "/agentes/meus-contratos",
          format,
          sourcePath: "contratos",
          sourceQuery: baseQueryFilters,
          mapRow: (row) => ({
            codigo: row.codigo,
            associado: row.associado.nome_completo,
            status_visual_label: row.status_visual_label,
            etapa_fluxo: row.etapa_fluxo,
            valor_disponivel: row.valor_disponivel,
            status_renovacao: row.status_renovacao,
            cancelamento_tipo: row.cancelamento_tipo ?? "",
            cancelamento_motivo: row.cancelamento_motivo ?? "",
          }),
        });
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "Falha ao exportar contratos.");
      } finally {
        setIsExporting(false);
      }
    },
    [baseQueryFilters],
  );

  React.useEffect(() => {
    if (page > totalPages) {
      setPage(totalPages);
    }
  }, [page, totalPages]);

  const columns = React.useMemo<DataTableColumn<ContratoListItem>[]>(
    () => [
      {
        id: "associado",
        header: "Associado",
        headerClassName: "w-[19%] whitespace-normal leading-5",
        cellClassName: "whitespace-normal break-words",
        cell: (row) => (
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <ChevronRightIcon className="size-4 shrink-0 text-muted-foreground" />
              <div className="min-w-0 space-y-1">
                <CopySnippet
                  label="Nome"
                  value={row.associado.nome_completo}
                  inline
                  className="max-w-full"
                />
                <p className="text-xs text-muted-foreground">
                  Clique na linha para ver ciclos
                </p>
              </div>
            </div>
            <div className="flex flex-wrap gap-2 pl-7">
              <CopySnippet label="CPF" value={row.associado.cpf_cnpj} mono inline />
              <CopySnippet
                label="Matrícula do Servidor"
                value={row.associado.matricula_orgao || row.associado.matricula}
                mono
                inline
              />
            </div>
          </div>
        ),
      },
      ...(isAdmin
        ? [
            {
              id: "agente",
              header: "Agente",
              headerClassName: "w-[11%] whitespace-normal leading-5",
              cellClassName: "whitespace-normal break-words",
              cell: (row: ContratoListItem) =>
                row.agente?.full_name ?? "Sem agente",
            } satisfies DataTableColumn<ContratoListItem>,
          ]
        : []),
      {
        id: "status",
        header: "Status do Contrato",
        headerClassName: "w-[14%] whitespace-normal leading-5",
        cellClassName: "whitespace-normal",
        cell: (row) => (
            <div className="space-y-3">
              <div className="space-y-1">
                <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                  Status do contrato
                </p>
                <StatusBadge
                  status={row.status_visual_slug}
                  label={row.status_visual_label}
                />
                {row.possui_meses_nao_descontados ? (
                  <p className="text-xs text-amber-200">
                    {row.meses_nao_descontados_count} mês(es) não descontado(s)
                  </p>
                ) : null}
                {row.cancelamento_tipo ? (
                  <div className="space-y-1">
                    <Badge className="rounded-full bg-rose-500/15 text-rose-200">
                      {row.cancelamento_tipo === "desistente"
                        ? "Desistente"
                        : "Cancelado"}
                    </Badge>
                    <p className="max-w-xs text-xs text-rose-200/90">
                      {row.cancelamento_motivo || "Contrato encerrado antes da ativação."}
                    </p>
                    {row.cancelado_em ? (
                      <p className="text-[11px] text-muted-foreground">
                        Registrado em {formatDate(row.cancelado_em)}
                      </p>
                    ) : null}
                  </div>
                ) : null}
            </div>
            <div className="space-y-1">
              <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                Etapa do fluxo
              </p>
              <StatusBadge
                status={normalizeEtapaFluxo(row.etapa_fluxo)}
                label={
                  ETAPA_FLUXO_LABELS[normalizeEtapaFluxo(row.etapa_fluxo)] ??
                  "Análise"
                }
              />
            </div>
          </div>
        ),
      },
      {
        id: "valor_disponivel",
        header: "Valor disponível",
        headerClassName: "w-[10%] whitespace-normal leading-5",
        cell: (row) => formatCurrency(row.valor_disponivel),
      },
      {
        id: "auxilio",
        header: "Auxílio do Agente",
        headerClassName: "w-[12%] whitespace-normal leading-5",
        cellClassName: "whitespace-normal",
        cell: (row) => (
          <div>
            <p>{formatCurrency(row.comissao_agente)}</p>
            <p className="text-xs text-muted-foreground">Repasse configurado do agente</p>
          </div>
        ),
      },
      {
        id: "mensalidades",
        header: "Ciclo atual",
        headerClassName: "w-[16%] whitespace-normal leading-5",
        cellClassName: "whitespace-normal",
        cell: (row) => (
          <div className="space-y-2">
            <p className="font-medium">
              {row.mensalidades.pagas}/{row.mensalidades.total}
            </p>
            <p className="text-xs text-muted-foreground">
              {row.mensalidades.descricao}
            </p>
          </div>
        ),
      },
      {
        id: "liberacao",
        header: "Liberação do Auxílio",
        headerClassName: "w-[10%] whitespace-normal leading-5",
        cellClassName: "whitespace-normal",
        cell: (row) =>
          row.auxilio_liberado_em ? (
            <div className="space-y-1">
              <StatusBadge status="pago" label="Pago" />
              <p className="text-xs text-muted-foreground">
                {formatDate(row.auxilio_liberado_em)}
              </p>
            </div>
          ) : (
            <StatusBadge status="pendente" label="Pendente" />
          ),
      },
      {
        id: "acoes",
        header: "Ações",
        headerClassName: "w-[8%] whitespace-normal leading-5",
        cellClassName: "whitespace-normal",
        cell: (row) => (
          <div
            className="flex flex-wrap items-center gap-2"
            onClick={(event) => event.stopPropagation()}
          >
            <Button variant="outline" size="icon-sm" asChild>
              <Link href={`/associados/${row.associado.id}`}>
                <EyeIcon className="size-4" />
              </Link>
            </Button>
          </div>
        ),
      },
    ],
    [isAdmin],
  );

  const detailColumns = React.useMemo<DataTableColumn<ContratoListItem>[]>(
    () => [
      {
        id: "associado",
        header: "Associado",
        cell: (row) => (
          <div>
            <p className="font-medium">{row.associado.nome_completo}</p>
            <p className="text-xs text-muted-foreground">
              {row.associado.matricula_orgao || row.associado.matricula}
            </p>
          </div>
        ),
      },
      {
        id: "cpf",
        header: "CPF",
        cell: (row) => (
          <CopySnippet label="CPF" value={row.associado.cpf_cnpj} mono inline />
        ),
      },
      {
        id: "agente",
        header: "Agente",
        cell: (row) => row.agente?.full_name ?? "Sem agente",
      },
      {
        id: "referencia",
        header: "Referência",
        cell: (row) => (
          <div>
            <p className="font-medium">{row.codigo}</p>
            <p className="text-xs text-muted-foreground">
              {row.mensalidades.descricao}
            </p>
          </div>
        ),
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
            <Link href={`/associados/${row.associado.id}`}>Abrir</Link>
          </Button>
        ),
      },
    ],
    [],
  );

  return (
    <div className="min-w-0 space-y-6">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        {resumoQuery.isLoading && !resumoQuery.data ? (
          Array.from({ length: 5 }).map((_, index) => <MetricCardSkeleton key={index} />)
        ) : (
          (Object.keys(METRIC_META) as ContratoMetricKey[]).map((key) => {
            const meta = METRIC_META[key];
            const value =
              key === "total"
                ? resumoQuery.data?.total
                : resumoQuery.data?.[key];
            return (
              <StatsCard
                key={key}
                title={meta.title}
                value={String(value ?? 0)}
                delta={meta.delta(resumoQuery.data)}
                tone={meta.tone}
                icon={meta.icon}
                onClick={() => setDetailMetric(key)}
              />
            );
          })
        )}
      </section>

      <section className="min-w-0 space-y-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h1 className="text-2xl font-semibold">
              {isAdmin ? "Todos os Contratos" : "Meus Contratos"}
            </h1>
            <p className="text-sm text-muted-foreground">
              {isAdmin
                ? "Visão consolidada de todos os contratos com filtros por período, associado, agente e status."
                : "Acompanhe seus contratos, quitações do ciclo atual e prontidão para renovação."}
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <ExportButton
              disabled={isExporting}
              label={isExporting ? "Exportando..." : "Exportar"}
              onExport={(format) => void handleExport(format)}
            />
            {!isAdmin ? (
              <Button asChild>
                <Link href="/agentes/cadastrar-associado">+ Novo Associado</Link>
              </Button>
            ) : null}
          </div>
        </div>

        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="relative w-full max-w-2xl">
            <Input
              value={associadoFilter}
              onChange={(event) => {
                setAssociadoFilter(event.target.value);
                setPage(1);
              }}
              placeholder="Buscar por nome, CPF ou matrícula"
              className="w-full rounded-2xl border-border/60 bg-card/60"
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
              <SheetContent className="w-full border-l border-border/60 sm:max-w-xl">
                <SheetHeader>
                  <SheetTitle>Filtros avançados</SheetTitle>
                  <SheetDescription>
                    Ajuste etapa do fluxo, competência, período, mensalidades,
                    paginação e filtros administrativos.
                  </SheetDescription>
                </SheetHeader>

                <div className="space-y-5 overflow-y-auto px-4 pb-4">
                  {isAdmin ? (
                    <FilterField label="Agente">
                      <Select
                        value={agenteFilter}
                        onValueChange={(value) => {
                          setAgenteFilter(value);
                          setPage(1);
                        }}
                      >
                        <SelectTrigger className="w-full rounded-2xl bg-card/60">
                          <SelectValue
                            placeholder={
                              agentesQuery.isLoading
                                ? "Carregando agentes..."
                                : "Todos os agentes"
                            }
                          />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value={ALL_AGENTS_VALUE}>
                            Todos os agentes
                          </SelectItem>
                          {(agentesQuery.data ?? []).map((agente) => (
                            <SelectItem key={agente.id} value={String(agente.id)}>
                              {agente.full_name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </FilterField>
                  ) : null}

                  <div className="grid gap-4 md:grid-cols-2">
                    <FilterField label="Status do contrato">
                      <Select
                        value={statusFilter}
                        onValueChange={(value) => {
                          setStatusFilter(value);
                          setPage(1);
                        }}
                      >
                        <SelectTrigger className="w-full rounded-2xl bg-card/60">
                          <SelectValue placeholder="Status do contrato" />
                        </SelectTrigger>
                        <SelectContent>
                          {STATUS_FILTER_OPTIONS.map((option) => (
                            <SelectItem key={option.value} value={option.value}>
                              {option.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </FilterField>

                    <FilterField label="Etapa do fluxo">
                      <Select
                        value={etapaFilter}
                        onValueChange={(value) => {
                          setEtapaFilter(value);
                          setPage(1);
                        }}
                      >
                        <SelectTrigger className="w-full rounded-2xl bg-card/60">
                          <SelectValue placeholder="Etapa do fluxo" />
                        </SelectTrigger>
                        <SelectContent>
                          {ETAPA_FILTER_OPTIONS.map((option) => (
                            <SelectItem key={option.value} value={option.value}>
                              {option.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </FilterField>
                  </div>

                  <div className="grid gap-4 md:grid-cols-2">
                    <FilterField label="Mês e ano">
                      <CalendarCompetencia
                        value={parseMonthValue(competenciaFilter)}
                        onChange={(value) => {
                          setCompetenciaFilter(formatMonthValue(value));
                          setPage(1);
                        }}
                      />
                    </FilterField>

                    <FilterField label="Itens por página">
                      <Select
                        value={pageSize}
                        onValueChange={(value) => {
                          setPageSize(value);
                          setPage(1);
                        }}
                      >
                        <SelectTrigger className="w-full rounded-2xl bg-card/60">
                          <SelectValue placeholder="Itens por página" />
                        </SelectTrigger>
                        <SelectContent>
                          {PAGE_SIZE_OPTIONS.map((option) => (
                            <SelectItem key={option.value} value={option.value}>
                              {option.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </FilterField>
                  </div>

                  <div className="grid gap-4 md:grid-cols-2">
                    <FilterField label="Número de ciclos">
                      <Select
                        value={numeroCiclosFilter}
                        onValueChange={(value) => {
                          setNumeroCiclosFilter(value);
                          setPage(1);
                        }}
                      >
                        <SelectTrigger className="w-full rounded-2xl bg-card/60">
                          <SelectValue placeholder="Todos os ciclos" />
                        </SelectTrigger>
                        <SelectContent>
                          {CICLO_OPTIONS.map((option) => (
                            <SelectItem key={option.value} value={option.value}>
                              {option.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </FilterField>

                    <FilterField label="Perfil do ciclo">
                      <Select
                        value={perfilCicloFilter}
                        onValueChange={(value) => {
                          setPerfilCicloFilter(value);
                          setPage(1);
                        }}
                      >
                        <SelectTrigger className="w-full rounded-2xl bg-card/60">
                          <SelectValue placeholder="Todos os perfis" />
                        </SelectTrigger>
                        <SelectContent>
                          {PERFIL_CICLO_OPTIONS.map((option) => (
                            <SelectItem key={option.value} value={option.value}>
                              {option.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </FilterField>
                  </div>

                  <div className="grid gap-4 md:grid-cols-2">
                    <FilterField label="Data inicial">
                      <DatePicker
                        value={parseDateValue(dataInicio)}
                        onChange={(value) => {
                          setDataInicio(formatDateValue(value));
                          setPage(1);
                        }}
                        placeholder="Data inicial"
                      />
                    </FilterField>

                    <FilterField label="Data final">
                      <DatePicker
                        value={parseDateValue(dataFim)}
                        onChange={(value) => {
                          setDataFim(formatDateValue(value));
                          setPage(1);
                        }}
                        placeholder="Data final"
                      />
                    </FilterField>
                  </div>

                  <FilterField label="Pagamentos livres válidos">
                    <Select
                      value={mensalidadesFilter}
                      onValueChange={(value) => {
                        setMensalidadesFilter(value);
                        setPage(1);
                      }}
                    >
                      <SelectTrigger className="w-full rounded-2xl bg-card/60">
                        <SelectValue placeholder="Mensalidades" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="todas">Todas</SelectItem>
                        <SelectItem value="1">1 pagamento</SelectItem>
                        <SelectItem value="2">2 pagamentos</SelectItem>
                        <SelectItem value="3">3 pagamentos</SelectItem>
                        <SelectItem value="4">4 pagamentos</SelectItem>
                      </SelectContent>
                    </Select>
                  </FilterField>
                </div>

                <SheetFooter className="border-t border-border/60">
                  <Button
                    variant="outline"
                    onClick={resetAdvancedFilters}
                    type="button"
                  >
                    Limpar avançados
                  </Button>
                  <SheetClose asChild>
                    <Button type="button">Fechar</Button>
                  </SheetClose>
                </SheetFooter>
              </SheetContent>
            </Sheet>
          </div>
        </div>

        <p className="text-sm text-muted-foreground">
          Mostrando{" "}
          {rows.length
            ? `${isAllPageSize ? 1 : (page - 1) * Number(pageSize) + 1}-${isAllPageSize ? rows.length : (page - 1) * Number(pageSize) + rows.length}`
            : "0"}{" "}
          de {totalCount}
        </p>
      </section>

      <DataTable
        data={rows}
        columns={columns}
        renderExpanded={(row) => (
          <ContratoCiclosPanel associadoId={row.associado.id} />
        )}
        currentPage={page}
        totalPages={totalPages}
        onPageChange={setPage}
        emptyMessage="Nenhum contrato encontrado para os filtros informados."
        loading={contratosQuery.isLoading}
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
        description="Tabela operacional com associado, agente, referência do contrato e acesso direto ao detalhe."
        rows={detailRowsQuery.data?.results ?? []}
        columns={detailColumns}
        exportColumns={[
          {
            header: "Associado",
            value: (row) => row.associado.nome_completo,
          },
          {
            header: "CPF",
            value: (row) => row.associado.cpf_cnpj,
          },
          {
            header: "Matrícula",
            value: (row) => row.associado.matricula_orgao || row.associado.matricula,
          },
          {
            header: "Agente",
            value: (row) => row.agente?.full_name ?? "",
          },
          {
            header: "Referência",
            value: (row) => row.codigo,
          },
          {
            header: "Status",
            value: (row) => row.status_visual_label,
          },
        ]}
        exportTitle={detailMetric ? METRIC_META[detailMetric].title : "Contratos"}
        exportFilename={`contratos-${detailMetric ?? "detalhe"}`}
        emptyMessage="Nenhum contrato encontrado para o KPI selecionado."
        isLoading={detailRowsQuery.isLoading}
        matchesSearch={(row, normalized) =>
          [
            row.associado.nome_completo,
            row.associado.cpf_cnpj,
            row.associado.matricula,
            row.associado.matricula_orgao,
            row.agente?.full_name,
            row.codigo,
          ]
            .filter(Boolean)
            .some((value) => value!.toLowerCase().includes(normalized))
        }
      />
    </div>
  );
}

function FilterField({
  label,
  className,
  children,
}: React.PropsWithChildren<{ label: string; className?: string }>) {
  return (
    <div className={cn("space-y-2", className)}>
      <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
        {label}
      </p>
      {children}
    </div>
  );
}
