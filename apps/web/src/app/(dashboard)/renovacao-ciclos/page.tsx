"use client";

import * as React from "react";
import Link from "next/link";
import { useQueries } from "@tanstack/react-query";
import { format, isWithinInterval, startOfQuarter, subDays } from "date-fns";
import { ptBR } from "date-fns/locale";
import {
  CalendarDaysIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  CircleAlertIcon,
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
import ExportButton from "@/components/shared/export-button";
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
import { ScrollArea } from "@/components/ui/scroll-area";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  useV1ImportacaoArquivoRetornoDescontadosList,
  useV1ImportacaoArquivoRetornoList,
  useV1ImportacaoArquivoRetornoNaoDescontadosList,
  useV1ImportacaoArquivoRetornoPendenciasManuaisList,
  useV1RenovacaoCiclosList,
  useV1RenovacaoCiclosMesesList,
  useV1RenovacaoCiclosVisaoMensalRetrieve,
} from "@/gen";
import type {
  ArquivoRetornoItem,
  ArquivoRetornoList,
  RenovacaoCicloItem,
} from "@/gen/models";
import type {
  AssociadoDetail,
  AssociadoListItem,
  PaginatedResponse,
} from "@/lib/api/types";
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
import { maskCPFCNPJ } from "@/lib/masks";
import { cn } from "@/lib/utils";

