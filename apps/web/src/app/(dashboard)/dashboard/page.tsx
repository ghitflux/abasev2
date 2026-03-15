"use client";

import * as React from "react";
import Link from "next/link";
import { format } from "date-fns";
import { useQuery } from "@tanstack/react-query";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  RadialBar,
  RadialBarChart,
  XAxis,
} from "recharts";
import {
  CircleDollarSignIcon,
  LayoutGridIcon,
  SlidersHorizontalIcon,
  Users2Icon,
} from "lucide-react";
import { toast } from "sonner";

import type { DashboardAgentes } from "@/gen/models/DashboardAgentes";
import type { DashboardDetailRow } from "@/gen/models/DashboardDetailRow";
import type { DashboardMetricCard } from "@/gen/models/DashboardMetricCard";
import type { DashboardNovosAssociados } from "@/gen/models/DashboardNovosAssociados";
import type { DashboardResumoGeral } from "@/gen/models/DashboardResumoGeral";
import type { DashboardTesouraria } from "@/gen/models/DashboardTesouraria";
import type { DashboardTrendPoint } from "@/gen/models/DashboardTrendPoint";
import type { DashboardValuePoint } from "@/gen/models/DashboardValuePoint";
import type { PaginatedDashboardDetailRowList } from "@/gen/models/PaginatedDashboardDetailRowList";
import { apiFetch } from "@/lib/api/client";
import {
  formatCurrency,
  formatDate,
  formatLongMonthYear,
} from "@/lib/formatters";
import { maskCPFCNPJ } from "@/lib/masks";
import { cn } from "@/lib/utils";
import RoleGuard from "@/components/auth/role-guard";
import CalendarCompetencia from "@/components/custom/calendar-competencia";
import DatePicker from "@/components/custom/date-picker";
import StatusBadge from "@/components/custom/status-badge";
import DashboardDetailDialog from "@/components/shared/dashboard-detail-dialog";
import type { DataTableColumn } from "@/components/shared/data-table";
import ExportButton from "@/components/shared/export-button";
import { AnalyticsSectionSkeleton } from "@/components/shared/page-skeletons";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
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
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { exportRows, type TableExportColumn } from "@/lib/table-export";

const STATUS_OPTIONS = [
  { value: "todos", label: "Todos os status" },
  { value: "cadastrado", label: "Cadastrado" },
  { value: "em_analise", label: "Em analise" },
  { value: "pendente", label: "Pendente" },
  { value: "ativo", label: "Ativo" },
  { value: "inadimplente", label: "Inadimplente" },
  { value: "inativo", label: "Inativo" },
] as const;

const DETAIL_EXPORT_COLUMNS: TableExportColumn<DashboardDetailRow>[] = [
  { header: "Associado", value: (row) => row.associado_nome },
  { header: "CPF/CNPJ", value: (row) => maskCPFCNPJ(row.cpf_cnpj) },
  { header: "Matricula", value: (row) => row.matricula },
  { header: "Status", value: (row) => row.status },
  { header: "Agente", value: (row) => row.agente_nome },
  { header: "Contrato", value: (row) => row.contrato_codigo },
  { header: "Etapa", value: (row) => row.etapa },
  { header: "Competencia", value: (row) => row.competencia },
  { header: "Valor", value: (row) => row.valor },
  { header: "Origem", value: (row) => row.origem },
  { header: "Data referencia", value: (row) => row.data_referencia },
  { header: "Observacao", value: (row) => row.observacao },
];

const DETAIL_COLUMNS: DataTableColumn<DashboardDetailRow>[] = [
  {
    id: "associado_nome",
    header: "Associado",
    cell: (row) => (
      <div>
        <p className="font-medium text-foreground">
          {row.associado_nome || "Sem associado"}
        </p>
        <p className="text-xs text-muted-foreground">
          {row.origem || row.contrato_codigo || "-"}
        </p>
      </div>
    ),
  },
  {
    id: "cpf_cnpj",
    header: "CPF/CNPJ",
    cell: (row) => (row.cpf_cnpj ? maskCPFCNPJ(row.cpf_cnpj) : "-"),
  },
  {
    id: "matricula",
    header: "Matricula",
    cell: (row) => row.matricula || "-",
  },
  {
    id: "status",
    header: "Status",
    cell: (row) => (row.status ? <StatusBadge status={row.status} /> : "-"),
  },
  {
    id: "agente_nome",
    header: "Agente",
    cell: (row) => row.agente_nome || "-",
  },
  {
    id: "contrato_codigo",
    header: "Contrato",
    cell: (row) =>
      row.associado_id ? (
        <Link
          href={`/associados/${row.associado_id}`}
          className="text-primary hover:underline"
        >
          {row.contrato_codigo || "Abrir cadastro"}
        </Link>
      ) : (
        row.contrato_codigo || "-"
      ),
  },
  {
    id: "competencia",
    header: "Competencia",
    cell: (row) => row.competencia || "-",
  },
  {
    id: "valor",
    header: "Valor",
    cell: (row) => (row.valor ? formatCurrency(row.valor) : "-"),
  },
  {
    id: "data_referencia",
    header: "Data",
    cell: (row) =>
      row.data_referencia ? formatDate(row.data_referencia) : "-",
  },
];

const TREASURY_CHART_CONFIG = {
  recebido: { label: "Recebido", color: "hsl(var(--primary))" },
  projetado: { label: "Projetado", color: "hsl(142 71% 45%)" },
  importacao: { label: "Importacao", color: "hsl(var(--primary))" },
  manual: { label: "Manual", color: "hsl(38 92% 50%)" },
  inadimplentes_quitados: {
    label: "Inadimplentes quitados",
    color: "hsl(142 71% 45%)",
  },
  contratos_novos: { label: "Contratos novos", color: "hsl(199 89% 48%)" },
  recebido_atual: { label: "Recebido", color: "hsl(var(--primary))" },
  pendente_atual: { label: "Pendente", color: "hsl(0 84% 60%)" },
  futuro: { label: "Projecao futura", color: "hsl(142 71% 45%)" },
} satisfies ChartConfig;

const SUMMARY_CHART_CONFIG = {
  value: { label: "Volume", color: "hsl(var(--primary))" },
  cadastros: { label: "Cadastros", color: "hsl(var(--primary))" },
  efetivados: { label: "Efetivados", color: "hsl(142 71% 45%)" },
  renovacoes: { label: "Renovacoes", color: "hsl(199 89% 48%)" },
  cadastrado: { label: "Cadastrado", color: "hsl(var(--primary))" },
  em_analise: { label: "Em analise", color: "hsl(38 92% 50%)" },
  pendente: { label: "Pendente", color: "hsl(0 84% 60%)" },
  ativo: { label: "Ativo", color: "hsl(142 71% 45%)" },
  inadimplente: { label: "Inadimplente", color: "hsl(0 84% 60%)" },
  inativo: { label: "Inativo", color: "hsl(215 20% 65%)" },
} satisfies ChartConfig;

const AGENT_CHART_COLORS = [
  "hsl(var(--primary))",
  "hsl(142 71% 45%)",
  "hsl(199 89% 48%)",
  "hsl(38 92% 50%)",
];

type SectionFilterButtonProps = {
  title: string;
  description: string;
  activeCount: number;
  children: React.ReactNode;
  onClear: () => void;
  onApply: () => void;
  onOpenChange?: (open: boolean) => void;
};

type DetailState = {
  section: "summary" | "treasury" | "new-associados" | "agentes";
  metric: string;
  title: string;
  description: string;
  query: Record<string, string | undefined>;
};

