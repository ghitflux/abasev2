"use client";

import { format } from "date-fns";

import type { PaginatedResponse, RelatorioGeradoItem } from "@/lib/api/types";

import { apiFetch } from "@/lib/api/client";

type ReportRow = Record<string, unknown>;
type ReportQueryValue =
  | string
  | number
  | boolean
  | null
  | undefined
  | Array<string | number | boolean>;
type ReportQuery = Record<string, ReportQueryValue>;
export type ReportScope = "day" | "month";

export async function exportRouteReport({
  route,
  format,
  rows,
  filters,
}: {
  route: string;
  format: "pdf" | "xlsx";
  rows: ReportRow[];
  filters?: Record<string, unknown>;
}) {
  const relatorio = await apiFetch<RelatorioGeradoItem>("relatorios/exportar", {
    method: "POST",
    body: {
      rota: route,
      formato: format,
      filtros: {
        ...(filters ?? {}),
        rows,
      },
    },
  });

  window.open(`/api/backend/relatorios/${relatorio.id}/download`, "_blank", "noopener,noreferrer");
}

export async function fetchAllPaginatedRows<T>({
  sourcePath,
  sourceQuery,
  pageSize = 200,
}: {
  sourcePath: string;
  sourceQuery?: ReportQuery;
  pageSize?: number;
}) {
  const firstPage = await apiFetch<PaginatedResponse<T>>(sourcePath, {
    query: {
      ...(sourceQuery ?? {}),
      page: 1,
      page_size: pageSize,
    },
  });

  const resolvedPageSize = Math.max(firstPage.results.length || 0, 1);
  const totalPages = Math.max(1, Math.ceil(firstPage.count / resolvedPageSize));
  if (totalPages === 1) {
    return firstPage.results;
  }

  const remainingPages = await Promise.all(
    Array.from({ length: totalPages - 1 }, (_, index) =>
      apiFetch<PaginatedResponse<T>>(sourcePath, {
        query: {
          ...(sourceQuery ?? {}),
          page: index + 2,
          page_size: pageSize,
        },
      }),
    ),
  );

  return [firstPage, ...remainingPages].flatMap((page) => page.results);
}

export async function exportPaginatedRouteReport<T>({
  route,
  format,
  sourcePath,
  sourceQuery,
  mapRow,
  filters,
  pageSize,
}: {
  route: string;
  format: "pdf" | "xlsx";
  sourcePath: string;
  sourceQuery?: ReportQuery;
  mapRow: (row: T) => ReportRow;
  filters?: Record<string, unknown>;
  pageSize?: number;
}) {
  const rows = await fetchAllPaginatedRows<T>({
    sourcePath,
    sourceQuery,
    pageSize,
  });

  await exportRouteReport({
    route,
    format,
    rows: rows.map((row) => mapRow(row)),
    filters: filters ?? sourceQuery,
  });
}

export function resolveReportReferenceDate({
  scope,
  dayReference,
  monthReference,
  fallback = new Date(),
}: {
  scope: ReportScope;
  dayReference?: Date;
  monthReference?: Date;
  fallback?: Date;
}) {
  return scope === "day"
    ? dayReference ?? monthReference ?? fallback
    : monthReference ?? dayReference ?? fallback;
}

export function describeReportScope(scope: ReportScope, referenceDate: Date) {
  return {
    escopo_relatorio: scope === "day" ? "dia" : "mes",
    referencia_relatorio: format(referenceDate, scope === "day" ? "dd/MM/yyyy" : "MM/yyyy"),
  };
}

function normalizeDateCandidate(value: unknown) {
  if (value == null) {
    return "";
  }

  const stringValue = String(value).trim();
  if (!stringValue) {
    return "";
  }

  if (/^\d{4}-\d{2}$/.test(stringValue)) {
    return stringValue;
  }

  if (/^\d{4}-\d{2}-\d{2}$/.test(stringValue)) {
    return stringValue.slice(0, 10);
  }

  if (/^\d{4}-\d{2}-\d{2}[T\s]/.test(stringValue)) {
    const parsedDateTime = new Date(stringValue);
    if (!Number.isNaN(parsedDateTime.getTime())) {
      return format(parsedDateTime, "yyyy-MM-dd");
    }
    return stringValue.slice(0, 10);
  }

  const parsed = new Date(stringValue);
  if (Number.isNaN(parsed.getTime())) {
    return stringValue;
  }

  return format(parsed, "yyyy-MM-dd");
}

export function filterRowsByReportScope<T>({
  rows,
  scope,
  referenceDate,
  getCandidates,
}: {
  rows: T[];
  scope: ReportScope;
  referenceDate: Date;
  getCandidates: (row: T) => Array<unknown>;
}) {
  const scopeKey = format(referenceDate, scope === "day" ? "yyyy-MM-dd" : "yyyy-MM");

  return rows.filter((row) => {
    const candidates = getCandidates(row)
      .map((candidate) => normalizeDateCandidate(candidate))
      .filter(Boolean);

    if (!candidates.length) {
      return true;
    }

    return candidates.some((candidate) => candidate.startsWith(scopeKey));
  });
}
