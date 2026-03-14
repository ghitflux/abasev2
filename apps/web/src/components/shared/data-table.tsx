"use client";

import * as React from "react";
import { ChevronDownIcon, ChevronUpIcon, ChevronsLeftIcon, ChevronsRightIcon } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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

type DataTablePageSizeOption =
  | number
  | {
      label: string;
      value: number;
    };

type DataTableProps<T extends { id: number | string }> = {
  columns: DataTableColumn<T>[];
  data: T[];
  renderExpanded?: (row: T) => React.ReactNode;
  pageSize?: number;
  pageSizeOptions?: DataTablePageSizeOption[];
  pageSizeLabel?: string;
  currentPage?: number;
  totalPages?: number;
  onPageChange?: (page: number) => void;
  emptyMessage?: string;
  className?: string;
  tableClassName?: string;
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

function normalizePageSizeOption(option: DataTablePageSizeOption) {
  if (typeof option === "number") {
    return { label: String(option), value: option };
  }

  return option;
}

export default function DataTable<T extends { id: number | string }>({
  columns,
  data,
  renderExpanded,
  pageSize = 5,
  pageSizeOptions,
  pageSizeLabel = "Por página",
  currentPage,
  totalPages,
  onPageChange,
  emptyMessage = "Nenhum registro encontrado.",
  className,
  tableClassName,
}: DataTableProps<T>) {
  const [internalPage, setInternalPage] = React.useState(1);
  const [internalPageSize, setInternalPageSize] = React.useState(pageSize);
  const [sortBy, setSortBy] = React.useState<string | null>(null);
  const [direction, setDirection] = React.useState<"asc" | "desc">("asc");
  const [expandedRow, setExpandedRow] = React.useState<number | string | null>(null);
  const isControlledPagination =
    currentPage !== undefined && totalPages !== undefined && !!onPageChange;
  const normalizedPageSizeOptions = React.useMemo(() => {
    const options = (pageSizeOptions ?? []).map(normalizePageSizeOption);

    if (!options.length) {
      return [];
    }

    if (!options.some((option) => option.value === pageSize)) {
      return [{ label: String(pageSize), value: pageSize }, ...options];
    }

    return options;
  }, [pageSize, pageSizeOptions]);
  const resolvedPageSize = isControlledPagination
    ? pageSize
    : normalizedPageSizeOptions.length
      ? internalPageSize
      : pageSize;

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
    : Math.max(1, Math.ceil(sortedData.length / resolvedPageSize));
  const currentRows = isControlledPagination
    ? sortedData
    : sortedData.slice((page - 1) * resolvedPageSize, page * resolvedPageSize);
  const changePage = (nextPage: number) => {
    if (isControlledPagination) {
      onPageChange?.(nextPage);
      return;
    }
    setInternalPage(nextPage);
  };
  const pageItems = React.useMemo(
    () => buildPageItems(page, resolvedTotalPages),
    [page, resolvedTotalPages],
  );

  React.useEffect(() => {
    if (!isControlledPagination) {
      setInternalPageSize(pageSize);
    }
  }, [isControlledPagination, pageSize]);

  React.useEffect(() => {
    if (
      !isControlledPagination &&
      normalizedPageSizeOptions.length > 0 &&
      !normalizedPageSizeOptions.some((option) => option.value === internalPageSize)
    ) {
      setInternalPageSize(normalizedPageSizeOptions[0].value);
    }
  }, [internalPageSize, isControlledPagination, normalizedPageSizeOptions]);

  React.useEffect(() => {
    if (isControlledPagination) {
      return;
    }

    setInternalPage((current) => Math.min(current, resolvedTotalPages));
  }, [isControlledPagination, resolvedTotalPages]);

  return (
    <div
      className={cn(
        "min-w-0 w-full overflow-hidden rounded-[1.75rem] border border-border/60 bg-card/70 shadow-xl shadow-black/20",
        className,
      )}
    >
      <Table className={cn("min-w-full", tableClassName)}>
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
                  className="group border-border/60 hover:bg-white/3"
                  data-expanded={expandedRow === row.id ? "true" : "false"}
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
        <div className="flex flex-wrap items-center gap-3">
          <p className="text-sm text-muted-foreground">
            Página {page} de {resolvedTotalPages}
          </p>
          {!isControlledPagination && normalizedPageSizeOptions.length > 0 ? (
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">{pageSizeLabel}</span>
              <Select
                value={String(resolvedPageSize)}
                onValueChange={(value) => {
                  setInternalPageSize(Number(value));
                  setInternalPage(1);
                }}
              >
                <SelectTrigger className="h-9 w-[7.5rem] rounded-xl bg-background/70">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {normalizedPageSizeOptions.map((option) => (
                    <SelectItem key={option.value} value={String(option.value)}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          <Button variant="outline" size="icon-sm" disabled={page === 1} onClick={() => changePage(1)}>
            <ChevronsLeftIcon className="size-4" />
          </Button>
          <Button variant="outline" size="icon-sm" disabled={page === 1} onClick={() => changePage(Math.max(1, page - 1))}>
            <ChevronUpIcon className="size-4 rotate-90" />
          </Button>
          {pageItems.map((item) =>
            typeof item === "number" ? (
              <Button
                key={item}
                variant={item === page ? "secondary" : "outline"}
                size="icon-sm"
                className="rounded-xl"
                onClick={() => changePage(item)}
              >
                {item}
              </Button>
            ) : (
              <span key={item} className="px-1 text-sm text-muted-foreground">
                ...
              </span>
            ),
          )}
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