type SummaryFilters = {
  competencia: Date;
  dateStart?: Date;
  dateEnd?: Date;
  status: string;
};

type TreasuryFilters = {
  competencia: Date;
};

type NewAssociadosFilters = {
  dateStart?: Date;
  dateEnd?: Date;
  status: string;
};

type AgentFilters = {
  dateStart?: Date;
  dateEnd?: Date;
};

type DashboardSection = DetailState["section"];

type SectionExportMetric = {
  label: string;
  metric: string;
};

type SectionExportRow = DashboardDetailRow & {
  indicador: string;
};

function toMonthId(value: Date) {
  return format(value, "yyyy-MM");
}

function toIsoDate(value?: Date) {
  return value ? format(value, "yyyy-MM-dd") : undefined;
}

function normalizeText(value: string) {
  return value
    .normalize("NFD")
    .replaceAll(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

function formatMetricValue(card: DashboardMetricCard) {
  if (card.format === "currency") {
    return formatCurrency(card.numeric_value);
  }
  return card.value;
}

function countActiveFilters(
  filters: Record<string, Date | string | undefined>,
) {
  return Object.values(filters).filter((value) => {
    if (value instanceof Date) return true;
    return Boolean(value && value !== "todos");
  }).length;
}

function hasSameMonth(left: Date, right: Date) {
  return toMonthId(left) === toMonthId(right);
}

function hasSameDate(left: Date, right: Date) {
  return format(left, "yyyy-MM-dd") === format(right, "yyyy-MM-dd");
}

function uniqExportMetrics(metrics: Array<SectionExportMetric | null>) {
  const seen = new Set<string>();

  return metrics.filter((metric): metric is SectionExportMetric => {
    if (!metric || seen.has(metric.metric)) return false;
    seen.add(metric.metric);
    return true;
  });
}

function buildPointMetrics(points: DashboardValuePoint[]) {
  return points.map((point) => ({
    label: point.label,
    metric: point.detail_metric,
  }));
}

function buildTrendMetrics(
  points: DashboardTrendPoint[],
  options: {
    includeRenovacoes?: boolean;
  } = {},
) {
  return uniqExportMetrics(
    points.flatMap((point) => [
      {
        label: `Cadastros ${point.label}`,
        metric: point.cadastros_metric,
      },
      {
        label: `Efetivados ${point.label}`,
        metric: point.efetivados_metric,
      },
      options.includeRenovacoes && point.renovacoes_metric
        ? {
            label: `Renovacoes ${point.label}`,
            metric: point.renovacoes_metric,
          }
        : null,
    ]),
  );
}

function buildSummaryExportMetrics(data: DashboardResumoGeral) {
  return uniqExportMetrics([
    ...data.kpis.map((card) => ({
      label: card.label,
      metric: card.detail_metric,
    })),
    ...buildPointMetrics(data.flow_bars),
    ...data.status_pie.map((point) => ({
      label: `Status ${point.label}`,
      metric: point.detail_metric,
    })),
    ...buildTrendMetrics(data.trend_lines, { includeRenovacoes: true }),
  ]);
}

function buildTreasuryExportMetrics(data: DashboardTesouraria) {
  return uniqExportMetrics([
    ...data.cards.map((card) => ({
      label: card.label,
      metric: card.detail_metric,
    })),
    ...data.projection_area.flatMap((point) => [
      {
        label: `Recebido ${point.label}`,
        metric: point.recebido_metric,
      },
      {
        label: `Projetado ${point.label}`,
        metric: point.projetado_metric,
      },
    ]),
    ...buildPointMetrics(data.movement_bars),
    ...data.composition_radial.map((point) => ({
      label: point.label,
      metric: point.detail_metric,
    })),
  ]);
}

function buildNewAssociadosExportMetrics(data: DashboardNovosAssociados) {
  return uniqExportMetrics([
    ...data.cards.map((card) => ({
      label: card.label,
      metric: card.detail_metric,
    })),
    ...buildTrendMetrics(data.trend_area),
    ...data.status_pie.map((point) => ({
      label: `Status ${point.label}`,
      metric: point.detail_metric,
    })),
  ]);
}

function buildAgentsExportMetrics(data: DashboardAgentes) {
  return uniqExportMetrics([
    ...data.ranking.map((item) => ({
      label: `${item.agent_name} · Efetivados`,
      metric: item.detail_metric,
    })),
    ...data.cards.map((card) => ({
      label: card.label,
      metric: card.detail_metric,
    })),
  ]);
}

const SECTION_EXPORT_COLUMNS: TableExportColumn<SectionExportRow>[] = [
  { header: "Indicador", value: (row) => row.indicador },
  { header: "Associado", value: (row) => row.associado_nome },
  { header: "CPF/CNPJ", value: (row) => maskCPFCNPJ(row.cpf_cnpj) },
  { header: "Matricula", value: (row) => row.matricula },
  { header: "Status", value: (row) => row.status },
  { header: "Agente", value: (row) => row.agente_nome },
  { header: "Contrato", value: (row) => row.contrato_codigo },
  { header: "Etapa", value: (row) => row.etapa },
  { header: "Competencia", value: (row) => row.competencia },
  { header: "Valor", value: (row) => row.valor },
  { header: "Origem", value: (row) => row.origem },
  { header: "Data referencia", value: (row) => row.data_referencia },
  { header: "Observacao", value: (row) => row.observacao },
];

function matchesDetailRowSearch(row: DashboardDetailRow, search: string) {
  const haystack = normalizeText(
    [
      row.associado_nome,
      row.cpf_cnpj,
      row.matricula,
      row.status,
      row.agente_nome,
      row.contrato_codigo,
      row.origem,
      row.observacao,
    ]
      .filter(Boolean)
      .join(" "),
  );

  return haystack.includes(normalizeText(search));
}

function FilterField({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2">
      <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
        {label}
      </p>
      {children}
    </div>
  );
}

function SectionFilterButton({
  title,
  description,
  activeCount,
  children,
  onClear,
  onApply,
  onOpenChange,
}: SectionFilterButtonProps) {
  const [open, setOpen] = React.useState(false);

  const handleOpenChange = React.useCallback(
    (nextOpen: boolean) => {
      setOpen(nextOpen);
      onOpenChange?.(nextOpen);
    },
    [onOpenChange],
  );

  return (
    <Sheet open={open} onOpenChange={handleOpenChange}>
      <SheetTrigger asChild>
        <Button variant="outline" className="rounded-2xl">
          <SlidersHorizontalIcon className="size-4" />
          Filtros
          {activeCount ? (
            <Badge className="ml-1 rounded-full bg-primary/15 px-2 py-0 text-primary">
              {activeCount}
            </Badge>
          ) : null}
        </Button>
      </SheetTrigger>
      <SheetContent className="w-full border-l border-border/60 sm:max-w-lg">
        <SheetHeader>
          <SheetTitle>{title}</SheetTitle>
          <SheetDescription>{description}</SheetDescription>
        </SheetHeader>
        <div className="space-y-5 overflow-y-auto px-4 pb-4">{children}</div>
        <SheetFooter className="border-t border-border/60">
          <Button
            variant="outline"
            onClick={() => {
              onClear();
              handleOpenChange(false);
            }}
          >
            Limpar
          </Button>
          <Button
            onClick={() => {
              onApply();
              handleOpenChange(false);
            }}
          >
            Aplicar
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}

function MetricButtonCard({
  card,
  icon,
  onClick,
}: {
  card: DashboardMetricCard;
  icon: React.ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "group w-full rounded-[1.6rem] border border-border/60 bg-card/80 p-5 text-left shadow-xl shadow-black/15 transition hover:border-primary/40 hover:bg-card focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
        card.tone === "danger" && "border-destructive/30",
      )}
      aria-label={card.label}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-2">
          <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
            {card.label}
          </p>
          <p className="text-3xl font-semibold tracking-tight text-foreground">
            {formatMetricValue(card)}
          </p>
          <p className="text-sm text-muted-foreground">{card.description}</p>
        </div>
        <div className="flex size-11 items-center justify-center rounded-2xl bg-primary/10 text-primary transition group-hover:bg-primary/15">
          {icon}
        </div>
      </div>
    </button>
  );
}

function SectionCard({
  title,
  description,
  actions,
  children,
  className,
}: {
  title: string;
  description: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <Card
      className={cn(
        "border-border/60 bg-card/75 shadow-xl shadow-black/15",
        className,
      )}
    >
      <CardHeader className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-2">
          <CardTitle>{title}</CardTitle>
          <CardDescription>{description}</CardDescription>
        </div>
        {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

function LoadingSection({ label }: { label: string }) {
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">Carregando {label}...</p>
      <AnalyticsSectionSkeleton />
    </div>
  );
}

function SummaryDot({
  cx,
  cy,
  stroke,
  onClick,
}: {
  cx?: number;
  cy?: number;
  stroke?: string;
  onClick: () => void;
}) {
  if (cx === undefined || cy === undefined) return null;
  return (
    <circle
      cx={cx}
      cy={cy}
      r={5}
      fill={stroke ?? "hsl(var(--primary))"}
      stroke="hsl(var(--background))"
      strokeWidth={2}
      className="cursor-pointer"
      onClick={onClick}
    />
  );
}

function DashboardPageContent() {
  const currentMonth = React.useMemo(() => new Date(), []);
  const currentMonthStart = React.useMemo(
    () => new Date(currentMonth.getFullYear(), currentMonth.getMonth(), 1),
    [currentMonth],
  );
  const [summaryFilters, setSummaryFilters] = React.useState<SummaryFilters>({
    competencia: currentMonth,
    status: "todos",
  });
  const [summaryDraft, setSummaryDraft] = React.useState(summaryFilters);
  const [treasuryFilters, setTreasuryFilters] = React.useState<TreasuryFilters>(
    {
      competencia: currentMonth,
    },
  );
  const [treasuryDraft, setTreasuryDraft] = React.useState(treasuryFilters);
  const [newAssociadosFilters, setNewAssociadosFilters] =
    React.useState<NewAssociadosFilters>({
      dateStart: currentMonthStart,
      dateEnd: currentMonth,
      status: "todos",
    });
  const [newAssociadosDraft, setNewAssociadosDraft] =
    React.useState(newAssociadosFilters);
  const [agentFilters, setAgentFilters] = React.useState<AgentFilters>({
    dateStart: currentMonthStart,
    dateEnd: currentMonth,
  });
  const [agentDraft, setAgentDraft] = React.useState(agentFilters);
  const [detailState, setDetailState] = React.useState<DetailState | null>(
    null,
  );
  const [exportingSection, setExportingSection] =
    React.useState<DashboardSection | null>(null);

  const summaryQueryParams = React.useMemo<Record<string, string | undefined>>(
    () => ({
      competencia: toMonthId(summaryFilters.competencia),
      date_start: toIsoDate(summaryFilters.dateStart),
      date_end: toIsoDate(summaryFilters.dateEnd),
      status:
        summaryFilters.status === "todos" ? undefined : summaryFilters.status,
    }),
    [summaryFilters],
  );

  const treasuryQueryParams = React.useMemo<Record<string, string | undefined>>(
    () => ({
      competencia: toMonthId(treasuryFilters.competencia),
    }),
    [treasuryFilters],
  );

  const newAssociadosQueryParams = React.useMemo<
    Record<string, string | undefined>
  >(
    () => ({
      date_start: toIsoDate(newAssociadosFilters.dateStart),
      date_end: toIsoDate(newAssociadosFilters.dateEnd),
      status:
        newAssociadosFilters.status === "todos"
          ? undefined
          : newAssociadosFilters.status,
    }),
    [newAssociadosFilters],
  );

  const agentQueryParams = React.useMemo<Record<string, string | undefined>>(
    () => ({
      date_start: toIsoDate(agentFilters.dateStart),
      date_end: toIsoDate(agentFilters.dateEnd),
    }),
    [agentFilters],
  );

  const summaryQuery = useQuery({
    queryKey: [
      "dashboard-admin-summary",
      toMonthId(summaryFilters.competencia),
      toIsoDate(summaryFilters.dateStart),
      toIsoDate(summaryFilters.dateEnd),
      summaryFilters.status,
    ],
    queryFn: () =>
      apiFetch<DashboardResumoGeral>("dashboard/admin/resumo-geral", {
        query: summaryQueryParams,
      }),
  });

  const treasuryQuery = useQuery({
    queryKey: [
      "dashboard-admin-treasury",
      toMonthId(treasuryFilters.competencia),
    ],
    queryFn: () =>
      apiFetch<DashboardTesouraria>("dashboard/admin/tesouraria", {
        query: treasuryQueryParams,
      }),
  });

  const newAssociadosQuery = useQuery({
    queryKey: [
      "dashboard-admin-new-associados",
      toIsoDate(newAssociadosFilters.dateStart),
      toIsoDate(newAssociadosFilters.dateEnd),
      newAssociadosFilters.status,
    ],
    queryFn: () =>
      apiFetch<DashboardNovosAssociados>("dashboard/admin/novos-associados", {
        query: newAssociadosQueryParams,
      }),
  });

  const agentsQuery = useQuery({
    queryKey: [
      "dashboard-admin-agents",
      toIsoDate(agentFilters.dateStart),
      toIsoDate(agentFilters.dateEnd),
    ],
    queryFn: () =>
      apiFetch<DashboardAgentes>("dashboard/admin/agentes", {
        query: agentQueryParams,
      }),
  });

  const detailQuery = useQuery({
    queryKey: ["dashboard-admin-detail", detailState],
    queryFn: () =>
      apiFetch<PaginatedDashboardDetailRowList>("dashboard/admin/detalhes", {
        query: {
          section: detailState?.section,
          metric: detailState?.metric,
          page_size: "all",
          ...detailState?.query,
        },
      }),
    enabled: Boolean(detailState),
  });

  const openDetail = React.useCallback(
    (
      section: DetailState["section"],
      metric: string,
      title: string,
      description: string,
      query: Record<string, string | undefined>,
    ) => {
      setDetailState({ section, metric, title, description, query });
    },
    [],
  );

  const fetchDetailRows = React.useCallback(
    async (
      section: DashboardSection,
      metrics: SectionExportMetric[],
      query: Record<string, string | undefined>,
    ) => {
      const payloads = await Promise.all(
        metrics.map(async ({ label, metric }) => {
          const response = await apiFetch<PaginatedDashboardDetailRowList>(
            "dashboard/admin/detalhes",
            {
              query: {
                section,
                metric,
                page_size: "all",
                ...query,
              },
            },
          );

          return response.results.map((row) => ({
            ...row,
            indicador: label,
          }));
        }),
      );

      return payloads.flat();
    },
    [],
  );

  const handleSectionExport = React.useCallback(
    async ({
      format,
      section,
      title,
      filenameBase,
      metrics,
      query,
    }: {
      format: "csv" | "pdf" | "excel";
      section: DashboardSection;
      title: string;
      filenameBase: string;
      metrics: SectionExportMetric[];
      query: Record<string, string | undefined>;
    }) => {
      if (!metrics.length) {
        toast.error("Nenhum dado disponivel para exportacao nesta secao.");
        return;
      }

      setExportingSection(section);

      try {
        const rows = await fetchDetailRows(section, metrics, query);
        if (!rows.length) {
          toast.error("Nenhum registro encontrado para exportacao.");
          return;
        }

        exportRows(format, title, filenameBase, SECTION_EXPORT_COLUMNS, rows);
      } catch (error) {
        toast.error(
          error instanceof Error
            ? error.message
            : "Nao foi possivel exportar a secao.",
        );
      } finally {
        setExportingSection((current) =>
          current === section ? null : current,
        );
      }
    },
    [fetchDetailRows],
  );

  const summaryExportMetrics = React.useMemo(
    () =>
      summaryQuery.data ? buildSummaryExportMetrics(summaryQuery.data) : [],
    [summaryQuery.data],
  );

  const treasuryExportMetrics = React.useMemo(
    () =>
      treasuryQuery.data ? buildTreasuryExportMetrics(treasuryQuery.data) : [],
    [treasuryQuery.data],
  );

  const newAssociadosExportMetrics = React.useMemo(
    () =>
      newAssociadosQuery.data
        ? buildNewAssociadosExportMetrics(newAssociadosQuery.data)
        : [],
    [newAssociadosQuery.data],
  );

  const agentsExportMetrics = React.useMemo(
    () => (agentsQuery.data ? buildAgentsExportMetrics(agentsQuery.data) : []),
    [agentsQuery.data],
  );

  const summaryActiveFilters =
    countActiveFilters({
      dateStart: summaryFilters.dateStart,
      dateEnd: summaryFilters.dateEnd,
      status: summaryFilters.status,
    }) + (hasSameMonth(summaryFilters.competencia, currentMonth) ? 0 : 1);

  const newAssociadosActiveFilters =
    countActiveFilters({
      status: newAssociadosFilters.status,
    }) +
    (newAssociadosFilters.dateStart &&
    hasSameDate(newAssociadosFilters.dateStart, currentMonthStart)
      ? 0
      : newAssociadosFilters.dateStart
        ? 1
        : 0) +
    (newAssociadosFilters.dateEnd &&
    hasSameDate(newAssociadosFilters.dateEnd, currentMonth)
      ? 0
      : newAssociadosFilters.dateEnd
        ? 1
        : 0);

  const agentActiveFilters =
    (agentFilters.dateStart &&
    hasSameDate(agentFilters.dateStart, currentMonthStart)
      ? 0
      : agentFilters.dateStart
        ? 1
        : 0) +
    (agentFilters.dateEnd && hasSameDate(agentFilters.dateEnd, currentMonth)
      ? 0
      : agentFilters.dateEnd
        ? 1
        : 0);
  const treasuryActiveFilters = hasSameMonth(
    treasuryFilters.competencia,
    currentMonth,
  )
    ? 0
    : 1;

  const summaryTitle = formatLongMonthYear(summaryFilters.competencia);
  const treasuryTitle = formatLongMonthYear(treasuryFilters.competencia);

  const topAgentSeries = React.useMemo(() => {
    return (agentsQuery.data?.ranking ?? []).slice(0, 3);
  }, [agentsQuery.data?.ranking]);

  const radarData = React.useMemo(() => {
    const metrics = [
      { key: "efetivados", label: "Efetivados" },
      { key: "cadastros", label: "Cadastros" },
      { key: "em_processo", label: "Em processo" },
      { key: "renovados", label: "Renovados" },
      { key: "inadimplentes", label: "Inadimplentes" },
    ] as const;

    return metrics.map((metric) => ({
      metric: metric.label,
      ...Object.fromEntries(
        topAgentSeries.map((agent) => [
          `agent_${agent.agent_id}`,
          agent[metric.key],
        ]),
      ),
    }));
  }, [topAgentSeries]);

  const radarConfig = React.useMemo<ChartConfig>(() => {
    return Object.fromEntries(
      topAgentSeries.map((agent, index) => [
        `agent_${agent.agent_id}`,
        {
          label: agent.agent_name,
          color: AGENT_CHART_COLORS[index % AGENT_CHART_COLORS.length],
        },
      ]),
    );
  }, [topAgentSeries]);

  const detailRows = detailQuery.data?.results ?? [];

  return (
    <>
      <div className="space-y-8 pb-8">
        <section className="space-y-3 rounded-[2rem] border border-border/60 bg-[linear-gradient(135deg,rgba(251,146,60,0.18),rgba(12,18,28,0.94))] p-6 shadow-2xl shadow-black/20">
          <Badge
            variant="outline"
            className="w-fit border-white/15 bg-white/5 text-white"
          >
            ADMIN
          </Badge>
          <div className="space-y-2">
            <h1 className="text-3xl font-semibold tracking-tight text-white md:text-[2.5rem]">
              Dashboard Executivo
            </h1>
            <p className="max-w-3xl text-sm text-white/75">
              Leitura consolidada da operacao, tesouraria, fluxo de efetivacao,
              renovacao e ranking de agentes em uma unica rota administrativa.
            </p>
          </div>
        </section>

        <SectionCard
          title="Tesouraria"
          description="Recebimentos, baixas, inadimplencia quitada e projecao para a competencia atual e os ciclos seguintes."
          actions={
            <>
              <SectionFilterButton
                title="Filtros da tesouraria"
                description="Defina a competencia financeira analisada no topo do dashboard."
                activeCount={treasuryActiveFilters}
                onOpenChange={(open) => {
                  if (open) setTreasuryDraft(treasuryFilters);
                }}
                onClear={() =>
                  setTreasuryDraft({
                    competencia: currentMonth,
                  })
                }
                onApply={() => setTreasuryFilters(treasuryDraft)}
              >
                <FilterField label="Competencia">
                  <CalendarCompetencia
                    value={treasuryDraft.competencia}
                    onChange={(value) =>
                      setTreasuryDraft((current) => ({
                        ...current,
                        competencia: value,
                      }))
                    }
                  />
                </FilterField>
              </SectionFilterButton>
              <ExportButton
                disabled={
                  !treasuryQuery.data || exportingSection === "treasury"
                }
                label={
                  exportingSection === "treasury" ? "Exportando..." : "Exportar"
                }
                onExport={(format) =>
                  void handleSectionExport({
                    format,
                    section: "treasury",
                    title: `Tesouraria - ${treasuryTitle}`,
                    filenameBase: `dashboard-tesouraria-${toMonthId(treasuryFilters.competencia)}`,
                    metrics: treasuryExportMetrics,
                    query: treasuryQueryParams,
                  })
                }
              />
            </>
          }
        >
          {treasuryQuery.isLoading || !treasuryQuery.data ? (
            <LoadingSection label="tesouraria" />
          ) : (
            <div className="space-y-6">
              <div className="flex items-center justify-between rounded-[1.4rem] border border-border/60 bg-background/40 px-4 py-3">
                <div>
                  <p className="text-xs uppercase tracking-[0.22em] text-muted-foreground">
                    Competencia
                  </p>
                  <p className="text-lg font-semibold text-foreground">
                    {treasuryTitle}
                  </p>
                </div>
                <p className="text-sm text-muted-foreground">
                  Horizonte: competencia atual + 2 ciclos
                </p>
              </div>

              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {treasuryQuery.data.cards.map((card) => (
                  <MetricButtonCard
                    key={card.key}
                    card={card}
                    icon={<CircleDollarSignIcon className="size-5" />}
                    onClick={() =>
                      openDetail(
                        "treasury",
                        card.detail_metric,
                        `${card.label} em ${treasuryTitle}`,
                        card.description,
                        treasuryQueryParams,
                      )
                    }
                  />
                ))}
              </div>

              <div className="grid gap-6 xl:grid-cols-3">
                <SectionCard
                  title="Recebido x projetado"
                  description="Serie principal da tesouraria com foco no fluxo esperado para o mes atual e dois ciclos seguintes."
                  className="xl:col-span-2"
                >
                  <ChartContainer
                    config={TREASURY_CHART_CONFIG}
                    className="h-[320px] w-full"
                  >
                    <AreaChart data={treasuryQuery.data.projection_area}>
                      <CartesianGrid vertical={false} />
                      <XAxis
                        dataKey="label"
                        tickLine={false}
                        axisLine={false}
                      />
                      <ChartTooltip
                        content={
                          <ChartTooltipContent
                            formatter={(value, name, item) => [
                              formatCurrency(Number(value)),
                              TREASURY_CHART_CONFIG[
                                String(
                                  item.dataKey,
                                ) as keyof typeof TREASURY_CHART_CONFIG
                              ]?.label ?? name,
                            ]}
                          />
                        }
                      />
                      <ChartLegend content={<ChartLegendContent />} />
                      <Area
                        dataKey="recebido"
                        type="monotone"
                        fill="var(--color-recebido)"
                        fillOpacity={0.22}
                        stroke="var(--color-recebido)"
                        strokeWidth={2}
                        dot={(props) => (
                          <SummaryDot
                            key={`recebido-${props.index}-${props.cx}-${props.cy}`}
                            cx={props.cx}
                            cy={props.cy}
                            stroke="var(--color-recebido)"
                            onClick={() =>
                              openDetail(
                                "treasury",
                                props.payload.recebido_metric,
                                `Recebidos em ${props.payload.label}`,
                                "Baixas financeiras que compoem a linha de recebimento.",
                                treasuryQueryParams,
                              )
                            }
                          />
                        )}
                      />
                      <Area
                        dataKey="projetado"
                        type="monotone"
                        fill="var(--color-projetado)"
                        fillOpacity={0.18}
                        stroke="var(--color-projetado)"
                        strokeWidth={2}
                        dot={(props) => (
                          <SummaryDot
                            key={`projetado-${props.index}-${props.cx}-${props.cy}`}
                            cx={props.cx}
                            cy={props.cy}
                            stroke="var(--color-projetado)"
                            onClick={() =>
                              openDetail(
                                "treasury",
                                props.payload.projetado_metric,
                                `Projecao em ${props.payload.label}`,
                                "Parcelas elegiveis que sustentam a projecao financeira.",
                                treasuryQueryParams,
                              )
                            }
                          />
                        )}
                      />
                    </AreaChart>
                  </ChartContainer>
                </SectionCard>

                <SectionCard
                  title="Composicao financeira"
                  description="Peso relativo do recebido atual, pendencia da competencia e projecao futura."
                >
                  <ChartContainer
                    config={TREASURY_CHART_CONFIG}
                    className="h-[320px] w-full"
                  >
                    <RadialBarChart
                      data={treasuryQuery.data.composition_radial}
                      innerRadius={28}
                      outerRadius={120}
                      startAngle={180}
                      endAngle={0}
                    >
                      <ChartTooltip
                        content={
                          <ChartTooltipContent
                            formatter={(value, name) => [
                              formatCurrency(Number(value)),
                              String(name),
                            ]}
                          />
                        }
                      />
                      <ChartLegend content={<ChartLegendContent />} />
                      <RadialBar background dataKey="value">
                        {treasuryQuery.data.composition_radial.map(
                          (item, index) => (
                            <Cell
                              key={item.key}
                              fill={
                                AGENT_CHART_COLORS[
                                  index % AGENT_CHART_COLORS.length
                                ]
                              }
                              className="cursor-pointer"
                              onClick={() =>
                                openDetail(
                                  "treasury",
                                  item.detail_metric,
                                  `${item.label} em ${treasuryTitle}`,
                                  "Detalhamento financeiro da composicao radial.",
                                  treasuryQueryParams,
                                )
                              }
                            />
                          ),
                        )}
                      </RadialBar>
                    </RadialBarChart>
                  </ChartContainer>
                </SectionCard>
              </div>

              <SectionCard
                title="Movimentos do periodo"
                description="Baixas por importacao e manual, inadimplentes quitados e contratos novos do mes analisado."
              >
                <ChartContainer
                  config={TREASURY_CHART_CONFIG}
                  className="h-[280px] w-full"
                >
                  <BarChart data={treasuryQuery.data.movement_bars}>
                    <CartesianGrid vertical={false} />
                    <XAxis dataKey="label" tickLine={false} axisLine={false} />
                    <ChartTooltip content={<ChartTooltipContent />} />
                    <Bar dataKey="value" radius={[14, 14, 6, 6]}>
                      {treasuryQuery.data.movement_bars.map((item, index) => (
                        <Cell
                          key={item.key}
                          fill={
                            AGENT_CHART_COLORS[
                              index % AGENT_CHART_COLORS.length
                            ]
                          }
                          className="cursor-pointer"
                          onClick={() =>
                            openDetail(
                              "treasury",
                              item.detail_metric,
                              `${item.label} em ${treasuryTitle}`,
                              "Linhas que sustentam o indicador financeiro selecionado.",
                              treasuryQueryParams,
                            )
                          }
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ChartContainer>
              </SectionCard>
            </div>
          )}
        </SectionCard>

        <SectionCard
          title="KPIs gerais"
          description="Panorama do cadastro, efetivacao e renovacao com detalhamento direto em tabela."
          actions={
            <>
              <SectionFilterButton
                title="Filtros do panorama geral"
                description="Controle a competencia das renovacoes e o recorte de cadastros do panorama executivo."
                activeCount={summaryActiveFilters}
                onOpenChange={(open) => {
                  if (open) setSummaryDraft(summaryFilters);
                }}
                onClear={() =>
                  setSummaryDraft({
                    competencia: currentMonth,
                    status: "todos",
                  })
                }
                onApply={() => setSummaryFilters(summaryDraft)}
              >
                <FilterField label="Competencia de renovacao">
                  <CalendarCompetencia
                    value={summaryDraft.competencia}
                    onChange={(value) =>
                      setSummaryDraft((current) => ({
                        ...current,
                        competencia: value,
                      }))
                    }
                  />
                </FilterField>
                <div className="grid gap-4 md:grid-cols-2">
                  <FilterField label="Data inicial">
                    <DatePicker
                      value={summaryDraft.dateStart}
                      onChange={(value) =>
                        setSummaryDraft((current) => ({
                          ...current,
                          dateStart: value,
                        }))
                      }
                      placeholder="Data inicial"
                    />
                  </FilterField>
                  <FilterField label="Data final">
                    <DatePicker
                      value={summaryDraft.dateEnd}
                      onChange={(value) =>
                        setSummaryDraft((current) => ({
                          ...current,
                          dateEnd: value,
                        }))
                      }
                      placeholder="Data final"
                    />
                  </FilterField>
                </div>
                <FilterField label="Status do associado">
                  <Select
                    value={summaryDraft.status}
                    onValueChange={(value) =>
                      setSummaryDraft((current) => ({
                        ...current,
                        status: value,
                      }))
                    }
                  >
                    <SelectTrigger className="rounded-2xl bg-card/60">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {STATUS_OPTIONS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </FilterField>
              </SectionFilterButton>
              <ExportButton
                disabled={!summaryQuery.data || exportingSection === "summary"}
                label={
                  exportingSection === "summary" ? "Exportando..." : "Exportar"
                }
                onExport={(format) =>
                  void handleSectionExport({
                    format,
                    section: "summary",
                    title: `Panorama geral - ${summaryTitle}`,
                    filenameBase: `dashboard-panorama-${toMonthId(summaryFilters.competencia)}`,
                    metrics: summaryExportMetrics,
                    query: summaryQueryParams,
                  })
                }
              />
            </>
          }
        >
          {summaryQuery.isLoading || !summaryQuery.data ? (
            <LoadingSection label="panorama geral" />
          ) : (
            <div className="space-y-6">
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                {summaryQuery.data.kpis.map((card) => (
                  <MetricButtonCard
                    key={card.key}
                    card={card}
                    icon={<Users2Icon className="size-5" />}
                    onClick={() =>
                      openDetail(
                        "summary",
                        card.detail_metric,
                        `${card.label} em ${summaryTitle}`,
                        card.description,
                        summaryQueryParams,
                      )
                    }
                  />
                ))}
              </div>

              <div className="grid gap-6 xl:grid-cols-3">
                <SectionCard
                  title="Fluxo do cadastro ate a renovacao"
                  description="Volumetria das etapas mais relevantes do funil operacional."
                  className="xl:col-span-2"
                >
                  <ChartContainer
                    config={SUMMARY_CHART_CONFIG}
                    className="h-[280px] w-full"
                  >
                    <BarChart data={summaryQuery.data.flow_bars}>
                      <CartesianGrid vertical={false} />
                      <XAxis
                        dataKey="label"
                        tickLine={false}
                        axisLine={false}
                      />
                      <ChartTooltip content={<ChartTooltipContent />} />
                      <Bar dataKey="value" radius={[14, 14, 6, 6]}>
                        {summaryQuery.data.flow_bars.map((item, index) => (
                          <Cell
                            key={item.key}
                            fill={
                              AGENT_CHART_COLORS[
                                index % AGENT_CHART_COLORS.length
                              ]
                            }
                            className="cursor-pointer"
                            onClick={() =>
                              openDetail(
                                "summary",
                                item.detail_metric,
                                `${item.label} em ${summaryTitle}`,
                                "Detalhamento do volume exibido no grafico de barras.",
                                summaryQueryParams,
                              )
                            }
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ChartContainer>
                </SectionCard>

                <SectionCard
                  title="Status da base"
                  description="Distribuicao percentual por status do associado."
                >
                  <ChartContainer
                    config={SUMMARY_CHART_CONFIG}
                    className="h-[280px] w-full"
                  >
                    <PieChart>
                      <ChartTooltip
                        content={<ChartTooltipContent nameKey="label" />}
                      />
                      <ChartLegend
                        content={<ChartLegendContent nameKey="label" />}
                      />
                      <Pie
                        data={summaryQuery.data.status_pie}
                        dataKey="value"
                        nameKey="label"
                        innerRadius={58}
                        outerRadius={92}
                        strokeWidth={4}
                      >
                        {summaryQuery.data.status_pie.map((item, index) => (
                          <Cell
                            key={item.key}
                            fill={
                              AGENT_CHART_COLORS[
                                index % AGENT_CHART_COLORS.length
                              ]
                            }
                            className="cursor-pointer"
                            onClick={() =>
                              openDetail(
                                "summary",
                                item.detail_metric,
                                `${item.label} em ${summaryTitle}`,
                                "Detalhamento do segmento selecionado na pizza de status.",
                                summaryQueryParams,
                              )
                            }
                          />
                        ))}
                      </Pie>
                    </PieChart>
                  </ChartContainer>
                </SectionCard>
              </div>

              <SectionCard
                title="Tendencia operacional"
                description="Serie mensal de cadastros, efetivacoes e renovacoes dos ultimos seis meses."
              >
                <ChartContainer
                  config={SUMMARY_CHART_CONFIG}
                  className="h-[300px] w-full"
                >
                  <LineChart data={summaryQuery.data.trend_lines}>
                    <CartesianGrid vertical={false} />
                    <XAxis dataKey="label" tickLine={false} axisLine={false} />
                    <ChartTooltip
                      content={
                        <ChartTooltipContent
                          formatter={(value, name) => [
                            String(value),
                            String(name),
                          ]}
                        />
                      }
                    />
                    <ChartLegend content={<ChartLegendContent />} />
                    <Line
                      dataKey="cadastros"
                      stroke="var(--color-cadastros)"
                      strokeWidth={2}
                      dot={(props) => (
                        <SummaryDot
                          key={`summary-cadastros-${props.index}-${props.cx}-${props.cy}`}
                          cx={props.cx}
                          cy={props.cy}
                          stroke="var(--color-cadastros)"
                          onClick={() =>
                            openDetail(
                              "summary",
                              props.payload.cadastros_metric,
                              `Cadastros em ${props.payload.label}`,
                              "Associados criados na serie temporal selecionada.",
                              summaryQueryParams,
                            )
                          }
                        />
                      )}
                    />
                    <Line
                      dataKey="efetivados"
                      stroke="var(--color-efetivados)"
                      strokeWidth={2}
                      dot={(props) => (
                        <SummaryDot
                          key={`summary-efetivados-${props.index}-${props.cx}-${props.cy}`}
                          cx={props.cx}
                          cy={props.cy}
                          stroke="var(--color-efetivados)"
                          onClick={() =>
                            openDetail(
                              "summary",
                              props.payload.efetivados_metric,
                              `Efetivados em ${props.payload.label}`,
                              "Contratos efetivados no ponto da serie selecionado.",
                              summaryQueryParams,
                            )
                          }
                        />
                      )}
                    />
                    <Line
                      dataKey="renovacoes"
                      stroke="var(--color-renovacoes)"
                      strokeWidth={2}
                      dot={(props) => (
                        <SummaryDot
                          key={`summary-renovacoes-${props.index}-${props.cx}-${props.cy}`}
                          cx={props.cx}
                          cy={props.cy}
                          stroke="var(--color-renovacoes)"
                          onClick={() =>
                            openDetail(
                              "summary",
                              props.payload.renovacoes_metric,
                              `Renovacoes em ${props.payload.label}`,
                              "Ciclos renovados no ponto da serie selecionado.",
                              summaryQueryParams,
                            )
                          }
                        />
                      )}
                    />
                  </LineChart>
                </ChartContainer>
              </SectionCard>
            </div>
          )}
        </SectionCard>

        <SectionCard
          title="Novos associados"
          description="Volume, status e conversao dos novos cadastros no periodo filtrado."
          actions={
            <>
              <SectionFilterButton
                title="Filtros de novos associados"
                description="Defina o periodo e o status para a secao de novos associados."
                activeCount={newAssociadosActiveFilters}
                onOpenChange={(open) => {
                  if (open) setNewAssociadosDraft(newAssociadosFilters);
                }}
                onClear={() =>
                  setNewAssociadosDraft({
                    dateStart: currentMonthStart,
                    dateEnd: currentMonth,
                    status: "todos",
                  })
                }
                onApply={() => setNewAssociadosFilters(newAssociadosDraft)}
              >
                <div className="grid gap-4 md:grid-cols-2">
                  <FilterField label="Data inicial">
                    <DatePicker
                      value={newAssociadosDraft.dateStart}
                      onChange={(value) =>
                        setNewAssociadosDraft((current) => ({
                          ...current,
                          dateStart: value,
                        }))
                      }
                      placeholder="Data inicial"
                    />
                  </FilterField>
                  <FilterField label="Data final">
                    <DatePicker
                      value={newAssociadosDraft.dateEnd}
                      onChange={(value) =>
                        setNewAssociadosDraft((current) => ({
                          ...current,
                          dateEnd: value,
                        }))
                      }
                      placeholder="Data final"
                    />
                  </FilterField>
                </div>
                <FilterField label="Status do associado">
                  <Select
                    value={newAssociadosDraft.status}
                    onValueChange={(value) =>
                      setNewAssociadosDraft((current) => ({
                        ...current,
                        status: value,
                      }))
                    }
                  >
                    <SelectTrigger className="rounded-2xl bg-card/60">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {STATUS_OPTIONS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </FilterField>
              </SectionFilterButton>
              <ExportButton
                disabled={
                  !newAssociadosQuery.data ||
                  exportingSection === "new-associados"
                }
                label={
                  exportingSection === "new-associados"
                    ? "Exportando..."
                    : "Exportar"
                }
                onExport={(format) =>
                  void handleSectionExport({
                    format,
                    section: "new-associados",
                    title: "Novos associados",
                    filenameBase: "dashboard-novos-associados",
                    metrics: newAssociadosExportMetrics,
                    query: newAssociadosQueryParams,
                  })
                }
              />
            </>
          }
        >
          {newAssociadosQuery.isLoading || !newAssociadosQuery.data ? (
            <LoadingSection label="novos associados" />
          ) : (
            <div className="space-y-6">
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                {newAssociadosQuery.data.cards.map((card) => (
                  <MetricButtonCard
                    key={card.key}
                    card={card}
                    icon={<LayoutGridIcon className="size-5" />}
                    onClick={() =>
                      openDetail(
                        "new-associados",
                        card.detail_metric,
                        `${card.label} no periodo`,
                        card.description,
                        newAssociadosQueryParams,
                      )
                    }
                  />
                ))}
              </div>

              <div className="grid gap-6 xl:grid-cols-3">
                <SectionCard
                  title="Cadastros x efetivacoes"
                  description="Serie temporal dos novos associados e das efetivacoes dentro do mesmo recorte."
                  className="xl:col-span-2"
                >
                  <ChartContainer
                    config={SUMMARY_CHART_CONFIG}
                    className="h-[300px] w-full"
                  >
                    <AreaChart data={newAssociadosQuery.data.trend_area}>
                      <CartesianGrid vertical={false} />
                      <XAxis
                        dataKey="label"
                        tickLine={false}
                        axisLine={false}
                      />
                      <ChartTooltip content={<ChartTooltipContent />} />
                      <ChartLegend content={<ChartLegendContent />} />
                      <Area
                        dataKey="cadastros"
                        type="monotone"
                        stroke="var(--color-cadastros)"
                        fill="var(--color-cadastros)"
                        fillOpacity={0.2}
                        dot={(props) => (
                          <SummaryDot
                            key={`new-associados-cadastros-${props.index}-${props.cx}-${props.cy}`}
                            cx={props.cx}
                            cy={props.cy}
                            stroke="var(--color-cadastros)"
                            onClick={() =>
                              openDetail(
                                "new-associados",
                                props.payload.cadastros_metric,
                                `Cadastros em ${props.payload.label}`,
                                "Novos associados criados no ponto da serie.",
                                newAssociadosQueryParams,
                              )
                            }
                          />
                        )}
                      />
                      <Area
                        dataKey="efetivados"
                        type="monotone"
                        stroke="var(--color-efetivados)"
                        fill="var(--color-efetivados)"
                        fillOpacity={0.18}
                        dot={(props) => (
                          <SummaryDot
                            key={`new-associados-efetivados-${props.index}-${props.cx}-${props.cy}`}
                            cx={props.cx}
                            cy={props.cy}
                            stroke="var(--color-efetivados)"
                            onClick={() =>
                              openDetail(
                                "new-associados",
                                props.payload.efetivados_metric,
                                `Efetivados em ${props.payload.label}`,
                                "Novos associados que chegaram a efetivacao no periodo selecionado.",
                                newAssociadosQueryParams,
                              )
                            }
                          />
                        )}
                      />
                    </AreaChart>
                  </ChartContainer>
                </SectionCard>

                <SectionCard
                  title="Distribuicao por status"
                  description="Como os novos cadastros estao distribuídos por status."
                >
                  <ChartContainer
                    config={SUMMARY_CHART_CONFIG}
                    className="h-[300px] w-full"
                  >
                    <PieChart>
                      <ChartTooltip
                        content={<ChartTooltipContent nameKey="label" />}
                      />
                      <ChartLegend
                        content={<ChartLegendContent nameKey="label" />}
                      />
                      <Pie
                        data={newAssociadosQuery.data.status_pie}
                        dataKey="value"
                        nameKey="label"
                        innerRadius={54}
                        outerRadius={92}
                        strokeWidth={4}
                      >
                        {newAssociadosQuery.data.status_pie.map(
                          (item, index) => (
                            <Cell
                              key={item.key}
                              fill={
                                AGENT_CHART_COLORS[
                                  index % AGENT_CHART_COLORS.length
                                ]
                              }
                              className="cursor-pointer"
                              onClick={() =>
                                openDetail(
                                  "new-associados",
                                  item.detail_metric,
                                  `${item.label} no periodo`,
                                  "Detalhamento do status selecionado.",
                                  newAssociadosQueryParams,
                                )
                              }
                            />
                          ),
                        )}
                      </Pie>
                    </PieChart>
                  </ChartContainer>
                </SectionCard>
              </div>
            </div>
          )}
        </SectionCard>

        <SectionCard
          title="Agentes"
          description="Ranking por efetivacao, comparacao por radar e participacao relativa dos agentes."
          actions={
            <>
              <SectionFilterButton
                title="Filtros de agentes"
                description="Defina o periodo do ranking e das comparacoes entre agentes."
                activeCount={agentActiveFilters}
                onOpenChange={(open) => {
                  if (open) setAgentDraft(agentFilters);
                }}
                onClear={() =>
                  setAgentDraft({
                    dateStart: currentMonthStart,
                    dateEnd: currentMonth,
                  })
                }
                onApply={() => setAgentFilters(agentDraft)}
              >
                <div className="grid gap-4 md:grid-cols-2">
                  <FilterField label="Data inicial">
                    <DatePicker
                      value={agentDraft.dateStart}
                      onChange={(value) =>
                        setAgentDraft((current) => ({
                          ...current,
                          dateStart: value,
                        }))
                      }
                      placeholder="Data inicial"
                    />
                  </FilterField>
                  <FilterField label="Data final">
                    <DatePicker
                      value={agentDraft.dateEnd}
                      onChange={(value) =>
                        setAgentDraft((current) => ({
                          ...current,
                          dateEnd: value,
                        }))
                      }
                      placeholder="Data final"
                    />
                  </FilterField>
                </div>
              </SectionFilterButton>
              <ExportButton
                disabled={!agentsQuery.data || exportingSection === "agentes"}
                label={
                  exportingSection === "agentes" ? "Exportando..." : "Exportar"
                }
                onExport={(format) =>
                  void handleSectionExport({
                    format,
                    section: "agentes",
                    title: "Ranking de agentes",
                    filenameBase: "dashboard-agentes",
                    metrics: agentsExportMetrics,
                    query: agentQueryParams,
                  })
                }
              />
            </>
          }
        >
          {agentsQuery.isLoading || !agentsQuery.data ? (
            <LoadingSection label="agentes" />
          ) : (
            <div className="space-y-6">
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                {agentsQuery.data.cards.map((card) => (
                  <MetricButtonCard
                    key={card.key}
                    card={card}
                    icon={<Users2Icon className="size-5" />}
                    onClick={() =>
                      openDetail(
                        "agentes",
                        card.detail_metric,
                        `${card.label} no ranking`,
                        card.description,
                        agentQueryParams,
                      )
                    }
                  />
                ))}
              </div>

              <div className="grid gap-6 xl:grid-cols-3">
                <SectionCard
                  title="Ranking por efetivacao"
                  description="Top agentes do periodo com foco em contratos efetivados."
                  className="xl:col-span-2"
                >
                  <ChartContainer
                    config={{
                      efetivados: {
                        label: "Efetivados",
                        color: "hsl(var(--primary))",
                      },
                    }}
                    className="h-[320px] w-full"
                  >
                    <BarChart data={agentsQuery.data.ranking}>
                      <CartesianGrid vertical={false} />
                      <XAxis
                        dataKey="agent_name"
                        tickLine={false}
                        axisLine={false}
                        hide
                      />
                      <ChartTooltip content={<ChartTooltipContent />} />
                      <Bar dataKey="efetivados" radius={[14, 14, 6, 6]}>
                        {agentsQuery.data.ranking.map((item, index) => (
                          <Cell
                            key={item.agent_id}
                            fill={
                              AGENT_CHART_COLORS[
                                index % AGENT_CHART_COLORS.length
                              ]
                            }
                            className="cursor-pointer"
                            onClick={() =>
                              openDetail(
                                "agentes",
                                item.detail_metric,
                                `${item.agent_name} no ranking`,
                                "Contratos efetivados que sustentam a posicao do agente.",
                                agentQueryParams,
                              )
                            }
                          />
                        ))}
                      </Bar>
                    </BarChart>
                  </ChartContainer>
                  <div className="mt-4 grid gap-2 md:grid-cols-2">
                    {agentsQuery.data.ranking.map((item, index) => (
                      <button
                        key={item.agent_id}
                        type="button"
                        className="flex items-center justify-between rounded-2xl border border-border/60 bg-background/40 px-4 py-3 text-left hover:border-primary/40"
                        onClick={() =>
                          openDetail(
                            "agentes",
                            item.detail_metric,
                            `${item.agent_name} no ranking`,
                            "Contratos efetivados que sustentam a posicao do agente.",
                            agentQueryParams,
                          )
                        }
                      >
                        <div className="flex items-center gap-3">
                          <span
                            className="inline-flex size-8 items-center justify-center rounded-full text-xs font-semibold text-background"
                            style={{
                              backgroundColor:
                                AGENT_CHART_COLORS[
                                  index % AGENT_CHART_COLORS.length
                                ],
                            }}
                          >
                            {index + 1}
                          </span>
                          <div>
                            <p className="font-medium text-foreground">
                              {item.agent_name}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {item.cadastros} cadastros · {item.renovados}{" "}
                              renovados
                            </p>
                          </div>
                        </div>
                        <p className="text-lg font-semibold text-foreground">
                          {item.efetivados}
                        </p>
                      </button>
                    ))}
                  </div>
                </SectionCard>

                <SectionCard
                  title="Participacao no total"
                  description="Percentual de participacao das efetivacoes por agente."
                >
                  <ChartContainer
                    config={radarConfig}
                    className="h-[320px] w-full"
                  >
                    <RadialBarChart
                      data={agentsQuery.data.ranking}
                      innerRadius={24}
                      outerRadius={120}
                      startAngle={180}
                      endAngle={0}
                    >
                      <ChartTooltip
                        content={
                          <ChartTooltipContent
                            formatter={(value) => [`${value}%`, "Participacao"]}
                          />
                        }
                      />
                      <RadialBar background dataKey="participacao">
                        {agentsQuery.data.ranking.map((item, index) => (
                          <Cell
                            key={item.agent_id}
                            fill={
                              AGENT_CHART_COLORS[
                                index % AGENT_CHART_COLORS.length
                              ]
                            }
                            className="cursor-pointer"
                            onClick={() =>
                              openDetail(
                                "agentes",
                                item.detail_metric,
                                `${item.agent_name} na participacao`,
                                "Contratos efetivados relacionados a participacao do agente.",
                                agentQueryParams,
                              )
                            }
                          />
                        ))}
                      </RadialBar>
                    </RadialBarChart>
                  </ChartContainer>
                </SectionCard>
              </div>

              <SectionCard
                title="Comparacao multidimensional"
                description="Radar com as metricas de efetivacao, cadastro, renovacao, processo e inadimplencia dos agentes lideres."
              >
                {topAgentSeries.length ? (
                  <ChartContainer
                    config={radarConfig}
                    className="h-[340px] w-full"
                  >
                    <RadarChart data={radarData}>
                      <ChartTooltip content={<ChartTooltipContent />} />
                      <ChartLegend content={<ChartLegendContent />} />
                      <PolarGrid />
                      <PolarAngleAxis dataKey="metric" />
                      {topAgentSeries.map((agent, index) => (
                        <Radar
                          key={agent.agent_id}
                          dataKey={`agent_${agent.agent_id}`}
                          stroke={
                            AGENT_CHART_COLORS[
                              index % AGENT_CHART_COLORS.length
                            ]
                          }
                          fill={
                            AGENT_CHART_COLORS[
                              index % AGENT_CHART_COLORS.length
                            ]
                          }
                          fillOpacity={0.12}
                          onClick={() =>
                            openDetail(
                              "agentes",
                              agent.detail_metric,
                              `${agent.agent_name} no radar`,
                              "Contratos efetivados associados ao agente selecionado no radar.",
                              agentQueryParams,
                            )
                          }
                        />
                      ))}
                    </RadarChart>
                  </ChartContainer>
                ) : (
                  <div className="rounded-[1.5rem] border border-border/60 bg-background/40 px-6 py-12 text-center text-sm text-muted-foreground">
                    Nenhum agente com dados suficientes para o radar no periodo
                    selecionado.
                  </div>
                )}
              </SectionCard>
            </div>
          )}
        </SectionCard>
      </div>

      <DashboardDetailDialog
        open={Boolean(detailState)}
        onOpenChange={(open) => {
          if (!open) setDetailState(null);
        }}
        title={detailState?.title ?? "Detalhamento"}
        description={
          detailState?.description ??
          "Tabela detalhada do indicador selecionado."
        }
        rows={detailRows}
        columns={DETAIL_COLUMNS}
        exportColumns={DETAIL_EXPORT_COLUMNS}
        exportTitle={detailState?.title ?? "Detalhamento dashboard"}
        exportFilename={(detailState?.title ?? "detalhamento-dashboard")
          .toLowerCase()
          .replace(/[^\w]+/g, "-")}
        emptyMessage="Nenhum registro encontrado para o recorte selecionado."
        isLoading={detailQuery.isLoading}
        matchesSearch={matchesDetailRowSearch}
      />
    </>
  );
}

export default function DashboardPage() {
  return (
    <RoleGuard allow={["ADMIN"]}>
      <DashboardPageContent />
    </RoleGuard>
  );
}
