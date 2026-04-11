"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { format, isWithinInterval, startOfQuarter, subDays } from "date-fns";
import { ptBR } from "date-fns/locale";
import {
  ArrowUpRightIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  EyeIcon,
  LayoutGridIcon,
  ListIcon,
  RefreshCcwIcon,
  SlidersHorizontalIcon,
  UserMinusIcon,
} from "lucide-react";
import { toast } from "sonner";

import CalendarCompetencia from "@/components/custom/calendar-competencia";
import DatePicker from "@/components/custom/date-picker";
import SearchableSelect, {
  type SelectOption,
} from "@/components/custom/searchable-select";
import StatusBadge from "@/components/custom/status-badge";
import CopySnippet from "@/components/shared/copy-snippet";
import DataTable, { type DataTableColumn } from "@/components/shared/data-table";
import ReportExportDialog from "@/components/shared/report-export-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Progress } from "@/components/ui/progress";
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useV1ImportacaoArquivoRetornoList,
  useV1RenovacaoCiclosList,
  useV1RenovacaoCiclosMesesList,
  useV1RenovacaoCiclosVisaoMensalRetrieve,
} from "@/gen";
import type { RenovacaoCicloItem } from "@/gen/models";
import { apiFetch } from "@/lib/api/client";
import {
  formatDateValue,
  formatMonthValue,
  parseDateValue,
  parseMonthValue,
} from "@/lib/date-value";
import {
  formatCurrency,
  formatDate,
  formatDateTime,
  formatLongMonthYear,
} from "@/lib/formatters";
import {
  getArquivoFinanceiroResumo,
  type ArquivoRetornoFinanceiroItem,
  type ArquivoRetornoFinanceiroPayload,
  type ArquivoRetornoFinanceiroResumo,
  type ArquivoRetornoWithFinanceiro,
  toFinanceiroNumber,
  toFinanceiroStatus,
} from "@/lib/importacao-financeiro";
import { maskCPFCNPJ } from "@/lib/masks";
import { cn } from "@/lib/utils";
import { usePermissions } from "@/hooks/use-permissions";
import RenovacaoAdminEditDialog from "@/components/refinanciamento/renovacao-admin-edit-dialog";

const STATUS_OPTIONS = [
  { value: "todos", label: "Todos os status" },
  { value: "ciclo_renovado", label: "Ciclo renovado" },
  { value: "apto_a_renovar", label: "Apto a renovar" },
  { value: "em_aberto", label: "Em aberto" },
  { value: "ciclo_iniciado", label: "Ciclo iniciado" },
  { value: "inadimplente", label: "Inadimplente" },
  { value: "em_previsao", label: "Em previsão" },
] satisfies SelectOption[];

const PARCELA_STATUS_OPTIONS = [
  { value: "todos", label: "Todos os status da parcela" },
  { value: "descontado", label: "Descontado" },
  { value: "efetivado", label: "Efetivado" },
  { value: "em_aberto", label: "Em aberto" },
  { value: "pendente", label: "Pendente" },
  { value: "nao_descontado", label: "Não descontado" },
] satisfies SelectOption[];

const PERIOD_OPTIONS = [
  { value: "todos", label: "Todo o histórico" },
  { value: "7d", label: "Últimos 7 dias" },
  { value: "30d", label: "Últimos 30 dias" },
  { value: "90d", label: "Últimos 90 dias" },
  { value: "trimestre", label: "Trimestre atual" },
] as const;

type PeriodPreset = (typeof PERIOD_OPTIONS)[number]["value"];
type LayoutMode = "grid" | "list";

type AdvancedFilters = {
  periodPreset: PeriodPreset;
  dateStart: string;
  dateEnd: string;
  parcelStatus: string;
  agent: string;
};

type EnrichedCycleItem = RenovacaoCicloItem & {
  agenteResponsavel: string;
  associadoUrl: string;
  statusExplicacao: string;
  contratoReferenciaRenovacaoId: number;
  contratoReferenciaRenovacaoCodigo: string;
  possuiMultiplosContratos: boolean;
};

type EnrichedReturnItem = ArquivoRetornoFinanceiroItem & {
  associadoId?: number;
  agenteResponsavel: string;
  matriculaResolvida: string;
  esperado: string | number;
  recebido: string | number;
  situacao: string;
  nome_servidor: string;
  statusBadge: string;
};

type TableExportColumn<T> = {
  header: string;
  value: (row: T) => string | number;
};

type RenovacaoCicloResumoData = {
  total_associados?: number;
  ciclo_renovado?: number;
  apto_a_renovar?: number;
  em_aberto?: number;
  ciclo_iniciado?: number;
  inadimplente?: number;
  esperado_total?: string | number;
  arrecadado_total?: string | number;
  percentual_arrecadado?: string | number;
};

type CycleParcelCard = {
  parcela: number;
  status: string;
  paid: boolean;
  active: boolean;
  reason: string;
};

type MetricStatusKey =
  | "ciclo_renovado"
  | "apto_a_renovar"
  | "em_aberto"
  | "inadimplente"
  | "em_previsao";

type CycleMetricDialogConfig = {
  key: string;
  title: string;
  description: string;
  rows: EnrichedCycleItem[];
  monthLabel: string;
  exportTitle: string;
  exportFilename: string;
  emptyMessage: string;
};

type ReturnMetricDialogConfig = {
  key: "quitados" | "faltando" | "mensalidades" | "valores_30_50";
  title: string;
  description: string;
  exportTitle: string;
  exportFilename: string;
  emptyMessage: string;
};

const DETAIL_PAGE_SIZE_OPTIONS = [
  { label: "5", value: 5 },
  { label: "10", value: 10 },
  { label: "20", value: 20 },
  { label: "50+", value: 50 },
] satisfies Array<{ label: string; value: number }>;

type PageSizeOption = (typeof DETAIL_PAGE_SIZE_OPTIONS)[number];

const KPI_SURFACE_CLASS = "min-w-0 overflow-hidden";
const TABLE_VIEWPORT_CLASS = "min-w-0 max-w-full overflow-x-auto";
const MODAL_SCROLL_VIEWPORT_CLASS = "min-h-0 overflow-y-auto pr-1";
const DETAIL_DIALOG_CONTENT_CLASS =
  "grid max-h-[calc(100vh-2rem)] w-[96vw] max-w-[96vw] grid-rows-[auto_auto_minmax(0,1fr)] overflow-hidden border-border/60 bg-background/95 p-5 sm:p-6 lg:max-w-[88vw] 2xl:max-w-[96rem]";
const WIDE_DIALOG_CONTENT_CLASS =
  "grid max-h-[calc(100vh-2rem)] w-[98vw] max-w-[98vw] grid-rows-[auto_auto_minmax(0,1fr)] overflow-hidden border-border/60 bg-background/95 p-5 sm:p-6 lg:max-w-[92vw] 2xl:max-w-[104rem]";

const MONTHLY_METRIC_META: Record<
  MetricStatusKey,
  {
    label: string;
    tone?: "neutral" | "warning" | "danger";
    accent?: "cyan";
    description: string;
  }
> = {
  ciclo_renovado: {
    label: "Renovados",
    description: "Associados com ciclo encerrado e renovacao efetivada na competencia.",
  },
  apto_a_renovar: {
    label: "Aptos a renovar",
    accent: "cyan",
    description: "Associados prontos para renovacao, mas ainda sem abertura do proximo ciclo.",
  },
  em_aberto: {
    label: "Em aberto",
    tone: "warning",
    description: "Associados com parcela atual em aberto na competencia filtrada.",
  },
  inadimplente: {
    label: "Inadimplentes",
    tone: "danger",
    description: "Associados com retorno nao descontado ou status consolidado de inadimplencia.",
  },
  em_previsao: {
    label: "Em previsao",
    tone: "warning",
    description: "Ciclos futuros ainda inativos, aguardando efetivacao da renovacao.",
  },
};

function buildPageItems(currentPage: number, totalPages: number) {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, index) => index + 1);
  }

  const pages = new Set<number>([1, totalPages, currentPage, currentPage - 1, currentPage + 1]);
  const sorted = [...pages].filter((page) => page >= 1 && page <= totalPages).sort((a, b) => a - b);
  const items: Array<number | string> = [];

  sorted.forEach((page, index) => {
    const previous = sorted[index - 1];
    if (previous && page - previous > 1) {
      items.push(`ellipsis-${previous}-${page}`);
    }
    items.push(page);
  });

  return items;
}

function normalizeText(value?: string | null) {
  return (value ?? "")
    .toString()
    .normalize("NFD")
    .replaceAll(/\p{Diacritic}/gu, "")
    .toLowerCase()
    .trim();
}

function onlyDigits(value?: string | null) {
  return (value ?? "").replaceAll(/\D/g, "");
}

export function parseCompetenciaDate(value?: string | null) {
  if (!value) return undefined;
  const trimmed = value.trim();

  const isoMonthMatch = /^(\d{4})-(\d{2})$/.exec(trimmed);
  if (isoMonthMatch) {
    return new Date(Number(isoMonthMatch[1]), Number(isoMonthMatch[2]) - 1, 1);
  }

  const isoDateMatch = /^(\d{4})-(\d{2})-(\d{2})$/.exec(trimmed);
  if (isoDateMatch) {
    return new Date(
      Number(isoDateMatch[1]),
      Number(isoDateMatch[2]) - 1,
      Number(isoDateMatch[3]),
    );
  }

  const displayMonthMatch = /^(\d{2})\/(\d{4})$/.exec(trimmed);
  if (displayMonthMatch) {
    return new Date(Number(displayMonthMatch[2]), Number(displayMonthMatch[1]) - 1, 1);
  }

  const parsed = new Date(trimmed);
  if (Number.isNaN(parsed.getTime())) return undefined;
  return new Date(parsed.getFullYear(), parsed.getMonth(), parsed.getDate());
}

function capitalize(value: string) {
  return value ? value.charAt(0).toUpperCase() + value.slice(1) : value;
}

function formatCompetenciaHeading(primary?: string | null, fallback?: string | null) {
  const date = parseCompetenciaDate(primary) ?? parseCompetenciaDate(fallback);
  if (!date) return primary || fallback || "-";
  return capitalize(formatLongMonthYear(date));
}

function resolveParcelaStatusLabel(status?: string | null) {
  const normalized = normalizeText(status).replaceAll(" ", "_");
  if (!normalized) return "Pendente";
  return normalized.replaceAll("_", " ");
}

function formatEtipiStatusLabel(
  statusCode?: string | null,
  statusDescription?: string | null,
) {
  const code = (statusCode ?? "").trim();
  const description = (statusDescription ?? "").trim();

  if (code && description) {
    return `${code} - ${description}`;
  }
  return description || code || "-";
}

function isParcelaPaid(row: RenovacaoCicloItem) {
  return (
    row.resultado_importacao === "baixa_efetuada" ||
    row.status_parcela === "descontado" ||
    row.status_parcela === "efetivado"
  );
}

function buildCycleResumo(rows: RenovacaoCicloItem[]) {
  return {
    total: rows.length,
    cicloRenovado: rows.filter(
      (row) => row.status_visual === "ciclo_renovado" || row.gerou_encerramento,
    ).length,
    aptoRenovar: rows.filter((row) => row.status_visual === "apto_a_renovar").length,
    emAberto: rows.filter((row) => row.status_visual === "em_aberto").length,
    cicloIniciado: rows.filter(
      (row) => row.status_visual === "ciclo_iniciado" || row.gerou_novo_ciclo,
    ).length,
    inadimplente: rows.filter((row) => row.status_visual === "inadimplente").length,
  };
}

function buildMonthlyMetrics(rows: RenovacaoCicloItem[]) {
  const resumo = buildCycleResumo(rows);
  const esperado = rows.reduce(
    (total, row) => total + Number.parseFloat(String(row.valor_parcela || 0) || "0"),
    0,
  );
  const arrecadado = rows.reduce((total, row) => {
    if (!isParcelaPaid(row)) return total;
    return total + Number.parseFloat(String(row.valor_parcela || 0) || "0");
  }, 0);
  const percentual = esperado > 0 ? (arrecadado / esperado) * 100 : 0;

  return {
    ...resumo,
    esperado,
    arrecadado,
    percentual,
  };
}

function toNumericValue(value: unknown) {
  if (typeof value === "number") return value;
  if (typeof value === "string") return Number.parseFloat(value) || 0;
  return 0;
}

function buildMonthlyMetricsFromResumo(resumo?: RenovacaoCicloResumoData | null) {
  return {
    total: resumo?.total_associados ?? 0,
    cicloRenovado: resumo?.ciclo_renovado ?? 0,
    aptoRenovar: resumo?.apto_a_renovar ?? 0,
    emAberto: resumo?.em_aberto ?? 0,
    cicloIniciado: resumo?.ciclo_iniciado ?? 0,
    inadimplente: resumo?.inadimplente ?? 0,
    esperado: toNumericValue(resumo?.esperado_total),
    arrecadado: toNumericValue(resumo?.arrecadado_total),
    percentual: toNumericValue(resumo?.percentual_arrecadado),
  };
}

function applyFinanceiroToMonthlyMetrics(
  metrics: ReturnType<typeof buildMonthlyMetrics>,
  financeiro?: ArquivoRetornoFinanceiroResumo | null,
) {
  if (!financeiro) return metrics;

  return {
    ...metrics,
    total: financeiro.total ?? metrics.total,
    esperado: toFinanceiroNumber(financeiro.esperado),
    arrecadado: toFinanceiroNumber(financeiro.recebido),
    percentual:
      typeof financeiro.percentual === "number"
        ? financeiro.percentual
        : metrics.percentual,
  };
}

function hasUnsupportedResumoFilters(advancedFilters: AdvancedFilters) {
  return (
    advancedFilters.periodPreset !== "todos" ||
    Boolean(advancedFilters.dateStart) ||
    Boolean(advancedFilters.dateEnd) ||
    advancedFilters.parcelStatus !== "todos" ||
    advancedFilters.agent !== "todos"
  );
}