const STATUS_OPTIONS = [
  { value: "todos", label: "Todos os status" },
  { value: "ciclo_renovado", label: "Ciclo renovado" },
  { value: "apto_a_renovar", label: "Apto a renovar" },
  { value: "em_aberto", label: "Em aberto" },
  { value: "ciclo_iniciado", label: "Ciclo iniciado" },
  { value: "inadimplente", label: "Inadimplente" },
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
type MonitoringMode = "trimestral" | "semestral";

type AdvancedFilters = {
  periodPreset: PeriodPreset;
  dateStart: string;
  dateEnd: string;
  parcelStatus: string;
  agent: string;
};

type EnrichedCycleItem = RenovacaoCicloItem & {
  matricula: string;
  agenteResponsavel: string;
  associadoUrl: string;
};

type EnrichedReturnItem = ArquivoRetornoItem & {
  associadoId?: number;
  agenteResponsavel: string;
  matriculaResolvida: string;
  esperado: string | number;
  recebido: string | number;
  situacao: string;
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

function extractResumoValue(arquivo: { resumo?: Record<string, unknown> } | undefined, key: string) {
  const value = arquivo?.resumo?.[key];
  if (typeof value === "number") return value;
  if (typeof value === "string") return Number.parseInt(value, 10) || 0;
  return 0;
}

function buildAutocompleteOptions(rows: EnrichedCycleItem[]) {
  const seen = new Set<string>();
  const options: SelectOption[] = [];

  rows.forEach((row) => {
    const entries = [
      {
        key: `nome::${row.nome_associado}`,
        label: `${row.nome_associado} • ${maskCPFCNPJ(row.cpf_cnpj)} • ${row.matricula}`,
      },
      {
        key: `cpf::${row.cpf_cnpj}`,
        label: `${maskCPFCNPJ(row.cpf_cnpj)} • ${row.nome_associado}`,
      },
      {
        key: `matricula::${row.matricula}`,
        label: `${row.matricula} • ${row.nome_associado}`,
      },
    ];

    entries.forEach((entry) => {
      if (seen.has(entry.key)) return;
      seen.add(entry.key);
      options.push({ value: entry.key, label: entry.label });
    });
  });

  return options;
}

function decodeAutocompleteValue(value: string) {
  const [, decoded = ""] = value.split("::");
  return decoded;
}

function buildCycleParcelCards(row: RenovacaoCicloItem) {
  return Array.from({ length: row.parcelas_total }, (_, index) => {
    const parcela = index + 1;
    const isCurrent = parcela === Math.min(row.parcelas_total, Math.max(row.parcelas_pagas, 1));
    const status =
      parcela < row.parcelas_pagas || (row.parcelas_pagas === row.parcelas_total && parcela <= row.parcelas_pagas)
        ? "Pago"
        : isCurrent
          ? capitalize(resolveParcelaStatusLabel(row.status_parcela))
          : "Pendente";

    return {
      parcela,
      status,
      paid: status === "Pago",
      active: isCurrent,
    };
  });
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

function exportAsPrintableHtml<T>(
  title: string,
  columns: TableExportColumn<T>[],
  rows: T[],
) {
  const popup = window.open("", "_blank", "noopener,noreferrer,width=1200,height=900");
  if (!popup) {
    toast.error("Não foi possível abrir a visualização para PDF.");
    return;
  }

  const headers = columns.map((column) => `<th>${column.header}</th>`).join("");
  const body = rows
    .map(
      (row) =>
        `<tr>${columns
          .map((column) => `<td>${String(column.value(row) ?? "-")}</td>`)
          .join("")}</tr>`,
    )
    .join("");

  popup.document.write(`
    <html lang="pt-BR">
      <head>
        <title>${title}</title>
        <style>
          body { font-family: Arial, sans-serif; padding: 24px; color: #111827; }
          h1 { margin: 0 0 16px; font-size: 22px; }
          table { width: 100%; border-collapse: collapse; }
          th, td { border: 1px solid #d1d5db; padding: 8px 10px; text-align: left; font-size: 12px; }
          th { background: #f3f4f6; text-transform: uppercase; letter-spacing: 0.04em; }
        </style>
      </head>
      <body>
        <h1>${title}</h1>
        <table>
          <thead><tr>${headers}</tr></thead>
          <tbody>${body}</tbody>
        </table>
      </body>
    </html>
  `);
  popup.document.close();
  popup.focus();
  popup.print();
}

function exportRows<T>(
  format: "csv" | "pdf" | "excel",
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
  const extension = format === "csv" ? "csv" : "xls";
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
    {
      header: "Status",
      value: (row) => row.status_desconto || row.resultado_processamento || "pendente",
    },
    { header: "Esperado", value: (row) => formatCurrency(row.esperado) },
    { header: "Recebido", value: (row) => formatCurrency(row.recebido) },
    { header: "Situação", value: (row) => row.situacao },
  ];
}

function useEnrichedCycleRows(rows: RenovacaoCicloItem[]) {
  const uniqueAssociadoIds = React.useMemo(
    () => [...new Set(rows.map((row) => row.associado_id).filter(Boolean))],
    [rows],
  );

  const detailQueries = useQueries({
    queries: uniqueAssociadoIds.map((associadoId) => ({
      queryKey: ["associado-renovacao-ciclo", associadoId],
      queryFn: () => apiFetch<AssociadoDetail>(`associados/${associadoId}`),
      staleTime: 5 * 60 * 1000,
      retry: false,
    })),
  });

  const detailsById = React.useMemo(() => {
    return new Map<number, AssociadoDetail>(
      uniqueAssociadoIds
        .map((associadoId, index) => [associadoId, detailQueries[index]?.data] as const)
        .filter((entry): entry is [number, AssociadoDetail] => Boolean(entry[1])),
    );
  }, [detailQueries, uniqueAssociadoIds]);

  return React.useMemo<EnrichedCycleItem[]>(() => {
    return rows.map((row) => {
      const detail = detailsById.get(row.associado_id);
      return {
        ...row,
        matricula:
          detail?.matricula_orgao ||
          detail?.contato?.matricula_servidor ||
          detail?.matricula ||
          row.contrato_codigo,
        agenteResponsavel: detail?.agente?.full_name || "Sem agente vinculado",
        associadoUrl: `/associados/${row.associado_id}`,
      };
    });
  }, [detailsById, rows]);
}

function useAssociadosByCpf(cpfs: string[]) {
  const uniqueCpfs = React.useMemo(
    () => [...new Set(cpfs.map(onlyDigits).filter(Boolean))],
    [cpfs],
  );

  const associadoQueries = useQueries({
    queries: uniqueCpfs.map((cpf) => ({
      queryKey: ["associado-by-cpf", cpf],
      queryFn: () =>
        apiFetch<PaginatedResponse<AssociadoListItem>>("associados", {
          query: { search: cpf, page_size: 1 },
        }),
      staleTime: 5 * 60 * 1000,
      retry: false,
    })),
  });

  return React.useMemo(() => {
    return new Map<string, AssociadoListItem>(
      uniqueCpfs
        .map((cpf, index) => [cpf, associadoQueries[index]?.data?.results?.[0]] as const)
        .filter((entry): entry is [string, AssociadoListItem] => Boolean(entry[1])),
    );
  }, [associadoQueries, uniqueCpfs]);
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
};

function CycleMembersTable({
  rows,
  monthLabel,
  compact = false,
  emptyMessage = "Nenhum associado encontrado para este mês.",
}: CycleMembersTableProps) {
  const [expandedRow, setExpandedRow] = React.useState<number | null>(null);

  return (
    <div className="overflow-hidden rounded-[1.35rem] border border-border/60 bg-background/55">
      <Table>
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
          {rows.length ? (
            rows.map((row) => {
              const parcelCards = buildCycleParcelCards(row);
              const isExpanded = expandedRow === row.id;

              return (
                <React.Fragment key={row.id}>
                  <TableRow
                    className="cursor-pointer border-border/60 hover:bg-white/3"
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
                            <Link
                              href={row.associadoUrl}
                              className="text-sm text-primary transition-colors hover:text-primary/80"
                              onClick={(event) => event.stopPropagation()}
                            >
                              Ver detalhes do associado
                            </Link>
                          </div>

                          <div className="grid gap-3 sm:grid-cols-3">
                            {parcelCards.map((parcelCard) => (
                              <div
                                key={`${row.id}-${parcelCard.parcela}`}
                                className={cn(
                                  "rounded-2xl border border-border/60 px-4 py-3",
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
    </div>
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
  const monthLabel = formatCompetenciaHeading(competenciaId);

  const listQuery = useV1RenovacaoCiclosList(
    { competencia: competenciaId, page_size: 50 },
    { query: { enabled: Boolean(competenciaId) } },
  );
  const enrichedRows = useEnrichedCycleRows(listQuery.data?.results ?? []);
  const filteredRows = React.useMemo(
    () =>
      enrichedRows.filter((row) =>
        matchesCycleRow(row, searchValue, selectedStatus, advancedFilters),
      ),
    [advancedFilters, enrichedRows, searchValue, selectedStatus],
  );
  const canUseServerResumo = !hasUnsupportedResumoFilters(advancedFilters);
  const resumoMensalQuery = useV1RenovacaoCiclosVisaoMensalRetrieve(
    {
      competencia: competenciaId,
      search: searchValue || undefined,
      status: selectedStatus !== "todos" ? selectedStatus : undefined,
    },
    {
      query: {
        enabled: Boolean(competenciaId) && canUseServerResumo,
      },
    },
  );
  const monthlyMetrics = React.useMemo(() => {
    if (canUseServerResumo && resumoMensalQuery.data) {
      return buildMonthlyMetricsFromResumo(resumoMensalQuery.data);
    }
    return buildMonthlyMetrics(filteredRows);
  }, [canUseServerResumo, filteredRows, resumoMensalQuery.data]);

  const visibleRows = layoutMode === "grid" ? filteredRows.slice(0, 4) : filteredRows.slice(0, 6);

  return (
    <Card className="border-border/60 bg-card/80 shadow-xl shadow-black/15">
      <CardHeader className="gap-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle className="text-2xl">{monthLabel}</CardTitle>
            <CardDescription className="mt-2">
              Esperado: <span className="font-semibold text-foreground">{formatCurrency(monthlyMetrics.esperado)}</span>
            </CardDescription>
            <CardDescription>
              Arrecadado: <span className="font-semibold text-emerald-300">{formatCurrency(monthlyMetrics.arrecadado)}</span>
            </CardDescription>
          </div>
          <ExportButton
            onExport={(format) =>
              exportRows(
                format,
                `Gestão detalhada ${monthLabel}`,
                sanitizeFileName(`gestao-ciclo-${competenciaId}`),
                cycleExportColumns(monthLabel),
                filteredRows,
              )
            }
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
          <MetricTile label="Renovados" value={monthlyMetrics.cicloRenovado} />
          <MetricTile label="Aptos a renovar" value={monthlyMetrics.aptoRenovar} />
          <MetricTile label="Em aberto" value={monthlyMetrics.emAberto} tone="warning" />
          <MetricTile label="Inadimplentes" value={monthlyMetrics.inadimplente} tone="danger" />
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-sm font-medium text-foreground">Detalhamento de associados</p>
            <p className="text-xs text-muted-foreground">{filteredRows.length} registros disponíveis</p>
          </div>
          <Dialog>
            <DialogTrigger asChild>
              <Button variant="outline" size="sm" className="rounded-2xl">
                <EyeIcon className="size-4" />
                Ampliar tabela
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-6xl border-border/60 bg-background/95">
              <DialogHeader>
                <DialogTitle>Gestão detalhada de {monthLabel}</DialogTitle>
                <DialogDescription>
                  Associados, agente responsável, parcelas do ciclo e status da parcela da competência.
                </DialogDescription>
              </DialogHeader>
              <div className="flex justify-end">
                <ExportButton
                  onExport={(format) =>
                    exportRows(
                      format,
                      `Gestão detalhada ${monthLabel}`,
                      sanitizeFileName(`gestao-ciclo-${competenciaId}`),
                      cycleExportColumns(monthLabel),
                      filteredRows,
                    )
                  }
                />
              </div>
              <ScrollArea className="max-h-[60vh]">
                <CycleMembersTable rows={filteredRows} monthLabel={monthLabel} />
              </ScrollArea>
            </DialogContent>
          </Dialog>
        </div>

        <ScrollArea className="max-h-[22rem]">
          <CycleMembersTable
            rows={visibleRows}
            monthLabel={monthLabel}
            compact
            emptyMessage="Nenhum associado corresponde aos filtros deste card."
          />
        </ScrollArea>
      </CardContent>
    </Card>
  );
}

type ReturnFileCardProps = {
  arquivo: ArquivoRetornoList;
  cycleLookup: Map<string, EnrichedCycleItem>;
  searchValue: string;
  advancedFilters: AdvancedFilters;
};

function buildReturnSituation(row: ArquivoRetornoItem) {
  if (row.gerou_encerramento && row.gerou_novo_ciclo) {
    return "Encerramento e novo ciclo gerados";
  }
  if (row.gerou_encerramento) {
    return "Encerramento do ciclo";
  }
  if (row.gerou_novo_ciclo) {
    return "Novo ciclo iniciado";
  }
  if (row.motivo_rejeicao) {
    return row.motivo_rejeicao;
  }
  if (row.observacao) {
    return row.observacao;
  }
  return capitalize((row.resultado_processamento || row.status_desconto || "pendente").replaceAll("_", " "));
}

function ReturnFileCard({
  arquivo,
  cycleLookup,
  searchValue,
  advancedFilters,
}: ReturnFileCardProps) {
  const [isExpanded, setIsExpanded] = React.useState(false);

  const descontadosQuery = useV1ImportacaoArquivoRetornoDescontadosList(
    arquivo.id,
    { page_size: 20 },
    { query: { enabled: isExpanded } },
  );
  const naoDescontadosQuery = useV1ImportacaoArquivoRetornoNaoDescontadosList(
    arquivo.id,
    { page_size: 20 },
    { query: { enabled: isExpanded } },
  );
  const pendenciasQuery = useV1ImportacaoArquivoRetornoPendenciasManuaisList(
    arquivo.id,
    { page_size: 20 },
    { query: { enabled: isExpanded } },
  );

  const rawItems = React.useMemo(() => {
    if (!isExpanded) return [];

    const collected = [
      ...(descontadosQuery.data?.results ?? []),
      ...(naoDescontadosQuery.data?.results ?? []),
      ...(pendenciasQuery.data?.results ?? []),
    ];

    const byId = new Map<number, ArquivoRetornoItem>();
    collected.forEach((item) => byId.set(item.id, item));
    return [...byId.values()];
  }, [
    descontadosQuery.data?.results,
    isExpanded,
    naoDescontadosQuery.data?.results,
    pendenciasQuery.data?.results,
  ]);

  const associadosByCpf = useAssociadosByCpf(rawItems.map((item) => item.cpf_cnpj));

  const detailRows = React.useMemo<EnrichedReturnItem[]>(() => {
    return rawItems
      .map((item) => {
        const normalizedCpf = onlyDigits(item.cpf_cnpj);
        const associado = associadosByCpf.get(normalizedCpf);
        const cycleMatch = cycleLookup.get(normalizedCpf);

        const resolved: EnrichedReturnItem = {
          ...item,
          associadoId: associado?.id ?? cycleMatch?.associado_id,
          agenteResponsavel:
            associado?.agente?.full_name ||
            cycleMatch?.agenteResponsavel ||
            "Sem agente vinculado",
          matriculaResolvida:
            associado?.matricula || cycleMatch?.matricula || item.matricula_servidor,
          esperado: cycleMatch?.valor_parcela || item.valor_descontado || 0,
          recebido: item.valor_descontado || 0,
          situacao: buildReturnSituation(item),
        };

        const comparableText = [
          resolved.associado_nome,
          resolved.nome_servidor,
          resolved.cpf_cnpj,
          resolved.matriculaResolvida,
          resolved.agenteResponsavel,
          resolved.situacao,
        ]
          .map(normalizeText)
          .join(" ");

        if (searchValue && !comparableText.includes(normalizeText(searchValue))) {
          return null;
        }

        if (
          advancedFilters.agent !== "todos" &&
          normalizeText(resolved.agenteResponsavel) !== normalizeText(advancedFilters.agent)
        ) {
          return null;
        }

        return resolved;
      })
      .filter((item): item is EnrichedReturnItem => item !== null);
  }, [advancedFilters.agent, associadosByCpf, cycleLookup, rawItems, searchValue]);

  const processados = arquivo.processados ?? 0;
  const total = arquivo.total_registros ?? 0;
  const progresso = total ? (processados / total) * 100 : 0;
  const fileTitle = formatCompetenciaHeading(
    arquivo.competencia_display,
    arquivo.competencia,
  );
  const cicloAberto = extractResumoValue(arquivo, "ciclo_aberto");

  return (
    <Card className="border-border/60 bg-card/80 shadow-xl shadow-black/15">
      <CardHeader className="gap-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="text-xl">{arquivo.arquivo_nome}</CardTitle>
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
              Processados: <span className="font-medium text-foreground">{processados}</span> de{" "}
              <span className="font-medium text-foreground">{total}</span>
            </span>
            <span className="font-medium text-foreground">{progresso.toFixed(1)}%</span>
          </div>
          <Progress value={progresso} className="h-2.5" />
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <MetricTile label="Descontados" value={extractResumoValue(arquivo, "efetivados") || extractResumoValue(arquivo, "baixa_efetuada")} accent="cyan" />
          <MetricTile label="Não descontados" value={extractResumoValue(arquivo, "nao_descontados") || extractResumoValue(arquivo, "nao_descontado")} tone="warning" />
          <MetricTile label="Pendências" value={extractResumoValue(arquivo, "pendencias_manuais")} tone="warning" />
          <MetricTile label="Não encontrados" value={extractResumoValue(arquivo, "nao_encontrado")} tone="danger" />
          {cicloAberto > 0 ? (
            <MetricTile label="Ciclo aberto" value={cicloAberto} tone="warning" />
          ) : null}
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
            <ExportButton
              onExport={(format) =>
                exportRows(
                  format,
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
          <ScrollArea className="max-h-[26rem]">
            <div className="overflow-hidden rounded-[1.35rem] border border-border/60 bg-background/55">
              <Table>
                <TableHeader>
                  <TableRow className="border-border/60 hover:bg-transparent">
                    <TableHead className="px-4 text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                      Nome
                    </TableHead>
                    <TableHead className="px-4 text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                      CPF
                    </TableHead>
                    <TableHead className="px-4 text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                      Matrícula
                    </TableHead>
                    <TableHead className="px-4 text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                      Agente responsável
                    </TableHead>
                    <TableHead className="px-4 text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                      Status
                    </TableHead>
                    <TableHead className="px-4 text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                      Esperado
                    </TableHead>
                    <TableHead className="px-4 text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                      Recebido
                    </TableHead>
                    <TableHead className="px-4 text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                      Situação
                    </TableHead>
                    <TableHead className="px-4 text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                      Ações
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {detailRows.length ? (
                    detailRows.map((row) => (
                      <TableRow key={row.id} className="border-border/60 hover:bg-white/3">
                        <TableCell className="px-4 py-3">
                          <CopySnippet
                            label="Nome"
                            value={row.associado_nome || row.nome_servidor}
                            inline
                            className="max-w-full"
                          />
                        </TableCell>
                        <TableCell className="px-4 py-3">
                          <CopySnippet label="CPF" value={row.cpf_cnpj} mono />
                        </TableCell>
                        <TableCell className="px-4 py-3">
                          <CopySnippet label="Matrícula" value={row.matriculaResolvida} mono />
                        </TableCell>
                        <TableCell className="px-4 py-3 text-sm text-foreground">
                          {row.agenteResponsavel}
                        </TableCell>
                        <TableCell className="px-4 py-3">
                          <StatusBadge status={row.status_desconto || row.resultado_processamento || "pendente"} />
                        </TableCell>
                        <TableCell className="px-4 py-3 text-sm text-foreground">
                          {formatCurrency(row.esperado)}
                        </TableCell>
                        <TableCell className="px-4 py-3 text-sm font-medium text-foreground">
                          {formatCurrency(row.recebido)}
                        </TableCell>
                        <TableCell className="px-4 py-3 text-sm text-muted-foreground">
                          {row.situacao}
                        </TableCell>
                        <TableCell className="px-4 py-3">
                          {row.associadoId ? (
                            <Button asChild variant="outline" size="sm" className="rounded-2xl">
                              <Link href={`/associados/${row.associadoId}`}>Ver detalhes do associado</Link>
                            </Button>
                          ) : (
                            <Button disabled variant="outline" size="sm" className="rounded-2xl">
                              Ver detalhes do associado
                            </Button>
                          )}
                        </TableCell>
                      </TableRow>
                    ))
                  ) : (
                    <TableRow className="border-border/60">
                      <TableCell colSpan={9} className="px-4 py-10 text-center text-sm text-muted-foreground">
                        Nenhum item detalhado disponível para este arquivo com os filtros atuais.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>
          </ScrollArea>
        ) : null}
      </CardContent>
    </Card>
  );
}

function MetricTile({
  label,
  value,
  tone = "neutral",
  accent,
}: {
  label: string;
  value: number;
  tone?: "neutral" | "warning" | "danger";
  accent?: "cyan";
}) {
  const toneClasses = {
    neutral: "border-border/60 text-foreground",
    warning: "border-amber-500/30 text-amber-300",
    danger: "border-rose-500/30 text-rose-300",
  } as const;

  return (
    <div
      className={cn(
        "rounded-2xl border bg-background/55 px-4 py-3",
        accent === "cyan" ? "border-cyan-500/30 text-cyan-300" : toneClasses[tone],
      )}
    >
      <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">{label}</p>
      <p className="mt-2 text-2xl font-semibold">{value}</p>
    </div>
  );
}

function MonitoringCard({
  title,
  value,
  tone = "neutral",
}: {
  title: string;
  value: number;
  tone?: "neutral" | "warning" | "danger";
}) {
  return (
    <div
      className={cn(
        "rounded-[1.35rem] border bg-card/80 px-5 py-4 shadow-lg shadow-black/10",
        tone === "danger"
          ? "border-rose-500/35"
          : tone === "warning"
            ? "border-amber-500/35"
            : "border-border/60",
      )}
    >
      <p className="text-sm text-muted-foreground">{title}</p>
      <p
        className={cn(
          "mt-3 text-4xl font-semibold",
          tone === "danger"
            ? "text-rose-300"
            : tone === "warning"
              ? "text-amber-300"
              : "text-foreground",
        )}
      >
        {value}
      </p>
    </div>
  );
}

export default function RenovacaoCiclosPage() {
  const monthsQuery = useV1RenovacaoCiclosMesesList();
  const [selectedCompetencia, setSelectedCompetencia] = React.useState("");
  const [selectedStatus, setSelectedStatus] = React.useState("todos");
  const [selectedAutocomplete, setSelectedAutocomplete] = React.useState("");
  const [visibleMonthsCount, setVisibleMonthsCount] = React.useState(3);
  const [layoutMode, setLayoutMode] = React.useState<LayoutMode>("grid");
  const [selectedYear, setSelectedYear] = React.useState("todos");
  const [selectedMonth, setSelectedMonth] = React.useState("todos");
  const [retornoCompetencia, setRetornoCompetencia] = React.useState("");
  const [retornoPeriod, setRetornoPeriod] = React.useState<"mes" | "trimestre">("mes");
  const [monitoringMode, setMonitoringMode] = React.useState<MonitoringMode>("trimestral");
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

  React.useEffect(() => {
    if (!selectedCompetencia && monthsQuery.data?.[0]?.id) {
      setSelectedCompetencia(monthsQuery.data[0].id);
    }
  }, [monthsQuery.data, selectedCompetencia]);

  React.useEffect(() => {
    if (!retornoCompetencia && (selectedCompetencia || monthsQuery.data?.[0]?.id)) {
      setRetornoCompetencia(selectedCompetencia || monthsQuery.data?.[0]?.id || "");
    }
  }, [monthsQuery.data, retornoCompetencia, selectedCompetencia]);

  const searchValue = decodeAutocompleteValue(selectedAutocomplete);
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
      },
    },
  );
  const detailListQuery = useV1RenovacaoCiclosList(
    { competencia: selectedCompetencia || undefined, page_size: 100 },
    { query: { enabled: Boolean(selectedCompetencia) } },
  );
  const importacaoQuery = useV1ImportacaoArquivoRetornoList(
    {
      competencia: retornoCompetencia || undefined,
      periodo: retornoPeriod,
      page_size: 12,
      ordering: "-created_at",
    },
    { query: { enabled: Boolean(retornoCompetencia) } },
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

  const detailMetrics = React.useMemo(
    () =>
      canUseServerResumo && detailResumoQuery.data
        ? buildMonthlyMetricsFromResumo(detailResumoQuery.data)
        : buildMonthlyMetrics(filteredDetailRows),
    [canUseServerResumo, detailResumoQuery.data, filteredDetailRows],
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

  const visibleMonths = filteredMonths.slice(0, visibleMonthsCount);

  const cycleLookup = React.useMemo(() => {
    return new Map<string, EnrichedCycleItem>(
      detailRows.map((row) => [onlyDigits(row.cpf_cnpj), row]),
    );
  }, [detailRows]);

  const monitoringCards = React.useMemo(() => {
    const total = filteredDetailRows.length;
    const firstStage = filteredDetailRows.filter((row) => row.parcelas_pagas <= 1).length;
    const secondStage = filteredDetailRows.filter((row) => row.parcelas_pagas === 2).length;
    const thirdStage = filteredDetailRows.filter((row) => row.parcelas_pagas >= 3).length;
    const pending = filteredDetailRows.filter(
      (row) =>
        row.status_visual === "inadimplente" ||
        row.status_visual === "em_aberto" ||
        row.resultado_importacao === "nao_descontado",
    ).length;

    if (monitoringMode === "semestral") {
      return [
        { title: "Meses 1-2 (Abertura)", value: Math.round(firstStage * 1.2) || firstStage },
        { title: "Meses 3-4 (Acompanhamento)", value: Math.round(secondStage * 1.1) || secondStage, tone: "neutral" as const },
        { title: "Meses 5-6 (Encerramento)", value: Math.max(thirdStage, Math.round(total * 0.35)), tone: "warning" as const },
        { title: "Pendências acumuladas", value: pending, tone: "danger" as const },
      ];
    }

    return [
      { title: "Mês 1/3 (Início)", value: firstStage },
      { title: "Mês 2/3 (Meio)", value: secondStage },
      { title: "Mês 3/3 (Encerramento)", value: thirdStage, tone: "warning" as const },
      { title: "Pendências acumuladas", value: pending, tone: "danger" as const },
    ];
  }, [filteredDetailRows, monitoringMode]);

  const activeAdvancedFiltersCount = countActiveFilters(selectedStatus, advancedFilters);
  const todayLabel = capitalize(
    format(new Date(), "EEE, dd 'de' MMM 'de' yyyy", { locale: ptBR }),
  );
  const selectedCompetenciaLabel = formatCompetenciaHeading(selectedCompetencia);

  const columns: DataTableColumn<EnrichedCycleItem>[] = [
    {
      id: "associado",
      header: "Associado",
      cell: (row) => (
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            <ChevronRightIcon className="size-4 shrink-0 text-muted-foreground" />
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
          <div className="flex flex-wrap gap-2 pl-7">
            <CopySnippet label="CPF" value={row.cpf_cnpj} mono />
            <CopySnippet label="Matrícula" value={row.matricula} mono />
          </div>
        </div>
      ),
      headerClassName: "w-[24%]",
    },
    {
      id: "agente",
      header: "Agente responsável",
      cell: (row) => row.agenteResponsavel,
      headerClassName: "w-[18%]",
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

  return (
    <div className="space-y-8 pb-10">
      <div className="space-y-5 rounded-[2rem] border border-border/60 bg-card/75 p-6 shadow-2xl shadow-black/20">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div className="space-y-2">
            <h1 className="text-4xl font-semibold tracking-tight text-foreground">
              Renovação de Ciclos
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

            <div className="flex items-center gap-2 rounded-2xl border border-border/60 bg-background/70 px-4 py-3 text-sm text-muted-foreground">
              <CalendarDaysIcon className="size-4" />
              {todayLabel}
            </div>
          </div>
        </div>

        <div className="grid gap-3 xl:grid-cols-[1.15fr_0.9fr_0.9fr_0.8fr]">
          <Select
            value={selectedCompetencia}
            onValueChange={(value) => {
              setSelectedCompetencia(value);
              if (!retornoCompetencia) {
                setRetornoCompetencia(value);
              }
            }}
          >
            <SelectTrigger className="rounded-2xl bg-background/60">
              <SelectValue placeholder="Competência base" />
            </SelectTrigger>
            <SelectContent>
              {monthsQuery.data?.map((month) => (
                <SelectItem key={month.id} value={month.id}>
                  {month.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <div className="flex gap-2">
            <SearchableSelect
              options={autocompleteOptions}
              value={selectedAutocomplete}
              onChange={setSelectedAutocomplete}
              placeholder="Buscar por CPF, matrícula ou nome"
              searchPlaceholder="Digite para localizar"
              className="rounded-2xl"
            />
            {selectedAutocomplete ? (
              <Button
                variant="outline"
                className="rounded-2xl"
                onClick={() => setSelectedAutocomplete("")}
              >
                Limpar
              </Button>
            ) : null}
          </div>

          <Select value={selectedStatus} onValueChange={setSelectedStatus}>
            <SelectTrigger className="rounded-2xl bg-background/60">
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

          <ExportButton
            onExport={(format) =>
              exportRows(
                format,
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
            <h2 className="text-2xl font-semibold text-foreground">Gestão detalhada por mês</h2>
            <p className="text-sm text-muted-foreground">
              Cards mensais com visão executiva, tabela dinâmica por associado e exportação em XLS/PDF.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
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
          {visibleMonths.map((month) => (
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
          <h2 className="text-2xl font-semibold text-foreground">Detalhamento mensal</h2>
          <p className="text-sm text-muted-foreground">
            Competência base {selectedCompetenciaLabel} com visão detalhada por associado e conciliação ETIPI.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-5">
          <MetricTile label="Total" value={detailMetrics.total} />
          <MetricTile label="Ciclo renovado" value={detailMetrics.cicloRenovado} />
          <MetricTile label="Apto a renovar" value={detailMetrics.aptoRenovar} accent="cyan" />
          <MetricTile label="Em aberto" value={detailMetrics.emAberto} tone="warning" />
          <MetricTile label="Inadimplentes" value={detailMetrics.inadimplente} tone="danger" />
        </div>

        <Card className="border-border/60 bg-card/80">
          <CardHeader className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div>
              <CardTitle>Detalhamento mensal já conciliado</CardTitle>
              <CardDescription>
                Copie nome, CPF e matrícula, confira o agente responsável e acompanhe as flags geradas pelo arquivo retorno.
              </CardDescription>
            </div>
            <ExportButton
              onExport={(format) =>
                exportRows(
                  format,
                  `Detalhamento mensal ${selectedCompetenciaLabel}`,
                  sanitizeFileName(`detalhamento-mensal-${selectedCompetencia || "atual"}`),
                  cycleExportColumns(selectedCompetenciaLabel),
                  filteredDetailRows,
                )
              }
            />
          </CardHeader>
          <CardContent>
            <DataTable
              columns={columns}
              data={filteredDetailRows}
              pageSize={8}
              emptyMessage="Nenhum ciclo encontrado para a competência selecionada."
              renderExpanded={(row) => (
                <div className="grid gap-4 md:grid-cols-[1.2fr_1fr_1fr_1.2fr]">
                  <div>
                    <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
                      Status ETIPI
                    </p>
                    <p className="mt-2 font-medium text-foreground">{row.status_codigo_etipi || "-"}</p>
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
                    </div>
                  </div>
                </div>
              )}
            />
          </CardContent>
        </Card>
      </section>

      <section className="space-y-5">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <h2 className="text-2xl font-semibold text-foreground">Arquivos retorno</h2>
            <p className="text-sm text-muted-foreground">
              Grid de três cards com progresso do processamento e detalhamento expansível por associado.
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
          </div>
        </div>

        <div className="grid gap-5 xl:grid-cols-3">
          {(importacaoQuery.data?.results ?? []).slice(0, 3).map((arquivo) => (
            <ReturnFileCard
              key={arquivo.id}
              arquivo={arquivo}
              cycleLookup={cycleLookup}
              searchValue={searchValue}
              advancedFilters={advancedFilters}
            />
          ))}
        </div>

        {!(importacaoQuery.data?.results ?? []).length ? (
          <Card className="border-border/60 bg-card/80">
            <CardContent className="py-10 text-center text-sm text-muted-foreground">
              Nenhum arquivo retorno encontrado para {formatCompetenciaHeading(retornoCompetencia)}.
            </CardContent>
          </Card>
        ) : null}
      </section>

      <section className="space-y-5">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <h2 className="text-2xl font-semibold text-foreground">
              Monitoramento de ciclos ({monitoringMode === "trimestral" ? "trimestral" : "semestral"})
            </h2>
            <p className="text-sm text-muted-foreground">
              KPIs derivados da competência filtrada para identificar abertura, andamento, encerramento e pendências acumuladas.
            </p>
          </div>

          <Tabs value={monitoringMode} onValueChange={(value) => setMonitoringMode(value as MonitoringMode)}>
            <TabsList variant="line">
              <TabsTrigger value="trimestral">Trimestral</TabsTrigger>
              <TabsTrigger value="semestral">Semestral</TabsTrigger>
            </TabsList>
          </Tabs>
        </div>

        <Tabs value={monitoringMode} onValueChange={(value) => setMonitoringMode(value as MonitoringMode)}>
          <TabsContent value={monitoringMode} className="space-y-4">
            <div className="grid gap-4 xl:grid-cols-4">
              {monitoringCards.map((card) => (
                <MonitoringCard
                  key={card.title}
                  title={card.title}
                  value={card.value}
                  tone={card.tone}
                />
              ))}
            </div>

            <div className="rounded-[1.35rem] border border-border/60 bg-card/80 px-5 py-4 text-sm text-muted-foreground">
              <div className="flex items-start gap-3">
                <CircleAlertIcon className="mt-0.5 size-4 text-cyan-300" />
                <p>
                  Regra de renovação automática: cada ciclo mantém três parcelas. No modo semestral, a leitura projeta dois ciclos consecutivos para antecipar acúmulo de pendências.
                </p>
              </div>
            </div>
          </TabsContent>
        </Tabs>
      </section>
    </div>
  );
}
