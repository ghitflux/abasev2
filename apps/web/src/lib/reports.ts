"use client";

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

  const totalPages = Math.max(1, Math.ceil(firstPage.count / pageSize));
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