function withinPreset(date: Date, periodPreset: PeriodPreset) {
  const today = new Date();
  if (periodPreset === "todos") return true;
  if (periodPreset === "7d") {
    return isWithinInterval(date, { start: subDays(today, 7), end: today });
  }
  if (periodPreset === "30d") {
    return isWithinInterval(date, { start: subDays(today, 30), end: today });
  }
  if (periodPreset === "90d") {
    return isWithinInterval(date, { start: subDays(today, 90), end: today });
  }

  const quarterStart = startOfQuarter(today);
  return isWithinInterval(date, { start: quarterStart, end: today });
}

function withinCustomRange(date: Date, dateStart?: string, dateEnd?: string) {
  const start = parseDateValue(dateStart);
  const end = parseDateValue(dateEnd);
  if (!start && !end) return true;

  const endBoundary = end
    ? new Date(end.getFullYear(), end.getMonth(), end.getDate(), 23, 59, 59, 999)
    : undefined;

  if (start && date < start) return false;
  if (endBoundary && date > endBoundary) return false;
  return true;
}

function matchesCycleRow(
  row: EnrichedCycleItem,
  searchValue: string,
  selectedStatus: string,
  advancedFilters: AdvancedFilters,
) {
  if (!matchesCycleSearchValue(row, searchValue)) {
    return false;
  }

  if (selectedStatus !== "todos" && row.status_visual !== selectedStatus) {
    return false;
  }

  if (
    advancedFilters.parcelStatus !== "todos" &&
    row.status_parcela !== advancedFilters.parcelStatus
  ) {
    return false;
  }

  if (
    advancedFilters.agent !== "todos" &&
    normalizeText(row.agenteResponsavel) !== normalizeText(advancedFilters.agent)
  ) {
    return false;
  }

  const referenceDate =
    (row.data_pagamento ? new Date(row.data_pagamento) : undefined) ??
    parseCompetenciaDate(row.competencia);

  if (referenceDate) {
    if (!withinPreset(referenceDate, advancedFilters.periodPreset)) {
      return false;
    }
    if (
      !withinCustomRange(
        referenceDate,
        advancedFilters.dateStart,
        advancedFilters.dateEnd,
      )
    ) {
      return false;
    }
  }

  return true;
}

function matchesCycleSearchValue(row: EnrichedCycleItem, searchValue: string) {
  const comparableText = [
    row.nome_associado,
    row.cpf_cnpj,
    row.matricula,
    row.agenteResponsavel,
    row.contrato_codigo,
  ]
    .map(normalizeText)
    .join(" ");

  if (searchValue && !comparableText.includes(normalizeText(searchValue))) {
    return false;
  }
  return true;
}

function countActiveFilters(selectedStatus: string, advancedFilters: AdvancedFilters) {
  return [
    selectedStatus !== "todos",
    advancedFilters.periodPreset !== "todos",
    Boolean(advancedFilters.dateStart),
    Boolean(advancedFilters.dateEnd),
    advancedFilters.parcelStatus !== "todos",
    advancedFilters.agent !== "todos",
  ].filter(Boolean).length;
}

function buildAutocompleteOptions(rows: EnrichedCycleItem[]) {
  const seen = new Set<string>();
  const options: SelectOption[] = [];

  rows.forEach((row) => {
    const uniqueKey = onlyDigits(row.cpf_cnpj) || normalizeText(row.matricula) || normalizeText(row.nome_associado);
    if (!uniqueKey || seen.has(uniqueKey)) {
      return;
    }

    seen.add(uniqueKey);
    options.push({
      value: `assoc::${uniqueKey}`,
      label: `${row.nome_associado} • ${maskCPFCNPJ(row.cpf_cnpj)} • ${row.matricula}`,
    });
  });

  return options;
}

function decodeAutocompleteValue(value: string) {
  const [, decoded = ""] = value.split("::");
  return decoded;
}

function buildCycleParcelCards(row: RenovacaoCicloItem): CycleParcelCard[] {
  const isFuturoCycle = row.status_ciclo === "futuro";

  return Array.from({ length: row.parcelas_total }, (_, index) => {
    const parcela = index + 1;
    const isCurrent =
      !isFuturoCycle && parcela === Math.min(row.parcelas_total, Math.max(row.parcelas_pagas, 1));
    const status =
      parcela < row.parcelas_pagas || (row.parcelas_pagas === row.parcelas_total && parcela <= row.parcelas_pagas)
        ? "Pago"
        : isFuturoCycle
          ? "Em previsão"
          : isCurrent
            ? capitalize(resolveParcelaStatusLabel(row.status_parcela))
            : "Pendente";
    const reason = isFuturoCycle
      ? "Parcela em previsão. O ciclo será ativado quando o primeiro pagamento for recebido."
      : status === "Pago"
        ? "Parcela já baixada em competência anterior do ciclo."
        : isCurrent
          ? row.status_descricao_etipi
            ? `Parcela atual marcada como ${status.toLowerCase()} porque o retorno ETIPI veio como ${formatEtipiStatusLabel(
                row.status_codigo_etipi,
                row.status_descricao_etipi,
              )}.`
            : `Parcela atual marcada como ${status.toLowerCase()} pelo status consolidado da competência.`
          : "Parcela futura do ciclo. Ainda não houve processamento desta etapa na competência selecionada.";

    return {
      parcela,
      status,
      paid: status === "Pago",
      active: isCurrent,
      reason,
    };
  });
}

function TablePagination({
  page,
  totalPages,
  onPageChange,
  pageSize,
  pageSizeOptions,
  pageSizeLabel = "Por página",
  onPageSizeChange,
}: {
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  pageSize?: number;
  pageSizeOptions?: PageSizeOption[];
  pageSizeLabel?: string;
  onPageSizeChange?: (pageSize: number) => void;
}) {
  if (totalPages <= 1 && !(pageSizeOptions?.length && onPageSizeChange && pageSize)) {
    return null;
  }

  const pageItems = buildPageItems(page, totalPages);

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border/60 px-4 py-3">
      <p className="text-xs text-muted-foreground">
        Página {page} de {totalPages}
      </p>
      <div className="flex flex-wrap items-center justify-end gap-3">
        {pageSizeOptions?.length && onPageSizeChange && pageSize ? (
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">{pageSizeLabel}</span>
            <Select
              value={String(pageSize)}
              onValueChange={(value) => onPageSizeChange(Number(value))}
            >
              <SelectTrigger className="h-8 min-w-24 rounded-xl bg-card/60 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {pageSizeOptions.map((option) => (
                  <SelectItem key={option.value} value={String(option.value)}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        ) : null}
        <Button
          type="button"
          variant="outline"
          size="xs"
          disabled={page === 1}
          onClick={() => onPageChange(1)}
        >
          Primeira
        </Button>
        <Button
          type="button"
          variant="outline"
          size="xs"
          disabled={page === 1}
          onClick={() => onPageChange(Math.max(1, page - 1))}
        >
          Anterior
        </Button>
        {pageItems.map((item) =>
          typeof item === "number" ? (
            <Button
              key={item}
              type="button"
              variant={item === page ? "secondary" : "outline"}
              size="xs"
              className="min-w-8 rounded-xl"
              onClick={() => onPageChange(item)}
            >
              {item}
            </Button>
          ) : (
            <span key={item} className="px-1 text-xs text-muted-foreground">
              ...
            </span>
          ),
        )}
        <Button
          type="button"
          variant="outline"
          size="xs"
          disabled={page === totalPages}
          onClick={() => onPageChange(Math.min(totalPages, page + 1))}
        >
          Próxima
        </Button>
        <Button
          type="button"
          variant="outline"
          size="xs"
          disabled={page === totalPages}
          onClick={() => onPageChange(totalPages)}
        >
          Última
        </Button>
      </div>
    </div>
  );
}

