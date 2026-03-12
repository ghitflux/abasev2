"use client";

import * as React from "react";
import { ChevronDownIcon, ChevronUpIcon, ChevronsLeftIcon, ChevronsRightIcon } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export type DataTableColumn<T> = {
  id: string;
  header: string;
  accessor?: keyof T;
  sortable?: boolean;
  cell?: (row: T) => React.ReactNode;
  headerClassName?: string;
  cellClassName?: string;
};

type DataTableProps<T extends { id: number | string }> = {
  columns: DataTableColumn<T>[];
  data: T[];
  renderExpanded?: (row: T) => React.ReactNode;
  pageSize?: number;
  currentPage?: number;
  totalPages?: number;
  onPageChange?: (page: number) => void;
  emptyMessage?: string;
  className?: string;
  tableClassName?: string;
};

export default function DataTable<T extends { id: number | string }>({
  columns,
  data,
  renderExpanded,
  pageSize = 5,
  currentPage,
  totalPages,
  onPageChange,
  emptyMessage = "Nenhum registro encontrado.",
  className,
  tableClassName,
}: DataTableProps<T>) {
  const [internalPage, setInternalPage] = React.useState(1);
  const [sortBy, setSortBy] = React.useState<string | null>(null);
  const [direction, setDirection] = React.useState<"asc" | "desc">("asc");
  const [expandedRow, setExpandedRow] = React.useState<number | string | null>(null);
  const isControlledPagination =
    currentPage !== undefined && totalPages !== undefined && !!onPageChange;

  const page = isControlledPagination ? currentPage : internalPage;

  const sortedData = React.useMemo(() => {
    if (!sortBy) return data;

    const column = columns.find((item) => item.id === sortBy);
    if (!column?.accessor) return data;
    const accessor = column.accessor;

    return [...data].sort((left, right) => {
      const leftValue = String(left[accessor] ?? "");
      const rightValue = String(right[accessor] ?? "");
      const comparison = leftValue.localeCompare(rightValue, "pt-BR", { numeric: true });
      return direction === "asc" ? comparison : -comparison;
    });
  }, [columns, data, direction, sortBy]);

  const resolvedTotalPages = isControlledPagination
    ? Math.max(1, totalPages ?? 1)
    : Math.max(1, Math.ceil(sortedData.length / pageSize));
  const currentRows = isControlledPagination
    ? sortedData
    : sortedData.slice((page - 1) * pageSize, page * pageSize);
  const changePage = (nextPage: number) => {
    if (isControlledPagination) {
      onPageChange?.(nextPage);
      return;
    }
    setInternalPage(nextPage);
  };

  return (
    <div
      className={cn(
        "min-w-0 w-full overflow-hidden rounded-[1.75rem] border border-border/60 bg-card/70 shadow-xl shadow-black/20",
        className,
      )}
    >
      <Table className={tableClassName}>
        <TableHeader>
          <TableRow className="border-border/60 hover:bg-transparent">
            {columns.map((column) => (
              <TableHead
                key={column.id}
                className={cn(
                  "h-12 px-5 text-xs uppercase tracking-[0.24em] text-muted-foreground",
                  column.headerClassName,
                )}
              >
                {column.sortable ? (
                  <button
                    className="inline-flex items-center gap-1"
                    onClick={() => {
                      if (sortBy === column.id) {
                        setDirection((current) => (current === "asc" ? "desc" : "asc"));
                      } else {
                        setSortBy(column.id);
                        setDirection("asc");
                      }
                    }}
                    type="button"
                  >
                    {column.header}
                    {sortBy === column.id ? (
                      direction === "asc" ? <ChevronUpIcon className="size-4" /> : <ChevronDownIcon className="size-4" />
                    ) : null}
                  </button>
                ) : (
                  column.header
                )}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {currentRows.length ? (
            currentRows.map((row) => (
              <React.Fragment key={row.id}>
                <TableRow
                  className="border-border/60 hover:bg-white/3"
                  onClick={() => {
                    if (!renderExpanded) return;
                    setExpandedRow((current) => (current === row.id ? null : row.id));
                  }}
                >
                  {columns.map((column) => (
                    <TableCell
                      key={column.id}
                      className={cn("px-5 py-4 align-top", column.cellClassName)}
                    >
                      {column.cell
                        ? column.cell(row)
                        : column.accessor
                          ? String(row[column.accessor] ?? "")
                          : null}
                    </TableCell>
                  ))}
                </TableRow>
                {renderExpanded && expandedRow === row.id ? (
                  <TableRow className="border-border/60 bg-white/3">
                    <TableCell colSpan={columns.length} className="px-5 py-4">
                      {renderExpanded(row)}
                    </TableCell>
                  </TableRow>
                ) : null}
              </React.Fragment>
            ))
          ) : (
            <TableRow className="border-border/60">
              <TableCell colSpan={columns.length} className="px-5 py-12 text-center text-sm text-muted-foreground">
                {emptyMessage}
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border/60 px-5 py-4">
        <p className="text-sm text-muted-foreground">
          Página {page} de {resolvedTotalPages}
        </p>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon-sm" disabled={page === 1} onClick={() => changePage(1)}>
            <ChevronsLeftIcon className="size-4" />
          </Button>
          <Button variant="outline" size="icon-sm" disabled={page === 1} onClick={() => changePage(Math.max(1, page - 1))}>
            <ChevronUpIcon className="size-4 rotate-90" />
          </Button>
          <Button variant="outline" size="icon-sm" disabled={page === resolvedTotalPages} onClick={() => changePage(Math.min(resolvedTotalPages, page + 1))}>
            <ChevronDownIcon className="size-4 -rotate-90" />
          </Button>
          <Button variant="outline" size="icon-sm" disabled={page === resolvedTotalPages} onClick={() => changePage(resolvedTotalPages)}>
            <ChevronsRightIcon className="size-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