function sanitizeFileName(value: string) {
  return value
    .normalize("NFD")
    .replaceAll(/\p{Diacritic}/gu, "")
    .replaceAll(/[^a-zA-Z0-9_-]+/g, "-")
    .replaceAll(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .toLowerCase();
}

function downloadFile(filename: string, content: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function exportAsSeparatedText<T>(
  filename: string,
  columns: TableExportColumn<T>[],
  rows: T[],
  separator = "\t",
) {
  const header = columns.map((column) => column.header).join(separator);
  const lines = rows.map((row) =>
    columns
      .map((column) =>
        String(column.value(row))
          .replaceAll("\n", " ")
          .replaceAll(separator, " "),
      )
      .join(separator),
  );
  downloadFile(filename, [header, ...lines].join("\n"), "application/vnd.ms-excel;charset=utf-8");
}

function escapeHtml(value: string) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function exportAsPrintableHtml<T>(
  title: string,
  columns: TableExportColumn<T>[],
  rows: T[],
) {
  const escapedTitle = escapeHtml(title);
  const headers = columns.map((column) => `<th>${escapeHtml(column.header)}</th>`).join("");
  const body = rows
    .map(
      (row) =>
        `<tr>${columns
          .map((column) => `<td>${escapeHtml(String(column.value(row) ?? "-"))}</td>`)
          .join("")}</tr>`,
    )
    .join("");
  const html = `
    <html lang="pt-BR">
      <head>
        <title>${escapedTitle}</title>
        <style>
          body { font-family: Arial, sans-serif; padding: 24px; color: #111827; }
          h1 { margin: 0 0 16px; font-size: 22px; }
          table { width: 100%; border-collapse: collapse; }
          th, td { border: 1px solid #d1d5db; padding: 8px 10px; text-align: left; font-size: 12px; }
          th { background: #f3f4f6; text-transform: uppercase; letter-spacing: 0.04em; }
        </style>
      </head>
      <body>
        <h1>${escapedTitle}</h1>
        <table>
          <thead><tr>${headers}</tr></thead>
          <tbody>${body}</tbody>
        </table>
      </body>
    </html>
  `;

  const iframe = document.createElement("iframe");
  iframe.setAttribute("aria-hidden", "true");
  iframe.style.position = "fixed";
  iframe.style.right = "0";
  iframe.style.bottom = "0";
  iframe.style.width = "0";
  iframe.style.height = "0";
  iframe.style.border = "0";
  iframe.style.opacity = "0";
  iframe.style.pointerEvents = "none";

  document.body.appendChild(iframe);

  const cleanup = () => {
    window.setTimeout(() => {
      iframe.remove();
    }, 0);
  };

  const printWindow = iframe.contentWindow;
  const printDocument = printWindow?.document;

  if (!printWindow || !printDocument) {
    cleanup();
    toast.error("Não foi possível preparar a visualização para PDF.");
    return;
  }

  try {
    printDocument.open();
    printDocument.write(html);
    printDocument.close();

    const triggerPrint = () => {
      try {
        printWindow.focus();
        printWindow.print();
      } catch {
        toast.error("Não foi possível gerar a visualização para PDF.");
      } finally {
        window.setTimeout(cleanup, 1500);
      }
    };

    printWindow.addEventListener("afterprint", cleanup, { once: true });
    window.setTimeout(triggerPrint, 150);
  } catch {
    cleanup();
    toast.error("Não foi possível gerar a visualização para PDF.");
  }
}

function exportRows<T>(
  format: "csv" | "pdf" | "excel" | "xlsx",
  title: string,
  filenameBase: string,
  columns: TableExportColumn<T>[],
  rows: T[],
) {
  if (format === "pdf") {
    exportAsPrintableHtml(title, columns, rows);
    return;
  }

  const separator = format === "csv" ? ";" : "\t";
  const extension = format === "csv" ? "csv" : format === "xlsx" ? "xlsx" : "xls";
  exportAsSeparatedText(`${filenameBase}.${extension}`, columns, rows, separator);
}

function cycleExportColumns(competenciaLabel: string): TableExportColumn<EnrichedCycleItem>[] {
  return [
    { header: "Associado", value: (row) => row.nome_associado },
    { header: "CPF", value: (row) => maskCPFCNPJ(row.cpf_cnpj) },
    { header: "Matrícula", value: (row) => row.matricula },
    { header: "Agente responsável", value: (row) => row.agenteResponsavel },
    { header: "Parcelas do ciclo", value: (row) => `${row.parcelas_pagas}/${row.parcelas_total}` },
    { header: `Status da parcela (${competenciaLabel})`, value: (row) => row.status_parcela },
  ];
}

function returnExportColumns(): TableExportColumn<EnrichedReturnItem>[] {
  return [
    { header: "Nome", value: (row) => row.associado_nome || row.nome_servidor },
    { header: "CPF", value: (row) => maskCPFCNPJ(row.cpf_cnpj) },
    { header: "Matrícula", value: (row) => row.matriculaResolvida },
    { header: "Agente responsável", value: (row) => row.agenteResponsavel },
    { header: "Status", value: (row) => row.status_label || row.situacao },
    { header: "Esperado", value: (row) => formatCurrency(row.esperado) },
    { header: "Recebido", value: (row) => formatCurrency(row.recebido) },
    { header: "Situação", value: (row) => row.situacao },
  ];
}

function matchesReturnSearchValue(row: EnrichedReturnItem, searchValue: string) {
  const comparableText = [
    row.associado_nome,
    row.nome_servidor,
    row.cpf_cnpj,
    row.matriculaResolvida,
    row.agenteResponsavel,
    row.status_label,
    row.situacao,
  ]
    .map(normalizeText)
    .join(" ");

  if (searchValue && !comparableText.includes(normalizeText(searchValue))) {
    return false;
  }

  return true;
}

function buildEnrichedReturnRows(
  rows: ArquivoRetornoFinanceiroItem[],
  cycleLookup: Map<string, EnrichedCycleItem>,
  options: {
    searchValue?: string;
    agent?: string;
  } = {},
) {
  const searchValue = options.searchValue ?? "";
  const agent = options.agent ?? "todos";

  return rows
    .map((item) => {
      const normalizedCpf = onlyDigits(item.cpf_cnpj);
      const cycleMatch = cycleLookup.get(normalizedCpf);

      return {
        ...item,
        associadoId: item.associado_id ?? cycleMatch?.associado_id,
        agenteResponsavel:
          item.agente_responsavel ||
          cycleMatch?.agenteResponsavel ||
          "Sem agente vinculado",
        matriculaResolvida: item.matricula || cycleMatch?.matricula || "-",
        esperado: item.esperado || cycleMatch?.valor_parcela || item.valor || 0,
        recebido: item.recebido || 0,
        situacao: item.situacao_label,
        nome_servidor: item.relatorio || item.associado_nome || cycleMatch?.nome_associado || "-",
        statusBadge: toFinanceiroStatus(item.situacao_code),
        associado_nome: item.associado_nome || cycleMatch?.nome_associado || item.relatorio || "-",
      } satisfies EnrichedReturnItem;
    })
    .filter((item) => {
      if (!matchesReturnSearchValue(item, searchValue)) {
        return false;
      }

      if (
        agent !== "todos" &&
        normalizeText(item.agenteResponsavel) !== normalizeText(agent)
      ) {
        return false;
      }

      return true;
    });
}

function buildReturnAutocompleteOptions(rows: EnrichedReturnItem[]) {
  const seen = new Set<string>();
  const options: SelectOption[] = [];

  rows.forEach((row) => {
    const uniqueKey = onlyDigits(row.cpf_cnpj) || normalizeText(row.matriculaResolvida) || normalizeText(row.associado_nome || row.nome_servidor);
    if (!uniqueKey || seen.has(uniqueKey)) {
      return;
    }

    seen.add(uniqueKey);
    options.push({
      value: `assoc::${uniqueKey}`,
      label: `${row.associado_nome || row.nome_servidor} • ${maskCPFCNPJ(row.cpf_cnpj)} • ${row.matriculaResolvida}`,
    });
  });

  return options;
}

function normalizeCategoria(value?: string | null) {
  return normalizeText(value).replaceAll("/", "_").replaceAll("-", "_").replaceAll(" ", "_");
}

function isMensalidadesCategoria(value?: string | null) {
  const normalized = normalizeCategoria(value);
  return normalized === "mensalidades" || normalized === "mensalidade";
}

function isValores3050Categoria(value?: string | null) {
  const normalized = normalizeCategoria(value);
  return normalized === "valores_30_50" || normalized === "valores3050";
}

function summarizeReturnRows(rows: EnrichedReturnItem[]) {
  const quitadosRows = rows.filter((row) => row.ok);
  const faltandoRows = rows.filter((row) => !row.ok);
  const mensalidadesRows = rows.filter((row) => isMensalidadesCategoria(row.categoria));
  const valores3050Rows = rows.filter((row) => isValores3050Categoria(row.categoria));

  const sumRows = (items: EnrichedReturnItem[]) =>
    items.reduce(
      (accumulator, row) => {
        accumulator.esperado += toFinanceiroNumber(row.esperado);
        accumulator.recebido += toFinanceiroNumber(row.recebido);
        return accumulator;
      },
      { esperado: 0, recebido: 0 },
    );

  const quitados = sumRows(quitadosRows);
  const faltando = sumRows(faltandoRows);
  const mensalidades = sumRows(mensalidadesRows);
  const valores3050 = sumRows(valores3050Rows);

  return {
    total: rows.length,
    quitados: {
      count: quitadosRows.length,
      ...quitados,
    },
    faltando: {
      count: faltandoRows.length,
      ...faltando,
      pendente: Math.max(faltando.esperado - faltando.recebido, 0),
    },
    mensalidades: {
      count: mensalidadesRows.length,
      ...mensalidades,
    },
    valores_30_50: {
      count: valores3050Rows.length,
      ...valores3050,
    },
  };
}

function matchesMetricStatus(row: EnrichedCycleItem, status: MetricStatusKey) {
  if (status === "ciclo_renovado") {
    return row.status_visual === "ciclo_renovado" || row.gerou_encerramento;
  }

  return row.status_visual === status;
}

function buildReturnColumns({
  compact = false,
  includeActions = false,
}: {
  compact?: boolean;
  includeActions?: boolean;
} = {}): DataTableColumn<EnrichedReturnItem>[] {
  const columns: DataTableColumn<EnrichedReturnItem>[] = [
    {
      id: "nome",
      header: compact ? "Associado" : "Nome",
      cell: (row) => (
        <CopySnippet
          label="Nome"
          value={row.associado_nome || row.nome_servidor}
          inline
          className="max-w-full"
        />
      ),
      headerClassName: compact ? "min-w-[16rem]" : "min-w-[18rem]",
      cellClassName: compact ? "min-w-[16rem]" : "min-w-[18rem]",
    },
  ];

  if (!compact) {
    columns.push(
      {
        id: "cpf",
        header: "CPF",
        cell: (row) => <CopySnippet label="CPF" value={row.cpf_cnpj} mono />,
      },
      {
        id: "matricula",
        header: "Matrícula",
        cell: (row) => <CopySnippet label="Matrícula" value={row.matriculaResolvida} mono />,
      },
      {
        id: "agente",
        header: "Agente responsável",
        accessor: "agenteResponsavel",
        cell: (row) => <span className="text-sm text-foreground">{row.agenteResponsavel}</span>,
      },
    );
  }

  columns.push(
    {
      id: "status",
      header: "Status",
      cell: (row) => (
        <StatusBadge status={row.statusBadge} label={row.status_label || row.situacao} />
      ),
    },
    {
      id: "esperado",
      header: "Esperado",
      cell: (row) => <span className="text-sm text-foreground">{formatCurrency(row.esperado)}</span>,
    },
    {
      id: "recebido",
      header: "Recebido",
      cell: (row) => (
        <span className="text-sm font-medium text-foreground">{formatCurrency(row.recebido)}</span>
      ),
    },
  );

  if (!compact) {
    columns.push({
      id: "situacao",
      header: "Situação",
      accessor: "situacao",
      cell: (row) => <span className="text-sm text-muted-foreground">{row.situacao}</span>,
      headerClassName: "min-w-[18rem]",
      cellClassName: "min-w-[18rem] whitespace-normal",
    });
  }

  if (includeActions) {
    columns.push({
      id: "acoes",
      header: "Ações",
      cell: (row) =>
        row.associadoId ? (
          <Button asChild variant="outline" size="sm" className="rounded-2xl">
            <Link href={`/associados/${row.associadoId}`}>
              <ArrowUpRightIcon className="size-4" />
              Ver detalhes do associado
            </Link>
          </Button>
        ) : (
          <Button disabled variant="outline" size="sm" className="rounded-2xl">
            Ver detalhes do associado
          </Button>
        ),
      headerClassName: "min-w-[12rem]",
      cellClassName: "min-w-[12rem]",
    });
  }

  return columns;
}

function useEnrichedCycleRows(rows: RenovacaoCicloItem[]) {
  return React.useMemo<EnrichedCycleItem[]>(() => {
    return rows.map((row) => {
      const rawRow = row as RenovacaoCicloItem & {
        status_explicacao?: string;
        contrato_referencia_renovacao_id?: number;
        contrato_referencia_renovacao_codigo?: string;
        possui_multiplos_contratos?: boolean;
      };
      return {
        ...row,
        matricula: row.matricula || row.contrato_codigo,
        agenteResponsavel: row.agente_responsavel || "Sem agente vinculado",
        associadoUrl: `/associados/${row.associado_id}`,
        statusExplicacao: rawRow.status_explicacao || "",
        contratoReferenciaRenovacaoId:
          rawRow.contrato_referencia_renovacao_id ?? row.contrato_id,
        contratoReferenciaRenovacaoCodigo:
          rawRow.contrato_referencia_renovacao_codigo ?? row.contrato_codigo,
        possuiMultiplosContratos: Boolean(rawRow.possui_multiplos_contratos),
      };
    });
  }, [rows]);
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

type CycleMembersTableProps = {
  rows: EnrichedCycleItem[];
  monthLabel: string;
  compact?: boolean;
  emptyMessage?: string;
  pageSize?: number;
  pageSizeOptions?: PageSizeOption[];
  pageSizeLabel?: string;
  tableClassName?: string;
};

function CycleMembersTable({
  rows,
  monthLabel,
  compact = false,
  emptyMessage = "Nenhum associado encontrado para este mês.",
  pageSize = compact ? 4 : 10,
  pageSizeOptions,
  pageSizeLabel,
  tableClassName,
}: CycleMembersTableProps) {
  const [expandedRow, setExpandedRow] = React.useState<number | null>(null);
  const [page, setPage] = React.useState(1);
  const [currentPageSize, setCurrentPageSize] = React.useState(pageSize);
  const resolvedPageSize = pageSizeOptions?.length ? currentPageSize : pageSize;
  const totalPages = Math.max(1, Math.ceil(rows.length / resolvedPageSize));
  const currentRows = React.useMemo(
    () => rows.slice((page - 1) * resolvedPageSize, page * resolvedPageSize),
    [page, resolvedPageSize, rows],
  );

  React.useEffect(() => {
    setPage((current) => Math.min(current, totalPages));
  }, [totalPages]);

  React.useEffect(() => {
    setExpandedRow(null);
  }, [page]);

  React.useEffect(() => {
    setCurrentPageSize(pageSize);
  }, [pageSize]);

  return (
    <div className="overflow-hidden rounded-[1.35rem] border border-border/60 bg-background/55">
      <Table className={cn(compact ? "min-w-[42rem]" : "min-w-[72rem]", tableClassName)}>
        <TableHeader>
          <TableRow className="border-border/60 hover:bg-transparent">
            <TableHead className="h-11 px-4 text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
              {compact ? "Associado" : "Associado"}
            </TableHead>
            {!compact ? (
              <>
                <TableHead className="h-11 px-4 text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                  CPF
                </TableHead>
                <TableHead className="h-11 px-4 text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                  Matrícula
                </TableHead>
                <TableHead className="h-11 px-4 text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                  Agente responsável
                </TableHead>
              </>
            ) : null}
            <TableHead className="h-11 px-4 text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
              Parc.
            </TableHead>
            <TableHead className="h-11 px-4 text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
              {compact ? "Status" : `Status da parcela (${monthLabel})`}
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {currentRows.length ? (
            currentRows.map((row) => {
              const parcelCards = buildCycleParcelCards(row);
              const isExpanded = expandedRow === row.id;

              return (
                <React.Fragment key={row.id}>
                  <TableRow
                    className={cn(
                      "cursor-pointer border-border/60 hover:bg-white/3",
                      row.status_visual === "em_previsao" && "opacity-55",
                    )}
                    onClick={() => setExpandedRow((current) => (current === row.id ? null : Number(row.id)))}
                  >
                    <TableCell className="px-4 py-3">
                      <div className="flex items-start gap-3">
                        {isExpanded ? (
                          <ChevronDownIcon className="mt-1 size-4 text-muted-foreground" />
                        ) : (
                          <ChevronRightIcon className="mt-1 size-4 text-muted-foreground" />
                        )}
                        <div className="min-w-0 space-y-1">
                          {compact ? (
                            <p className="truncate font-medium text-foreground">{row.nome_associado}</p>
                          ) : (
                            <CopySnippet
                              label="Nome"
                              value={row.nome_associado}
                              inline
                              className="max-w-full"
                            />
                          )}
                          <p className="text-xs text-muted-foreground">{row.contrato_codigo}</p>
                        </div>
                      </div>
                    </TableCell>
                    {!compact ? (
                      <>
                        <TableCell className="px-4 py-3">
                          <CopySnippet label="CPF" value={row.cpf_cnpj} mono />
                        </TableCell>
                        <TableCell className="px-4 py-3">
                          <CopySnippet label="Matrícula" value={row.matricula} mono />
                        </TableCell>
                        <TableCell className="px-4 py-3 text-sm text-foreground">
                          {row.agenteResponsavel}
                        </TableCell>
                      </>
                    ) : null}
                    <TableCell className="px-4 py-3 font-semibold text-cyan-300">
                      {row.parcelas_pagas}/{row.parcelas_total}
                    </TableCell>
                    <TableCell className="px-4 py-3">
                      <StatusBadge
                        status={compact ? row.status_visual : row.status_parcela}
                        label={compact ? undefined : capitalize(resolveParcelaStatusLabel(row.status_parcela))}
                      />
                    </TableCell>
                  </TableRow>
                  {isExpanded ? (
                    <TableRow className="border-border/60 bg-white/3">
                      <TableCell colSpan={compact ? 3 : 6} className="px-4 py-4">
                        <div className="space-y-4">
                          {row.status_visual === "apto_a_renovar" && row.statusExplicacao ? (
                            <div className="rounded-2xl border border-cyan-500/25 bg-cyan-500/10 px-4 py-3 text-sm text-cyan-50">
                              {row.statusExplicacao}
                            </div>
                          ) : null}
                          <div className="flex flex-wrap items-center justify-between gap-3">
                            <div>
                              <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
                                Detalhes do ciclo atual
                              </p>
                              <p className="mt-2 text-sm text-foreground">
                                {capitalize(resolveParcelaStatusLabel(row.status_parcela))} na competência{" "}
                                <span className="font-medium">{monthLabel}</span>
                              </p>
                            </div>
                            <Button variant="outline" size="sm" className="rounded-2xl" asChild>
                              <Link href={row.associadoUrl} onClick={(event) => event.stopPropagation()}>
                                  <ArrowUpRightIcon className="size-4" />
                                  Ver detalhes do associado
                              </Link>
                            </Button>
                          </div>

                          <div className="grid gap-3 sm:grid-cols-3">
                            {parcelCards.map((parcelCard) => (
                              <Tooltip key={`${row.id}-${parcelCard.parcela}`}>
                                <TooltipTrigger asChild>
                                  <div
                                    tabIndex={0}
                                    role="button"
                                    aria-label={`Parcela ${parcelCard.parcela} de ${row.parcelas_total}: ${parcelCard.status}`}
                                    className={cn(
                                      "rounded-2xl border border-border/60 px-4 py-3 outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring/50",
                                      parcelCard.active && "border-primary/45 bg-primary/8",
                                    )}
                                  >
                                    <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
                                      Parcela {parcelCard.parcela}/{row.parcelas_total}
                                    </p>
                                    <p
                                      className={cn(
                                        "mt-2 text-sm font-semibold",
                                        parcelCard.paid
                                          ? "text-emerald-300"
                                          : parcelCard.active
                                            ? "text-amber-300"
                                            : "text-muted-foreground",
                                      )}
                                    >
                                      {parcelCard.status}
                                    </p>
                                  </div>
                                </TooltipTrigger>
                                <TooltipContent side="bottom" className="max-w-72">
                                  {parcelCard.reason}
                                </TooltipContent>
                              </Tooltip>
                            ))}
                          </div>

                          <div className="flex flex-wrap gap-2">
                            <Button
                              className="rounded-2xl"
                              size="sm"
                              onClick={(event) => {
                                event.stopPropagation();
                                toast.success(`Fluxo de renovação iniciado para ${row.nome_associado}.`);
                              }}
                            >
                              <RefreshCcwIcon className="size-4" />
                              Renovar ciclo
                            </Button>
                            <Button
                              variant="destructive"
                              size="sm"
                              className="rounded-2xl"
                              onClick={(event) => {
                                event.stopPropagation();
                                toast.success(`Solicitação de desativação aberta para ${row.nome_associado}.`);
                              }}
                            >
                              <UserMinusIcon className="size-4" />
                              Desativar associado
                            </Button>
                          </div>
                        </div>
                      </TableCell>
                    </TableRow>
                  ) : null}
                </React.Fragment>
              );
            })
          ) : (
            <TableRow className="border-border/60">
              <TableCell
                colSpan={compact ? 3 : 6}
                className="px-4 py-10 text-center text-sm text-muted-foreground"
              >
                {emptyMessage}
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
      <TablePagination
        page={page}
        totalPages={totalPages}
        onPageChange={setPage}
        pageSize={resolvedPageSize}
        pageSizeOptions={pageSizeOptions}
        pageSizeLabel={pageSizeLabel}
        onPageSizeChange={(nextPageSize) => {
          setCurrentPageSize(nextPageSize);
          setPage(1);
          setExpandedRow(null);
        }}
      />
    </div>
  );
}

function TableSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="space-y-3 rounded-[1.35rem] border border-border/60 bg-background/55 p-4">
      <Skeleton className="h-10 w-full rounded-xl" />
      {Array.from({ length: rows }, (_, index) => (
        <Skeleton key={index} className="h-14 w-full rounded-xl" />
      ))}
    </div>
  );
}

function MetricTileSkeleton() {
  return (
    <div className="rounded-2xl border border-border/60 bg-background/55 px-4 py-3">
      <Skeleton className="h-3 w-20" />
      <Skeleton className="mt-3 h-7 w-14" />
    </div>
  );
}

function MonthlyCycleCardSkeleton() {
  return (
    <Card className="min-w-0 border-border/60 bg-card/80 shadow-xl shadow-black/15">
      <CardHeader className="gap-4">
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-2">
            <Skeleton className="h-8 w-32" />
            <Skeleton className="h-4 w-40" />
            <Skeleton className="h-4 w-44" />
          </div>
          <Skeleton className="h-10 w-24 rounded-2xl" />
        </div>
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-4 w-12" />
          </div>
          <Skeleton className="h-2.5 w-full rounded-full" />
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <MetricTileSkeleton />
          <MetricTileSkeleton />
          <MetricTileSkeleton />
          <MetricTileSkeleton />
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div className="space-y-2">
            <Skeleton className="h-4 w-40" />
            <Skeleton className="h-3 w-28" />
          </div>
          <Skeleton className="h-9 w-32 rounded-2xl" />
        </div>
        <TableSkeleton rows={4} />
      </CardContent>
    </Card>
  );
}

function ReturnFileCardSkeleton() {
  return (
    <Card className="min-w-0 border-border/60 bg-card/80 shadow-xl shadow-black/15">
      <CardHeader className="gap-5">
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-2">
            <Skeleton className="h-7 w-44" />
            <Skeleton className="h-4 w-60" />
          </div>
          <Skeleton className="h-7 w-24 rounded-full" />
        </div>
        <div className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <Skeleton className="h-4 w-40" />
            <Skeleton className="h-4 w-12" />
          </div>
          <Skeleton className="h-2.5 w-full rounded-full" />
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <MetricTileSkeleton />
          <MetricTileSkeleton />
          <MetricTileSkeleton />
          <MetricTileSkeleton />
        </div>
        <Skeleton className="h-14 w-full rounded-2xl" />
      </CardHeader>
      <CardContent className="space-y-4">
        <Skeleton className="h-9 w-44 rounded-2xl" />
      </CardContent>
    </Card>
  );
}

type MetricDetailDialogProps<T extends { id: number | string }> = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  rows: T[];
  isLoading?: boolean;
  autocompleteOptions: SelectOption[];
  matchesSearch: (row: T, searchValue: string) => boolean;
  placeholder: string;
  searchPlaceholder: string;
  emptyLabel: string;
  exportTitle: string;
  exportFilename: string;
  exportColumns: TableExportColumn<T>[];
  renderTable: (rows: T[]) => React.ReactNode;
};

function MetricDetailDialog<T extends { id: number | string }>({
  open,
  onOpenChange,
  title,
  description,
  rows,
  isLoading = false,
  autocompleteOptions,
  matchesSearch,
  placeholder,
  searchPlaceholder,
  emptyLabel,
  exportTitle,
  exportFilename,
  exportColumns,
  renderTable,
}: MetricDetailDialogProps<T>) {
  const [autocompleteValue, setAutocompleteValue] = React.useState("");
  const searchValue = decodeAutocompleteValue(autocompleteValue);
  const filteredRows = React.useMemo(
    () => rows.filter((row) => matchesSearch(row, searchValue)),
    [matchesSearch, rows, searchValue],
  );

  React.useEffect(() => {
    if (!open) {
      setAutocompleteValue("");
    }
  }, [open]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className={DETAIL_DIALOG_CONTENT_CLASS}>
        <DialogHeader className="shrink-0">
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>

        <div className="flex shrink-0 flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex min-w-0 flex-1 flex-col gap-2 sm:flex-row">
            <SearchableSelect
              options={autocompleteOptions}
              value={autocompleteValue}
              onChange={setAutocompleteValue}
              placeholder={placeholder}
              searchPlaceholder={searchPlaceholder}
              emptyLabel={emptyLabel}
              className="min-w-0 flex-1 rounded-2xl sm:min-w-[22rem]"
            />
          </div>
          <ReportExportDialog
            hideScope
            onExport={(_, fmt) =>
              exportRows(
                fmt,
                exportTitle,
                exportFilename,
                exportColumns,
                filteredRows,
              )
            }
          />
        </div>

        <div className={MODAL_SCROLL_VIEWPORT_CLASS}>
          {isLoading ? <TableSkeleton rows={6} /> : renderTable(filteredRows)}
        </div>
      </DialogContent>
    </Dialog>
  );
}

type MonthlyCycleCardProps = {
  competenciaId: string;
  layoutMode: LayoutMode;
  searchValue: string;
  selectedStatus: string;
  advancedFilters: AdvancedFilters;
};

function MonthlyCycleCard({
  competenciaId,
  layoutMode,
  searchValue,
  selectedStatus,
  advancedFilters,
}: MonthlyCycleCardProps) {
  const [isDialogOpen, setIsDialogOpen] = React.useState(false);
  const [dialogAutocomplete, setDialogAutocomplete] = React.useState("");
  const [metricDialogConfig, setMetricDialogConfig] =
    React.useState<CycleMetricDialogConfig | null>(null);
  const monthLabel = formatCompetenciaHeading(competenciaId);
  const canUseServerResumo = !hasUnsupportedResumoFilters(advancedFilters);
  const canUseFinanceiroResumo =
    !searchValue && selectedStatus === "todos" && !hasUnsupportedResumoFilters(advancedFilters);

  const listQuery = useV1RenovacaoCiclosList(
    { competencia: competenciaId, page_size: 1000 },
    {
      query: {
        enabled: Boolean(competenciaId),
        staleTime: 30 * 1000,
        placeholderData: (previousData) => previousData,
      },
    },
  );
  const importacaoMensalQuery = useQuery({
    queryKey: ["arquivo-retorno-mensal-card", competenciaId],
    queryFn: () =>
      apiFetch<{ results: ArquivoRetornoWithFinanceiro[] }>("importacao/arquivo-retorno", {
        query: {
          competencia: competenciaId,
          periodo: "mes",
          page_size: 1,
          ordering: "-created_at",
        },
      }),
    enabled: Boolean(competenciaId),
    staleTime: 30 * 1000,
    placeholderData: (previousData: { results: ArquivoRetornoWithFinanceiro[] } | undefined) =>
      previousData,
  });
  const enrichedRows = useEnrichedCycleRows(listQuery.data?.results ?? []);
  const cycleLookup = React.useMemo(
    () => new Map<string, EnrichedCycleItem>(enrichedRows.map((row) => [onlyDigits(row.cpf_cnpj), row])),
    [enrichedRows],
  );
  const filteredRows = React.useMemo(
    () =>
      enrichedRows.filter((row) =>
        matchesCycleRow(row, searchValue, selectedStatus, advancedFilters),
      ),
    [advancedFilters, enrichedRows, searchValue, selectedStatus],
  );
  const resumoMensalQuery = useV1RenovacaoCiclosVisaoMensalRetrieve(
    {
      competencia: competenciaId,
      search: searchValue || undefined,
      status: selectedStatus !== "todos" ? selectedStatus : undefined,
    },
    {
      query: {
        enabled: Boolean(competenciaId) && canUseServerResumo,
        staleTime: 30 * 1000,
        placeholderData: (previousData) => previousData,
      },
    },
  );
  const arquivoMensal = (importacaoMensalQuery.data?.results?.[0] ?? null) as
    | ArquivoRetornoWithFinanceiro
    | null;
  const financeiroMensal = getArquivoFinanceiroResumo(arquivoMensal);
  const financeiroDetalheQuery = useQuery({
    queryKey: ["arquivo-retorno-mensal-card-financeiro", arquivoMensal?.id],
    queryFn: () => {
      if (!arquivoMensal?.id) {
        throw new Error("Arquivo retorno mensal indisponível.");
      }

      return apiFetch<ArquivoRetornoFinanceiroPayload>(
        `importacao/arquivo-retorno/${arquivoMensal.id}/financeiro`,
      );
    },
    enabled: canUseFinanceiroResumo && Boolean(arquivoMensal?.id),
    staleTime: 30 * 1000,
    refetchOnMount: "always",
    refetchOnWindowFocus: true,
    placeholderData: (previousData: ArquivoRetornoFinanceiroPayload | undefined) =>
      previousData,
  });
  const monthlyMetrics = React.useMemo(() => {
    const metrics =
      canUseServerResumo && resumoMensalQuery.data
        ? buildMonthlyMetricsFromResumo(resumoMensalQuery.data)
        : buildMonthlyMetrics(filteredRows);

    if (canUseFinanceiroResumo) {
      return applyFinanceiroToMonthlyMetrics(
        metrics,
        financeiroDetalheQuery.data?.resumo ?? financeiroMensal,
      );
    }
    return metrics;
  }, [
    canUseFinanceiroResumo,
    canUseServerResumo,
    filteredRows,
    financeiroDetalheQuery.data?.resumo,
    financeiroMensal,
    resumoMensalQuery.data,
  ]);
  const financeRows = React.useMemo(
    () => buildEnrichedReturnRows(financeiroDetalheQuery.data?.rows ?? [], cycleLookup),
    [cycleLookup, financeiroDetalheQuery.data?.rows],
  );
  const hasConciliatedRows = enrichedRows.length > 0;
  const cardPageSize = layoutMode === "grid" ? 4 : 6;
  const dialogSearchValue = decodeAutocompleteValue(dialogAutocomplete);
  const useFinanceiroDetalhe =
    canUseFinanceiroResumo && Boolean(arquivoMensal?.id) && Boolean(financeiroDetalheQuery.data);
  const dialogAutocompleteOptions = React.useMemo(() => {
    if (useFinanceiroDetalhe) {
      return buildReturnAutocompleteOptions(financeRows);
    }

    return buildAutocompleteOptions(filteredRows);
  }, [filteredRows, financeRows, useFinanceiroDetalhe]);
  const dialogCycleRows = React.useMemo(
    () => filteredRows.filter((row) => matchesCycleSearchValue(row, dialogSearchValue)),
    [dialogSearchValue, filteredRows],
  );
  const dialogFinanceRows = React.useMemo(
    () => financeRows.filter((row) => matchesReturnSearchValue(row, dialogSearchValue)),
    [dialogSearchValue, financeRows],
  );
  const financeCompactColumns = React.useMemo(
    () => buildReturnColumns({ compact: true }),
    [],
  );
  const financeDetailColumns = React.useMemo(
    () => buildReturnColumns({ includeActions: true }),
    [],
  );
  const metricRowsByStatus = React.useMemo(
    () => ({
      ciclo_renovado: filteredRows.filter((row) => matchesMetricStatus(row, "ciclo_renovado")),
      apto_a_renovar: filteredRows.filter((row) => matchesMetricStatus(row, "apto_a_renovar")),
      em_aberto: filteredRows.filter((row) => matchesMetricStatus(row, "em_aberto")),
      inadimplente: filteredRows.filter((row) => matchesMetricStatus(row, "inadimplente")),
      em_previsao: filteredRows.filter((row) => matchesMetricStatus(row, "em_previsao")),
    }),
    [filteredRows],
  );
  const monthlyMetricCounts = React.useMemo(
    () =>
      !searchValue && selectedStatus === "todos" && canUseServerResumo
        ? {
            cicloRenovado: monthlyMetrics.cicloRenovado,
            aptoRenovar: monthlyMetrics.aptoRenovar,
            emAberto: monthlyMetrics.emAberto,
            inadimplente: monthlyMetrics.inadimplente,
            emPrevisao: metricRowsByStatus.em_previsao.length,
          }
        : {
            cicloRenovado: metricRowsByStatus.ciclo_renovado.length,
            aptoRenovar: metricRowsByStatus.apto_a_renovar.length,
            emAberto: metricRowsByStatus.em_aberto.length,
            inadimplente: metricRowsByStatus.inadimplente.length,
            emPrevisao: metricRowsByStatus.em_previsao.length,
          },
    [canUseServerResumo, metricRowsByStatus, monthlyMetrics, searchValue, selectedStatus],
  );
  const cycleMetricAutocompleteOptions = React.useMemo(
    () => buildAutocompleteOptions(metricDialogConfig?.rows ?? []),
    [metricDialogConfig?.rows],
  );
  const openMetricDialog = React.useCallback(
    (status: MetricStatusKey) => {
      const meta = MONTHLY_METRIC_META[status];
      setMetricDialogConfig({
        key: status,
        title: `${meta.label} em ${monthLabel}`,
        description: meta.description,
        rows: metricRowsByStatus[status],
        monthLabel,
        exportTitle: `${meta.label} - ${monthLabel}`,
        exportFilename: sanitizeFileName(`status-${status}-${competenciaId}`),
        emptyMessage: "Nenhum associado encontrado para este status com os filtros atuais.",
      });
    },
    [competenciaId, metricRowsByStatus, monthLabel],
  );
  const isFetchingFinanceiro = useFinanceiroDetalhe && financeiroDetalheQuery.isFetching;
  const isCardLoading =
    (listQuery.isLoading && !listQuery.data) ||
    (canUseServerResumo && resumoMensalQuery.isLoading && !resumoMensalQuery.data) ||
    (importacaoMensalQuery.isLoading && !importacaoMensalQuery.data) ||
    (canUseFinanceiroResumo && Boolean(arquivoMensal?.id) && financeiroDetalheQuery.isLoading && !financeiroDetalheQuery.data);

  if (isCardLoading) {
    return <MonthlyCycleCardSkeleton />;
  }

  return (
    <Card className="min-w-0 border-border/60 bg-card/80 shadow-xl shadow-black/15">
      <CardHeader className="gap-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle className="text-xl">{monthLabel}</CardTitle>
            <CardDescription className="mt-2">
              Esperado: <span className="font-semibold text-foreground">{formatCurrency(monthlyMetrics.esperado)}</span>
            </CardDescription>
            <CardDescription>
              Arrecadado: <span className="font-semibold text-emerald-300">{formatCurrency(monthlyMetrics.arrecadado)}</span>
            </CardDescription>
            {financeiroMensal ? (
              <CardDescription>
                Fonte: <span className="font-semibold text-cyan-300">arquivo retorno</span>
              </CardDescription>
            ) : null}
          </div>
          <ReportExportDialog
            hideScope
            onExport={(_, fmt) => {
              if (useFinanceiroDetalhe) {
                exportRows(
                  fmt,
                  `Gestão detalhada ${monthLabel}`,
                  sanitizeFileName(`gestao-financeira-${competenciaId}`),
                  returnExportColumns(),
                  financeRows,
                );
                return;
              }

              exportRows(
                fmt,
                `Gestão detalhada ${monthLabel}`,
                sanitizeFileName(`gestao-ciclo-${competenciaId}`),
                cycleExportColumns(monthLabel),
                filteredRows,
              );
            }}
          />
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>Execução do mês</span>
            <span className="font-medium text-foreground">{monthlyMetrics.percentual.toFixed(1)}%</span>
          </div>
          <Progress value={monthlyMetrics.percentual} className="h-2.5" />
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <MetricTile
            label="Renovados"
            value={monthlyMetricCounts.cicloRenovado}
            onClick={() => openMetricDialog("ciclo_renovado")}
          />
          <MetricTile
            label="Aptos a renovar"
            value={monthlyMetricCounts.aptoRenovar}
            accent="cyan"
            onClick={() => openMetricDialog("apto_a_renovar")}
          />
          <MetricTile
            label="Em aberto"
            value={monthlyMetricCounts.emAberto}
            tone="warning"
            onClick={() => openMetricDialog("em_aberto")}
          />
          <MetricTile
            label="Inadimplentes"
            value={monthlyMetricCounts.inadimplente}
            tone="danger"
            onClick={() => openMetricDialog("inadimplente")}
          />
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-sm font-medium text-foreground">
              {useFinanceiroDetalhe ? "Detalhamento financeiro" : "Detalhamento de associados"}
            </p>
            <p className="text-xs text-muted-foreground">
              {useFinanceiroDetalhe ? financeRows.length : filteredRows.length} registros disponíveis
            </p>
          </div>
          {listQuery.isFetching || resumoMensalQuery.isFetching || isFetchingFinanceiro ? (
            <Badge variant="outline" className="rounded-full border-border/60">
              Atualizando
            </Badge>
          ) : null}
          <Dialog
            open={isDialogOpen}
            onOpenChange={(open) => {
              setIsDialogOpen(open);
              if (!open) {
                setDialogAutocomplete("");
              }
            }}
          >
            <DialogTrigger asChild>
              <Button variant="outline" size="sm" className="rounded-2xl">
                <EyeIcon className="size-4" />
                Ampliar tabela
              </Button>
            </DialogTrigger>
            <DialogContent className={WIDE_DIALOG_CONTENT_CLASS}>
              <DialogHeader className="shrink-0">
                <DialogTitle>
                  {useFinanceiroDetalhe
                    ? `Gestão financeira de ${monthLabel}`
                    : `Gestão detalhada de ${monthLabel}`}
                </DialogTitle>
                <DialogDescription>
                  {useFinanceiroDetalhe
                    ? "Associados do arquivo retorno, valores esperados, recebidos e situação conciliada."
                    : "Associados, agente responsável, parcelas do ciclo e status da parcela da competência."}
                </DialogDescription>
              </DialogHeader>
              <div className="flex shrink-0 flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                <div className="flex min-w-0 flex-1 flex-col gap-2 sm:flex-row">
                  <SearchableSelect
                    options={dialogAutocompleteOptions}
                    value={dialogAutocomplete}
                    onChange={setDialogAutocomplete}
                    placeholder={
                      useFinanceiroDetalhe
                        ? "Buscar associado neste retorno"
                        : "Buscar associado nesta tabela"
                    }
                    searchPlaceholder="Buscar por nome, CPF ou matrícula"
                    emptyLabel={
                      useFinanceiroDetalhe
                        ? "Nenhum associado encontrado neste retorno."
                        : "Nenhum associado encontrado nesta tabela."
                    }
                    className="min-w-0 flex-1 rounded-2xl sm:min-w-[22rem]"
                  />
                </div>
                <ReportExportDialog
                  hideScope
                  onExport={(_, fmt) => {
                    if (useFinanceiroDetalhe) {
                      exportRows(
                        fmt,
                        `Gestão detalhada ${monthLabel}`,
                        sanitizeFileName(`gestao-financeira-${competenciaId}`),
                        returnExportColumns(),
                        dialogFinanceRows,
                      );
                      return;
                    }

                    exportRows(
                      fmt,
                      `Gestão detalhada ${monthLabel}`,
                      sanitizeFileName(`gestao-ciclo-${competenciaId}`),
                      cycleExportColumns(monthLabel),
                      dialogCycleRows,
                    );
                  }}
                />
              </div>
              <div className={MODAL_SCROLL_VIEWPORT_CLASS}>
                <div className={TABLE_VIEWPORT_CLASS}>
                  {useFinanceiroDetalhe ? (
                    <DataTable
                      columns={financeDetailColumns}
                      data={dialogFinanceRows}
                      pageSize={10}
                      pageSizeOptions={DETAIL_PAGE_SIZE_OPTIONS}
                      className="rounded-[1.35rem] border border-border/60 bg-background/55 shadow-none"
                      tableClassName="min-w-[82rem]"
                      emptyMessage="Nenhum lançamento encontrado no arquivo retorno desta competência."
                    />
                  ) : (
                    <CycleMembersTable
                      rows={dialogCycleRows}
                      monthLabel={monthLabel}
                      pageSize={10}
                      pageSizeOptions={DETAIL_PAGE_SIZE_OPTIONS}
                      tableClassName="min-w-[82rem]"
                    />
                  )}
                </div>
              </div>
            </DialogContent>
          </Dialog>
        </div>

        <div className={TABLE_VIEWPORT_CLASS}>
          {useFinanceiroDetalhe ? (
            <DataTable
              columns={financeCompactColumns}
              data={financeRows}
              pageSize={cardPageSize}
              className="rounded-[1.35rem] border border-border/60 bg-background/55 shadow-none"
              tableClassName="min-w-[44rem]"
              emptyMessage="Nenhum lançamento encontrado no arquivo retorno desta competência."
            />
          ) : (
            <CycleMembersTable
              rows={filteredRows}
              monthLabel={monthLabel}
              compact
              pageSize={cardPageSize}
              tableClassName="min-w-[42rem]"
              emptyMessage={
                hasConciliatedRows
                  ? "Nenhum associado corresponde aos filtros deste card."
                  : "Nenhuma parcela conciliada encontrada para esta competência."
              }
            />
          )}
        </div>
      </CardContent>

      <MetricDetailDialog
        open={Boolean(metricDialogConfig)}
        onOpenChange={(open) => {
          if (!open) {
            setMetricDialogConfig(null);
          }
        }}
        title={metricDialogConfig?.title ?? "Detalhamento por status"}
        description={
          metricDialogConfig?.description ??
          "Associados consolidados para o status selecionado na competência."
        }
        rows={metricDialogConfig?.rows ?? []}
        autocompleteOptions={cycleMetricAutocompleteOptions}
        matchesSearch={matchesCycleSearchValue}
        placeholder="Buscar associado neste status"
        searchPlaceholder="Buscar por nome, CPF ou matrícula"
        emptyLabel={metricDialogConfig?.emptyMessage ?? "Nenhum associado encontrado neste status."}
        exportTitle={metricDialogConfig?.exportTitle ?? `Detalhamento ${monthLabel}`}
        exportFilename={
          metricDialogConfig?.exportFilename ??
          sanitizeFileName(`status-detalhamento-${competenciaId}`)
        }
        exportColumns={cycleExportColumns(metricDialogConfig?.monthLabel ?? monthLabel)}
        renderTable={(rows) => (
          <div className={TABLE_VIEWPORT_CLASS}>
            <CycleMembersTable
              rows={rows}
              monthLabel={metricDialogConfig?.monthLabel ?? monthLabel}
              pageSize={10}
              pageSizeOptions={DETAIL_PAGE_SIZE_OPTIONS}
              tableClassName="min-w-[82rem]"
              emptyMessage={
                metricDialogConfig?.emptyMessage ??
                "Nenhum associado encontrado para este status com os filtros atuais."
              }
            />
          </div>
        )}
      />
    </Card>
  );
}

type ReturnFileCardProps = {
  arquivo: ArquivoRetornoWithFinanceiro;
  cycleLookup: Map<string, EnrichedCycleItem>;
  searchValue: string;
  advancedFilters: AdvancedFilters;
};

function ReturnFileCard({
  arquivo,
  cycleLookup,
  searchValue,
  advancedFilters,
}: ReturnFileCardProps) {
  const [isExpanded, setIsExpanded] = React.useState(false);
  const [metricDialogConfig, setMetricDialogConfig] =
    React.useState<ReturnMetricDialogConfig | null>(null);
  const financeiroResumo = getArquivoFinanceiroResumo(arquivo);
  const shouldLoadFinanceiro = Boolean(arquivo.id);
  const financeiroQuery = useQuery({
    queryKey: ["arquivo-retorno-financeiro", arquivo.id],
    queryFn: () =>
      apiFetch<ArquivoRetornoFinanceiroPayload>(
        `importacao/arquivo-retorno/${arquivo.id}/financeiro`,
      ),
    enabled: shouldLoadFinanceiro,
    staleTime: 30 * 1000,
    refetchOnMount: "always",
    refetchOnWindowFocus: true,
    placeholderData: (previousData: ArquivoRetornoFinanceiroPayload | undefined) => previousData,
  });
  const isDetailLoading = isExpanded && financeiroQuery.isLoading && !financeiroQuery.data;

  const rawItems = React.useMemo<ArquivoRetornoFinanceiroItem[]>(() => {
    if (!shouldLoadFinanceiro) return [];
    return financeiroQuery.data?.rows ?? [];
  }, [financeiroQuery.data?.rows, shouldLoadFinanceiro]);

  const allDetailRows = React.useMemo<EnrichedReturnItem[]>(
    () => buildEnrichedReturnRows(rawItems, cycleLookup),
    [cycleLookup, rawItems],
  );

  const detailRows = React.useMemo<EnrichedReturnItem[]>(() => {
    return allDetailRows.filter((item) => {
      if (!matchesReturnSearchValue(item, searchValue)) {
        return false;
      }

      if (
        advancedFilters.agent !== "todos" &&
        normalizeText(item.agenteResponsavel) !== normalizeText(advancedFilters.agent)
      ) {
        return false;
      }

      return true;
    });
  }, [advancedFilters.agent, allDetailRows, searchValue]);
  const detailColumns = React.useMemo<DataTableColumn<EnrichedReturnItem>[]>(
    () => buildReturnColumns({ includeActions: true }),
    [],
  );

  const fileTitle = formatCompetenciaHeading(
    arquivo.competencia_display,
    arquivo.competencia,
  );
  const liveFinanceiroResumo =
    financeiroQuery.data?.resumo ?? financeiroResumo;
  const metricRowsByStatus = React.useMemo(
    () => ({
      quitados: detailRows.filter((row) => row.ok),
      faltando: detailRows.filter((row) => !row.ok),
      mensalidades: detailRows.filter((row) => isMensalidadesCategoria(row.categoria)),
      valores_30_50: detailRows.filter((row) => isValores3050Categoria(row.categoria)),
    }),
    [detailRows],
  );
  const detailSummary = React.useMemo(() => summarizeReturnRows(detailRows), [detailRows]);
  const total = liveFinanceiroResumo?.total ?? arquivo.total_registros ?? detailSummary.total;
  const quitados = liveFinanceiroResumo?.ok ?? detailSummary.quitados.count;
  const faltando =
    liveFinanceiroResumo?.faltando ?? Math.max(total - quitados, 0);
  const recebido = toFinanceiroNumber(liveFinanceiroResumo?.recebido);
  const esperado = toFinanceiroNumber(liveFinanceiroResumo?.esperado);
  const pendente = toFinanceiroNumber(liveFinanceiroResumo?.pendente);
  const progresso = esperado > 0 ? (recebido / esperado) * 100 : 0;
  const mensalidades = liveFinanceiroResumo?.mensalidades ?? detailSummary.mensalidades;
  const valores3050 = liveFinanceiroResumo?.valores_30_50 ?? detailSummary.valores_30_50;
  const metricDialogRows = metricDialogConfig
    ? metricRowsByStatus[metricDialogConfig.key]
    : [];
  const metricAutocompleteOptions = React.useMemo(
    () => buildReturnAutocompleteOptions(metricDialogRows),
    [metricDialogRows],
  );
  const openMetricDialog = React.useCallback(
    (metric: keyof typeof metricRowsByStatus) => {
      const configMap: Record<keyof typeof metricRowsByStatus, ReturnMetricDialogConfig> = {
        quitados: {
          key: "quitados",
          title: `Quitados no arquivo ${fileTitle}`,
          description: "Associados efetivados neste arquivo retorno.",
          exportTitle: `Quitados - ${arquivo.arquivo_nome}`,
          exportFilename: sanitizeFileName(`arquivo-retorno-${arquivo.id}-quitados`),
          emptyMessage: "Nenhum associado quitado encontrado neste arquivo.",
        },
        faltando: {
          key: "faltando",
          title: `Faltando no arquivo ${fileTitle}`,
          description: "Associados que ainda permanecem pendentes neste arquivo retorno.",
          exportTitle: `Faltando - ${arquivo.arquivo_nome}`,
          exportFilename: sanitizeFileName(`arquivo-retorno-${arquivo.id}-faltando`),
          emptyMessage: "Nenhum associado pendente encontrado neste arquivo.",
        },
        mensalidades: {
          key: "mensalidades",
          title: `Mensalidades no arquivo ${fileTitle}`,
          description: "Associados classificados como mensalidades no resumo financeiro.",
          exportTitle: `Mensalidades - ${arquivo.arquivo_nome}`,
          exportFilename: sanitizeFileName(`arquivo-retorno-${arquivo.id}-mensalidades`),
          emptyMessage: "Nenhum associado classificado como mensalidade neste arquivo.",
        },
        valores_30_50: {
          key: "valores_30_50",
          title: `Valores 30/50 no arquivo ${fileTitle}`,
          description: "Associados classificados na faixa de valores 30/50 neste arquivo retorno.",
          exportTitle: `Valores 30/50 - ${arquivo.arquivo_nome}`,
          exportFilename: sanitizeFileName(`arquivo-retorno-${arquivo.id}-valores-30-50`),
          emptyMessage: "Nenhum associado classificado como valor 30/50 neste arquivo.",
        },
      };

      setMetricDialogConfig({
        ...configMap[metric],
      });
    },
    [arquivo.arquivo_nome, arquivo.id, fileTitle],
  );

  return (
    <Card className="min-w-0 border-border/60 bg-card/80 shadow-xl shadow-black/15">
      <CardHeader className="gap-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="text-lg">{arquivo.arquivo_nome}</CardTitle>
            <CardDescription className="mt-2">
              Competência {arquivo.competencia_display || formatCompetenciaHeading(arquivo.competencia)} • Processado em{" "}
              {formatDateTime(arquivo.processado_em || arquivo.created_at)}
            </CardDescription>
          </div>
          <StatusBadge status={arquivo.status || "pendente"} />
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between gap-3 text-sm">
            <span className="text-muted-foreground">
              Recebido: <span className="font-medium text-foreground">{formatCurrency(recebido)}</span> de{" "}
              <span className="font-medium text-foreground">{formatCurrency(esperado)}</span>
            </span>
            <span className="font-medium text-foreground">{progresso.toFixed(1)}%</span>
          </div>
          <Progress value={progresso} className="h-2.5" />
          <p className="text-sm text-muted-foreground">
            Quitados: <span className="font-medium text-foreground">{quitados}</span> de{" "}
            <span className="font-medium text-foreground">{total}</span> contratos.
            {faltando > 0 ? (
              <>
                {" "}
                Restam <span className="font-medium text-foreground">{faltando}</span> registros e{" "}
                <span className="font-medium text-foreground">{formatCurrency(pendente)}</span> pendentes.
              </>
            ) : null}
          </p>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <MetricTile
            label="Quitados"
            value={`${quitados}/${total}`}
            accent="cyan"
            onClick={() => openMetricDialog("quitados")}
          />
          <MetricTile
            label="Faltando"
            value={faltando}
            tone={faltando > 0 ? "warning" : "neutral"}
            hint={formatCurrency(pendente)}
            onClick={() => openMetricDialog("faltando")}
          />
          <MetricTile
            label="Mensalidades"
            value={formatCurrency(mensalidades?.recebido)}
            hint={`de ${formatCurrency(mensalidades?.esperado)}`}
            onClick={() => openMetricDialog("mensalidades")}
          />
          <MetricTile
            label="Valores 30/50"
            value={formatCurrency(valores3050?.recebido)}
            hint={`de ${formatCurrency(valores3050?.esperado)}`}
            onClick={() => openMetricDialog("valores_30_50")}
          />
        </div>

        <div className="rounded-2xl border border-border/60 bg-background/55 px-4 py-3 text-sm text-muted-foreground">
          {fileTitle}. Sistema de origem: <span className="font-medium text-foreground">{arquivo.sistema_origem}</span>. Usuário:{" "}
          <span className="font-medium text-foreground">{arquivo.uploaded_by_nome}</span>.
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            className="rounded-2xl"
            onClick={() => setIsExpanded((current) => !current)}
          >
            <EyeIcon className="size-4" />
            {isExpanded ? "Ocultar detalhamento do arquivo" : "Detalhamento do arquivo"}
          </Button>
          {isExpanded ? (
            <ReportExportDialog
              hideScope
              onExport={(_, fmt) =>
                exportRows(
                  fmt,
                  `Arquivo retorno ${arquivo.arquivo_nome}`,
                  sanitizeFileName(`arquivo-retorno-${arquivo.id}`),
                  returnExportColumns(),
                  detailRows,
                )
              }
            />
          ) : null}
        </div>

        {isExpanded ? (
          <div className={TABLE_VIEWPORT_CLASS}>
            {isDetailLoading ? (
              <TableSkeleton rows={5} />
            ) : (
              <DataTable
                columns={detailColumns}
                data={detailRows}
                pageSize={8}
                pageSizeOptions={DETAIL_PAGE_SIZE_OPTIONS}
                className="rounded-[1.35rem] border border-border/60 bg-background/55 shadow-none"
                tableClassName="min-w-[86rem]"
                emptyMessage="Nenhum item detalhado disponível para este arquivo com os filtros atuais."
              />
            )}
          </div>
        ) : null}
      </CardContent>

      <MetricDetailDialog
        open={Boolean(metricDialogConfig)}
        onOpenChange={(open) => {
          if (!open) {
            setMetricDialogConfig(null);
          }
        }}
        title={metricDialogConfig?.title ?? `Detalhamento do arquivo ${arquivo.arquivo_nome}`}
        description={
          metricDialogConfig?.description ??
          "Associados relacionados ao indicador selecionado deste arquivo retorno."
        }
        rows={metricDialogRows}
        isLoading={Boolean(metricDialogConfig) && shouldLoadFinanceiro && financeiroQuery.isLoading && !financeiroQuery.data}
        autocompleteOptions={metricAutocompleteOptions}
        matchesSearch={matchesReturnSearchValue}
        placeholder="Buscar associado neste indicador"
        searchPlaceholder="Buscar por nome, CPF ou matrícula"
        emptyLabel={
          metricDialogConfig?.emptyMessage ??
          "Nenhum associado encontrado para este indicador."
        }
        exportTitle={metricDialogConfig?.exportTitle ?? `Arquivo retorno ${arquivo.arquivo_nome}`}
        exportFilename={
          metricDialogConfig?.exportFilename ??
          sanitizeFileName(`arquivo-retorno-${arquivo.id}-detalhamento`)
        }
        exportColumns={returnExportColumns()}
        renderTable={(rows) => (
          <div className={TABLE_VIEWPORT_CLASS}>
            <DataTable
              columns={detailColumns}
              data={rows}
              pageSize={10}
              pageSizeOptions={DETAIL_PAGE_SIZE_OPTIONS}
              className="rounded-[1.35rem] border border-border/60 bg-background/55 shadow-none"
              tableClassName="min-w-[86rem]"
              emptyMessage={
                metricDialogConfig?.emptyMessage ??
                "Nenhum item detalhado disponível para este indicador."
              }
            />
          </div>
        )}
      />
    </Card>
  );
}

function MetricTile({
  label,
  value,
  hint,
  tone = "neutral",
  accent,
  onClick,
}: {
  label: string;
  value: React.ReactNode;
  hint?: string;
  tone?: "neutral" | "warning" | "danger";
  accent?: "cyan";
  onClick?: () => void;
}) {
  const toneClasses = {
    neutral: "border-border/60 text-foreground",
    warning: "border-amber-500/30 text-amber-300",
    danger: "border-rose-500/30 text-rose-300",
  } as const;

  const content = (
    <>
      <p className="break-words text-[10px] uppercase tracking-[0.18em] text-muted-foreground">{label}</p>
      <p className="mt-2 break-words text-xl font-semibold md:text-2xl">{value}</p>
      {hint ? <p className="mt-1 break-words text-xs text-muted-foreground">{hint}</p> : null}
    </>
  );

  if (onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        className={cn(
          KPI_SURFACE_CLASS,
          "rounded-2xl border bg-background/55 px-4 py-3 text-left transition-colors hover:bg-background/70 focus-visible:ring-2 focus-visible:ring-ring/50",
          accent === "cyan" ? "border-cyan-500/30 text-cyan-300" : toneClasses[tone],
        )}
      >
        {content}
      </button>
    );
  }

  return (
    <div
      className={cn(
        KPI_SURFACE_CLASS,
        "rounded-2xl border bg-background/55 px-4 py-3",
        accent === "cyan" ? "border-cyan-500/30 text-cyan-300" : toneClasses[tone],
      )}
    >
      {content}
    </div>
  );
}

export default function RenovacaoCiclosPage() {
  const { hasRole } = usePermissions();
  const isAdmin = hasRole("ADMIN");
  const monthsQuery = useV1RenovacaoCiclosMesesList(undefined, {
    query: {
      staleTime: 5 * 60 * 1000,
      placeholderData: (previousData) => previousData,
    },
  });
  const [selectedCompetencia, setSelectedCompetencia] = React.useState("");
  const [selectedStatus, setSelectedStatus] = React.useState("todos");
  const [selectedAutocomplete, setSelectedAutocomplete] = React.useState("");
  const [visibleMonthsCount, setVisibleMonthsCount] = React.useState(3);
  const [layoutMode, setLayoutMode] = React.useState<LayoutMode>("grid");
  const [selectedYear, setSelectedYear] = React.useState("todos");
  const [selectedMonth, setSelectedMonth] = React.useState("todos");
  const [retornoCompetencia, setRetornoCompetencia] = React.useState("");
  const [retornoPeriod, setRetornoPeriod] = React.useState<"mes" | "trimestre">("mes");
  const [visibleReturnFilesCount, setVisibleReturnFilesCount] = React.useState(3);
  const [detailMetricDialogConfig, setDetailMetricDialogConfig] =
    React.useState<CycleMetricDialogConfig | null>(null);
  const [renewalEditTarget, setRenewalEditTarget] =
    React.useState<EnrichedCycleItem | null>(null);
  const [advancedFilters, setAdvancedFilters] = React.useState<AdvancedFilters>({
    periodPreset: "todos",
    dateStart: "",
    dateEnd: "",
    parcelStatus: "todos",
    agent: "todos",
  });
  const [draftAdvancedFilters, setDraftAdvancedFilters] = React.useState<
    AdvancedFilters & { status: string }
  >({
    periodPreset: "todos",
    dateStart: "",
    dateEnd: "",
    parcelStatus: "todos",
    agent: "todos",
    status: "todos",
  });
  const deferredAutocomplete = React.useDeferredValue(selectedAutocomplete);

  React.useEffect(() => {
    if (!selectedCompetencia && monthsQuery.data?.[0]?.id) {
      setSelectedCompetencia(monthsQuery.data[0].id);
    }
  }, [monthsQuery.data, selectedCompetencia]);

  React.useEffect(() => {
    setVisibleReturnFilesCount(3);
  }, [retornoCompetencia, retornoPeriod]);

  const searchValue = decodeAutocompleteValue(deferredAutocomplete);
  const canUseServerResumo = !hasUnsupportedResumoFilters(advancedFilters);
  const detailResumoQuery = useV1RenovacaoCiclosVisaoMensalRetrieve(
    {
      competencia: selectedCompetencia || undefined,
      search: searchValue || undefined,
      status: selectedStatus !== "todos" ? selectedStatus : undefined,
    },
    {
      query: {
        enabled: Boolean(selectedCompetencia) && canUseServerResumo,
        staleTime: 30 * 1000,
        placeholderData: (previousData) => previousData,
      },
    },
  );
  const detailListQuery = useV1RenovacaoCiclosList(
    { competencia: selectedCompetencia || undefined, page_size: 1000 },
    {
      query: {
        enabled: Boolean(selectedCompetencia),
        staleTime: 30 * 1000,
        placeholderData: (previousData) => previousData,
      },
    },
  );
  const importacaoQuery = useV1ImportacaoArquivoRetornoList(
    {
      competencia: retornoCompetencia || undefined,
      periodo: retornoCompetencia ? retornoPeriod : undefined,
      page_size: visibleReturnFilesCount,
      ordering: "-created_at",
    },
    {
      query: {
        enabled: true,
        staleTime: 30 * 1000,
        placeholderData: (previousData) => previousData,
      },
    },
  );

  const detailRows = useEnrichedCycleRows(detailListQuery.data?.results ?? []);

  const agentOptions = React.useMemo<SelectOption[]>(() => {
    const agents = [...new Set(detailRows.map((row) => row.agenteResponsavel).filter(Boolean))];
    return [
      { value: "todos", label: "Todos os agentes" },
      ...agents.map((agent) => ({ value: agent, label: agent })),
    ];
  }, [detailRows]);

  const autocompleteOptions = React.useMemo(
    () => buildAutocompleteOptions(detailRows),
    [detailRows],
  );

  const filteredDetailRows = React.useMemo(
    () =>
      detailRows.filter((row) =>
        matchesCycleRow(row, searchValue, selectedStatus, advancedFilters),
      ),
    [advancedFilters, detailRows, searchValue, selectedStatus],
  );

  const selectedCompetenciaLabel = formatCompetenciaHeading(selectedCompetencia);
  const detailMetricRows = React.useMemo(
    () => ({
      total: filteredDetailRows,
      ciclo_renovado: filteredDetailRows.filter((row) =>
        matchesMetricStatus(row, "ciclo_renovado"),
      ),
      apto_a_renovar: filteredDetailRows.filter((row) =>
        matchesMetricStatus(row, "apto_a_renovar"),
      ),
      em_aberto: filteredDetailRows.filter((row) => matchesMetricStatus(row, "em_aberto")),
      inadimplente: filteredDetailRows.filter((row) =>
        matchesMetricStatus(row, "inadimplente"),
      ),
      em_previsao: filteredDetailRows.filter((row) =>
        matchesMetricStatus(row, "em_previsao"),
      ),
    }),
    [filteredDetailRows],
  );
  const detailMetricCounts = React.useMemo(
    () => ({
      total: detailMetricRows.total.length,
      cicloRenovado: detailMetricRows.ciclo_renovado.length,
      aptoRenovar: detailMetricRows.apto_a_renovar.length,
      emAberto: detailMetricRows.em_aberto.length,
      inadimplente: detailMetricRows.inadimplente.length,
      emPrevisao: detailMetricRows.em_previsao.length,
    }),
    [detailMetricRows],
  );
  const detailMetricAutocompleteOptions = React.useMemo(
    () => buildAutocompleteOptions(detailMetricDialogConfig?.rows ?? []),
    [detailMetricDialogConfig?.rows],
  );
  const openDetailMetricDialog = React.useCallback(
    (
      key: keyof typeof detailMetricRows,
      title: string,
      description: string,
      emptyMessage: string,
    ) => {
      setDetailMetricDialogConfig({
        key,
        title,
        description,
        rows: detailMetricRows[key],
        monthLabel: selectedCompetenciaLabel,
        exportTitle: `${title} - ${selectedCompetenciaLabel}`,
        exportFilename: sanitizeFileName(
          `detalhamento-mensal-${selectedCompetencia || "atual"}-${key}`,
        ),
        emptyMessage,
      });
    },
    [detailMetricRows, selectedCompetencia, selectedCompetenciaLabel],
  );

  const years = React.useMemo(() => {
    return [...new Set((monthsQuery.data ?? []).map((month) => month.id.slice(0, 4)))];
  }, [monthsQuery.data]);

  const filteredMonths = React.useMemo(() => {
    return (monthsQuery.data ?? []).filter((month) => {
      const date = parseCompetenciaDate(month.id);
      if (!date) return true;
      if (selectedYear !== "todos" && date.getFullYear().toString() !== selectedYear) {
        return false;
      }
      if (selectedMonth !== "todos" && (date.getMonth() + 1).toString() !== selectedMonth) {
        return false;
      }
      if (!withinPreset(date, advancedFilters.periodPreset)) {
        return false;
      }
      if (!withinCustomRange(date, advancedFilters.dateStart, advancedFilters.dateEnd)) {
        return false;
      }
      return true;
    });
  }, [advancedFilters.dateEnd, advancedFilters.dateStart, advancedFilters.periodPreset, monthsQuery.data, selectedMonth, selectedYear]);

  const visibleMonths = React.useMemo(
    () => filteredMonths.slice(0, visibleMonthsCount).reverse(),
    [filteredMonths, visibleMonthsCount],
  );

  const cycleLookup = React.useMemo(() => {
    return new Map<string, EnrichedCycleItem>(
      detailRows.map((row) => [onlyDigits(row.cpf_cnpj), row]),
    );
  }, [detailRows]);

  const activeAdvancedFiltersCount = countActiveFilters(selectedStatus, advancedFilters);
  const isMonthsLoading = monthsQuery.isLoading && !(monthsQuery.data ?? []).length;
  const isDetailLoading =
    (detailListQuery.isLoading && !detailListQuery.data) ||
    (canUseServerResumo && detailResumoQuery.isLoading && !detailResumoQuery.data);
  const isImportacaoLoading = importacaoQuery.isLoading && !importacaoQuery.data;
  const resetMainFilters = React.useCallback(() => {
    setSelectedAutocomplete("");
    setSelectedStatus("todos");
    setSelectedYear("todos");
    setSelectedMonth("todos");
    setVisibleMonthsCount(3);
    setAdvancedFilters({
      periodPreset: "todos",
      dateStart: "",
      dateEnd: "",
      parcelStatus: "todos",
      agent: "todos",
    });
    setDraftAdvancedFilters({
      periodPreset: "todos",
      dateStart: "",
      dateEnd: "",
      parcelStatus: "todos",
      agent: "todos",
      status: "todos",
    });
  }, []);

  const columns: DataTableColumn<EnrichedCycleItem>[] = [
    {
      id: "associado",
      header: "Associado",
      cell: (row) => (
        <div className="space-y-2">
          <div className="flex items-center gap-3">
            <ChevronRightIcon className="size-4 shrink-0 text-muted-foreground transition-transform group-data-[expanded=true]:rotate-90" />
            <div className="min-w-0 space-y-1">
              <CopySnippet
                label="Nome"
                value={row.nome_associado}
                inline
                className="max-w-full"
              />
              <p className="text-xs text-muted-foreground">{row.contrato_codigo}</p>
            </div>
          </div>
        </div>
      ),
      headerClassName: "w-[22%]",
    },
    {
      id: "cpf",
      header: "CPF",
      cell: (row) => <CopySnippet label="CPF" value={row.cpf_cnpj} mono />,
      headerClassName: "w-[14%]",
    },
    {
      id: "matricula",
      header: "Matrícula",
      cell: (row) => <CopySnippet label="Matrícula" value={row.matricula} mono />,
      headerClassName: "w-[14%]",
    },
    {
      id: "agente",
      header: "Agente responsável",
      cell: (row) => row.agenteResponsavel,
      headerClassName: "w-[16%]",
    },
    {
      id: "parcelas",
      header: "Parcela",
      cell: (row) => (
        <span className="font-semibold text-cyan-300">
          {row.parcelas_pagas}/{row.parcelas_total}
        </span>
      ),
    },
    {
      id: "mensalidade",
      header: "Mensalidade",
      cell: (row) => formatCurrency(row.valor_parcela),
    },
    {
      id: "status",
      header: "Status",
      cell: (row) => <StatusBadge status={row.status_visual} />,
    },
  ];

  if (isAdmin) {
    columns.push({
      id: "acoes",
      header: "Ação",
      cell: (row) => (
        <Button
          variant="outline"
          size="sm"
          className="rounded-2xl"
          onClick={(event) => {
            event.stopPropagation();
            setRenewalEditTarget(row);
          }}
        >
          Reeditar
        </Button>
      ),
      headerClassName: "w-[10%]",
    });
  }

  return (
    <div className="space-y-8 pb-10">
      <div className="space-y-5 rounded-[2rem] border border-border/60 bg-card/75 p-6 shadow-2xl shadow-black/20">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div className="space-y-2">
            <h1 className="text-3xl font-semibold tracking-tight text-foreground md:text-[2.4rem]">
              Dashboard de Ciclos
            </h1>
            <p className="max-w-3xl text-sm text-muted-foreground">
              Gestão detalhada da competência, reconciliação por arquivo retorno e monitoramento contínuo dos ciclos.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <Sheet
              onOpenChange={(open) => {
                if (open) {
                  setDraftAdvancedFilters({
                    ...advancedFilters,
                    status: selectedStatus,
                  });
                }
              }}
            >
              <SheetTrigger asChild>
                <Button variant="outline" className="rounded-2xl">
                  <SlidersHorizontalIcon className="size-4" />
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
                    Filtre período, datas, status, parcelas e agente responsável.
                  </SheetDescription>
                </SheetHeader>

                <div className="space-y-5 overflow-y-auto px-4 pb-4">
                  <FilterField label="Período">
                    <Select
                      value={draftAdvancedFilters.periodPreset}
                      onValueChange={(value) =>
                        setDraftAdvancedFilters((current) => ({
                          ...current,
                          periodPreset: value as PeriodPreset,
                        }))
                      }
                    >
                      <SelectTrigger className="rounded-2xl bg-card/60">
                        <SelectValue placeholder="Período" />
                      </SelectTrigger>
                      <SelectContent>
                        {PERIOD_OPTIONS.map((option) => (
                          <SelectItem key={option.value} value={option.value}>
                            {option.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </FilterField>

                  <div className="grid gap-4 md:grid-cols-2">
                    <FilterField label="Data inicial">
                      <DatePicker
                        value={parseDateValue(draftAdvancedFilters.dateStart)}
                        onChange={(value) =>
                          setDraftAdvancedFilters((current) => ({
                            ...current,
                            dateStart: formatDateValue(value),
                          }))
                        }
                        placeholder="Data inicial"
                      />
                    </FilterField>

                    <FilterField label="Data final">
                      <DatePicker
                        value={parseDateValue(draftAdvancedFilters.dateEnd)}
                        onChange={(value) =>
                          setDraftAdvancedFilters((current) => ({
                            ...current,
                            dateEnd: formatDateValue(value),
                          }))
                        }
                        placeholder="Data final"
                      />
                    </FilterField>
                  </div>

                  <div className="grid gap-4 md:grid-cols-2">
                    <FilterField label="Status do ciclo">
                      <Select
                        value={draftAdvancedFilters.status}
                        onValueChange={(value) =>
                          setDraftAdvancedFilters((current) => ({
                            ...current,
                            status: value,
                          }))
                        }
                      >
                        <SelectTrigger className="rounded-2xl bg-card/60">
                          <SelectValue placeholder="Status do ciclo" />
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

                    <FilterField label="Status da parcela">
                      <Select
                        value={draftAdvancedFilters.parcelStatus}
                        onValueChange={(value) =>
                          setDraftAdvancedFilters((current) => ({
                            ...current,
                            parcelStatus: value,
                          }))
                        }
                      >
                        <SelectTrigger className="rounded-2xl bg-card/60">
                          <SelectValue placeholder="Status da parcela" />
                        </SelectTrigger>
                        <SelectContent>
                          {PARCELA_STATUS_OPTIONS.map((option) => (
                            <SelectItem key={option.value} value={option.value}>
                              {option.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </FilterField>
                  </div>

                  <FilterField label="Agente responsável">
                    <SearchableSelect
                      options={agentOptions}
                      value={draftAdvancedFilters.agent}
                      onChange={(value) =>
                        setDraftAdvancedFilters((current) => ({
                          ...current,
                          agent: value,
                        }))
                      }
                      placeholder="Todos os agentes"
                      searchPlaceholder="Buscar agente"
                      clearValue="todos"
                      clearLabel="Todos os agentes"
                    />
                  </FilterField>
                </div>

                <SheetFooter className="border-t border-border/60">
                  <Button
                    variant="outline"
                    type="button"
                    onClick={() => {
                      setSelectedStatus("todos");
                      setSelectedAutocomplete("");
                      setAdvancedFilters({
                        periodPreset: "todos",
                        dateStart: "",
                        dateEnd: "",
                        parcelStatus: "todos",
                        agent: "todos",
                      });
                      setDraftAdvancedFilters({
                        periodPreset: "todos",
                        dateStart: "",
                        dateEnd: "",
                        parcelStatus: "todos",
                        agent: "todos",
                        status: "todos",
                      });
                    }}
                  >
                    Limpar avançados
                  </Button>
                  <SheetClose asChild>
                    <Button
                      type="button"
                      onClick={() => {
                        setSelectedStatus(draftAdvancedFilters.status);
                        setAdvancedFilters({
                          periodPreset: draftAdvancedFilters.periodPreset,
                          dateStart: draftAdvancedFilters.dateStart,
                          dateEnd: draftAdvancedFilters.dateEnd,
                          parcelStatus: draftAdvancedFilters.parcelStatus,
                          agent: draftAdvancedFilters.agent,
                        });
                        setVisibleMonthsCount(3);
                      }}
                    >
                      Aplicar
                    </Button>
                  </SheetClose>
                </SheetFooter>
              </SheetContent>
            </Sheet>
          </div>
        </div>

        <div className="grid items-start gap-3 lg:grid-cols-[minmax(14rem,16rem)_minmax(0,1fr)] xl:grid-cols-[minmax(14rem,16rem)_minmax(0,1fr)_auto_auto]">
          <Select
            value={selectedCompetencia}
            onValueChange={setSelectedCompetencia}
          >
            <SelectTrigger className="rounded-2xl bg-background/60">
              <SelectValue placeholder="Competência base" />
            </SelectTrigger>
            <SelectContent>
              {(monthsQuery.data ?? []).map((month) => (
                <SelectItem key={month.id} value={month.id}>
                  {month.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <div className="flex min-w-0 flex-col gap-2 sm:flex-row">
            <SearchableSelect
              options={autocompleteOptions}
              value={selectedAutocomplete}
              onChange={setSelectedAutocomplete}
              placeholder="Buscar associado, CPF ou matricula"
              searchPlaceholder="Digite para localizar associado"
              className="min-w-0 flex-1 rounded-2xl"
            />
          </div>

          <Button variant="outline" className="rounded-2xl" onClick={resetMainFilters}>
            Limpar filtros
          </Button>

          <ReportExportDialog
            hideScope
            onExport={(_, fmt) =>
              exportRows(
                fmt,
                `Detalhamento mensal ${selectedCompetenciaLabel}`,
                sanitizeFileName(`detalhamento-mensal-${selectedCompetencia || "atual"}`),
                cycleExportColumns(selectedCompetenciaLabel),
                filteredDetailRows,
              )
            }
          />
        </div>
      </div>

      <section className="space-y-5">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <h2 className="text-xl font-semibold text-foreground">Gestão detalhada por mês</h2>
            <p className="text-sm text-muted-foreground">
              Cards mensais com visão executiva, tabela dinâmica por associado e exportação em XLS/PDF.
            </p>
          </div>

          <div className="flex w-full flex-wrap items-center gap-3 xl:w-auto xl:justify-end">
            <Select value={selectedYear} onValueChange={setSelectedYear}>
              <SelectTrigger className="min-w-36 rounded-2xl bg-card/60">
                <SelectValue placeholder="Todos os anos" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="todos">Todos os anos</SelectItem>
                {years.map((year) => (
                  <SelectItem key={year} value={year}>
                    {year}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={selectedMonth} onValueChange={setSelectedMonth}>
              <SelectTrigger className="min-w-40 rounded-2xl bg-card/60">
                <SelectValue placeholder="Todos os meses" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="todos">Todos os meses</SelectItem>
                {Array.from({ length: 12 }, (_, index) => (
                  <SelectItem key={index + 1} value={String(index + 1)}>
                    {capitalize(format(new Date(2026, index, 1), "MMMM", { locale: ptBR }))}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <div className="flex items-center rounded-2xl border border-border/60 bg-card/60 p-1">
              <Button
                variant={layoutMode === "grid" ? "secondary" : "ghost"}
                size="icon-sm"
                className="rounded-xl"
                onClick={() => setLayoutMode("grid")}
                aria-label="Modo grade"
              >
                <LayoutGridIcon className="size-4" />
              </Button>
              <Button
                variant={layoutMode === "list" ? "secondary" : "ghost"}
                size="icon-sm"
                className="rounded-xl"
                onClick={() => setLayoutMode("list")}
                aria-label="Modo lista"
              >
                <ListIcon className="size-4" />
              </Button>
            </div>
          </div>
        </div>

        <div
          className={cn(
            "grid gap-5",
            layoutMode === "grid" ? "xl:grid-cols-3" : "grid-cols-1",
          )}
        >
          {isMonthsLoading
            ? Array.from({ length: 3 }, (_, index) => <MonthlyCycleCardSkeleton key={index} />)
            : visibleMonths.map((month) => (
                <MonthlyCycleCard
                  key={month.id}
                  competenciaId={month.id}
                  layoutMode={layoutMode}
                  searchValue={searchValue}
                  selectedStatus={selectedStatus}
                  advancedFilters={advancedFilters}
                />
              ))}
        </div>

        {visibleMonths.length < filteredMonths.length ? (
          <div className="flex justify-center">
            <Button
              variant="outline"
              className="rounded-2xl"
              onClick={() => setVisibleMonthsCount((current) => current + 3)}
            >
              Carregar meses anteriores
            </Button>
          </div>
        ) : null}
      </section>

      <section className="space-y-5">
        <div>
          <h2 className="text-xl font-semibold text-foreground">Detalhamento mensal</h2>
          <p className="text-sm text-muted-foreground">
            Competência base {selectedCompetenciaLabel} com visão detalhada por associado e conciliação ETIPI.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-5">
          {isDetailLoading ? (
            <>
              <MetricTileSkeleton />
              <MetricTileSkeleton />
              <MetricTileSkeleton />
              <MetricTileSkeleton />
              <MetricTileSkeleton />
            </>
          ) : (
            <>
              <MetricTile
                label="Total"
                value={detailMetricCounts.total}
                onClick={() =>
                  openDetailMetricDialog(
                    "total",
                    `Total de associados em ${selectedCompetenciaLabel}`,
                    "Todos os associados conciliados na competência base selecionada.",
                    "Nenhum associado encontrado para a competência selecionada.",
                  )
                }
              />
              <MetricTile
                label="Ciclo renovado"
                value={detailMetricCounts.cicloRenovado}
                onClick={() =>
                  openDetailMetricDialog(
                    "ciclo_renovado",
                    `Ciclo renovado em ${selectedCompetenciaLabel}`,
                    "Associados com ciclo encerrado e renovação efetivada na competência base.",
                    "Nenhum associado renovado encontrado para a competência selecionada.",
                  )
                }
              />
              <MetricTile
                label="Apto a renovar"
                value={detailMetricCounts.aptoRenovar}
                accent="cyan"
                onClick={() =>
                  openDetailMetricDialog(
                    "apto_a_renovar",
                    `Aptos a renovar em ${selectedCompetenciaLabel}`,
                    "Associados prontos para renovação na competência base.",
                    "Nenhum associado apto a renovar encontrado para a competência selecionada.",
                  )
                }
              />
              <MetricTile
                label="Em aberto"
                value={detailMetricCounts.emAberto}
                tone="warning"
                onClick={() =>
                  openDetailMetricDialog(
                    "em_aberto",
                    `Em aberto em ${selectedCompetenciaLabel}`,
                    "Associados com parcela atual em aberto na competência base.",
                    "Nenhum associado em aberto encontrado para a competência selecionada.",
                  )
                }
              />
              <MetricTile
                label="Inadimplentes"
                value={detailMetricCounts.inadimplente}
                tone="danger"
                onClick={() =>
                  openDetailMetricDialog(
                    "inadimplente",
                    `Inadimplentes em ${selectedCompetenciaLabel}`,
                    "Associados com inadimplência consolidada na competência base.",
                    "Nenhum associado inadimplente encontrado para a competência selecionada.",
                  )
                }
              />
              <MetricTile
                label="Em previsão"
                value={detailMetricCounts.emPrevisao}
                onClick={() =>
                  openDetailMetricDialog(
                    "em_previsao",
                    `Em previsão em ${selectedCompetenciaLabel}`,
                    "Ciclos futuros que ainda não foram ativados pela primeira parcela paga.",
                    "Nenhum ciclo em previsão encontrado para a competência selecionada.",
                  )
                }
              />
            </>
          )}
        </div>

        <Card className="min-w-0 border-border/60 bg-card/80">
          <CardHeader className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div>
              <CardTitle>Detalhamento mensal já conciliado</CardTitle>
              <CardDescription>
                Copie nome, CPF e matrícula, confira o agente responsável e acompanhe as flags geradas pelo arquivo retorno.
              </CardDescription>
            </div>
            <ReportExportDialog
              hideScope
              onExport={(_, fmt) =>
                exportRows(
                  fmt,
                  `Detalhamento mensal ${selectedCompetenciaLabel}`,
                  sanitizeFileName(`detalhamento-mensal-${selectedCompetencia || "atual"}`),
                  cycleExportColumns(selectedCompetenciaLabel),
                  filteredDetailRows,
                )
              }
            />
          </CardHeader>
          <CardContent>
            {isDetailLoading ? (
              <TableSkeleton rows={6} />
            ) : (
              <DataTable
                columns={columns}
                data={filteredDetailRows}
                pageSize={10}
                pageSizeOptions={DETAIL_PAGE_SIZE_OPTIONS}
                className="rounded-[1.35rem] shadow-none"
                tableClassName="min-w-[82rem]"
                emptyMessage="Nenhum ciclo encontrado para a competência selecionada."
                renderExpanded={(row) => (
                  <div className="space-y-4">
                    {row.status_visual === "apto_a_renovar" && row.statusExplicacao ? (
                      <div className="rounded-2xl border border-cyan-500/25 bg-cyan-500/10 px-4 py-3 text-sm text-cyan-50">
                        {row.statusExplicacao}
                      </div>
                    ) : null}
                    <div className="grid gap-4 md:grid-cols-[1.2fr_1fr_1fr_1.2fr]">
                      <div>
                        <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
                          Status ETIPI
                        </p>
                        <p className="mt-2 font-medium text-foreground">
                          {formatEtipiStatusLabel(
                            row.status_codigo_etipi,
                            row.status_descricao_etipi,
                          )}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
                          Resultado importação
                        </p>
                        <div className="mt-2">
                          <StatusBadge status={row.resultado_importacao} />
                        </div>
                      </div>
                      <div>
                        <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
                          Pagamento
                        </p>
                        <p className="mt-2 font-medium text-foreground">{formatDate(row.data_pagamento)}</p>
                      </div>
                      <div className="space-y-3">
                        <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
                          Ações rápidas
                        </p>
                        <div className="flex flex-wrap gap-2">
                          <Button
                            size="sm"
                            className="rounded-2xl"
                            onClick={(event) => {
                              event.stopPropagation();
                              toast.success(`Fluxo de renovação iniciado para ${row.nome_associado}.`);
                            }}
                          >
                            <RefreshCcwIcon className="size-4" />
                            Renovar ciclo
                          </Button>
                          <Button
                            variant="destructive"
                            size="sm"
                            className="rounded-2xl"
                            onClick={(event) => {
                              event.stopPropagation();
                              toast.success(`Solicitação de desativação aberta para ${row.nome_associado}.`);
                            }}
                          >
                            <UserMinusIcon className="size-4" />
                            Desativar associado
                          </Button>
                          <Button asChild variant="outline" size="sm" className="rounded-2xl">
                            <Link href={row.associadoUrl} onClick={(event) => event.stopPropagation()}>
                              Abrir associado
                            </Link>
                          </Button>
                          {isAdmin ? (
                            <Button
                              variant="outline"
                              size="sm"
                              className="rounded-2xl"
                              onClick={(event) => {
                                event.stopPropagation();
                                setRenewalEditTarget(row);
                              }}
                            >
                              Reeditar renovação
                            </Button>
                          ) : null}
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              />
            )}
          </CardContent>
        </Card>
      </section>

      <section className="space-y-5">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <h2 className="text-xl font-semibold text-foreground">Arquivos retorno</h2>
            <p className="text-sm text-muted-foreground">
              Listagem completa dos arquivos retorno processados, com progresso financeiro e detalhamento expansível por associado.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <CalendarCompetencia
              value={parseMonthValue(retornoCompetencia)}
              onChange={(value) => setRetornoCompetencia(formatMonthValue(value))}
            />
            <Select
              value={retornoPeriod}
              onValueChange={(value) => setRetornoPeriod(value as "mes" | "trimestre")}
            >
              <SelectTrigger className="min-w-40 rounded-2xl bg-card/60">
                <SelectValue placeholder="Mês ou trimestre" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="mes">Por mês</SelectItem>
                <SelectItem value="trimestre">Por trimestre</SelectItem>
              </SelectContent>
            </Select>
            <Button
              variant="outline"
              className="rounded-2xl"
              onClick={() => setRetornoCompetencia(selectedCompetencia)}
            >
              Competência base
            </Button>
            <Button
              variant="outline"
              className="rounded-2xl"
              onClick={() => {
                setRetornoCompetencia("");
                setRetornoPeriod("mes");
              }}
            >
              Limpar filtro
            </Button>
          </div>
        </div>

        <div className="grid gap-5 xl:grid-cols-2 2xl:grid-cols-3">
          {isImportacaoLoading
            ? Array.from({ length: 3 }, (_, index) => <ReturnFileCardSkeleton key={index} />)
            : (importacaoQuery.data?.results ?? []).map((arquivo) => (
                <ReturnFileCard
                  key={arquivo.id}
                  arquivo={arquivo}
                  cycleLookup={cycleLookup}
                  searchValue={searchValue}
                  advancedFilters={advancedFilters}
                />
              ))}
        </div>

        {(importacaoQuery.data?.count ?? 0) > (importacaoQuery.data?.results ?? []).length ? (
          <div className="flex justify-center">
            <Button
              variant="outline"
              className="rounded-2xl"
              onClick={() => setVisibleReturnFilesCount((current) => current + 3)}
            >
              Ver mais arquivos
            </Button>
          </div>
        ) : null}

        {!(importacaoQuery.data?.results ?? []).length ? (
          <Card className="min-w-0 border-border/60 bg-card/80">
            <CardContent className="py-10 text-center text-sm text-muted-foreground">
              Nenhum arquivo retorno encontrado para{" "}
              {retornoCompetencia ? formatCompetenciaHeading(retornoCompetencia) : "o historico atual"}.
            </CardContent>
          </Card>
        ) : null}
      </section>

      <MetricDetailDialog
        open={Boolean(detailMetricDialogConfig)}
        onOpenChange={(open) => {
          if (!open) {
            setDetailMetricDialogConfig(null);
          }
        }}
        title={detailMetricDialogConfig?.title ?? `Detalhamento mensal ${selectedCompetenciaLabel}`}
        description={
          detailMetricDialogConfig?.description ??
          "Associados relacionados ao indicador selecionado da competência base."
        }
        rows={detailMetricDialogConfig?.rows ?? []}
        autocompleteOptions={detailMetricAutocompleteOptions}
        matchesSearch={matchesCycleSearchValue}
        placeholder="Buscar associado neste indicador"
        searchPlaceholder="Buscar por nome, CPF ou matrícula"
        emptyLabel={
          detailMetricDialogConfig?.emptyMessage ??
          "Nenhum associado encontrado para este indicador."
        }
        exportTitle={
          detailMetricDialogConfig?.exportTitle ??
          `Detalhamento mensal ${selectedCompetenciaLabel}`
        }
        exportFilename={
          detailMetricDialogConfig?.exportFilename ??
          sanitizeFileName(`detalhamento-mensal-${selectedCompetencia || "atual"}-kpi`)
        }
        exportColumns={cycleExportColumns(detailMetricDialogConfig?.monthLabel ?? selectedCompetenciaLabel)}
        renderTable={(rows) => (
          <div className={TABLE_VIEWPORT_CLASS}>
            <CycleMembersTable
              rows={rows}
              monthLabel={detailMetricDialogConfig?.monthLabel ?? selectedCompetenciaLabel}
              pageSize={10}
              pageSizeOptions={DETAIL_PAGE_SIZE_OPTIONS}
              tableClassName="min-w-[82rem]"
              emptyMessage={
                detailMetricDialogConfig?.emptyMessage ??
                "Nenhum associado encontrado para este indicador."
              }
            />
          </div>
        )}
      />

      <RenovacaoAdminEditDialog
        open={Boolean(renewalEditTarget)}
        onOpenChange={(open) => {
          if (!open) {
            setRenewalEditTarget(null);
          }
        }}
        associadoId={renewalEditTarget?.associado_id ?? null}
        contractId={renewalEditTarget?.contratoReferenciaRenovacaoId ?? null}
        contractCode={renewalEditTarget?.contratoReferenciaRenovacaoCodigo}
        associadoNome={renewalEditTarget?.nome_associado}
      />
    </div>
  );
}
