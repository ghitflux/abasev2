"use client";

import * as React from "react";

import type { DataTableColumn } from "@/components/shared/data-table";
import DataTable from "@/components/shared/data-table";
import ExportButton from "@/components/shared/export-button";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import type { TableExportColumn } from "@/lib/table-export";
import { exportRows } from "@/lib/table-export";

type DashboardDetailDialogProps<T extends { id: number | string }> = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  rows: T[];
  columns: DataTableColumn<T>[];
  exportColumns: TableExportColumn<T>[];
  exportTitle: string;
  exportFilename: string;
  emptyMessage: string;
  isLoading?: boolean;
  searchPlaceholder?: string;
  matchesSearch?: (row: T, search: string) => boolean;
  searchValue?: string;
  onSearchValueChange?: (value: string) => void;
  currentPage?: number;
  totalPages?: number;
  onPageChange?: (page: number) => void;
  pageSize?: number;
  onExport?: (format: "csv" | "pdf" | "excel") => void | Promise<void>;
};

export default function DashboardDetailDialog<T extends { id: number | string }>({
  open,
  onOpenChange,
  title,
  description,
  rows,
  columns,
  exportColumns,
  exportTitle,
  exportFilename,
  emptyMessage,
  isLoading = false,
  searchPlaceholder = "Buscar por nome, CPF, matricula ou contrato",
  matchesSearch,
  searchValue,
  onSearchValueChange,
  currentPage,
  totalPages,
  onPageChange,
  pageSize = 10,
  onExport,
}: DashboardDetailDialogProps<T>) {
  const [internalSearch, setInternalSearch] = React.useState("");
  const isControlledSearch =
    searchValue !== undefined && onSearchValueChange !== undefined;
  const search = isControlledSearch ? searchValue : internalSearch;
  const setSearch = isControlledSearch ? onSearchValueChange : setInternalSearch;

  React.useEffect(() => {
    if (!open) {
      setSearch("");
    }
  }, [open, setSearch]);

  const filteredRows = React.useMemo(() => {
    const normalized = search.trim().toLowerCase();
    if (!normalized) return rows;
    if (matchesSearch) {
      return rows.filter((row) => matchesSearch(row, normalized));
    }
    return rows;
  }, [matchesSearch, rows, search]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="grid max-h-[calc(100vh-2rem)] w-[96vw] max-w-[96vw] grid-rows-[auto_auto_minmax(0,1fr)] overflow-hidden border-border/60 bg-background/95 p-5 sm:p-6 lg:max-w-[88vw] 2xl:max-w-[96rem]">
        <DialogHeader className="shrink-0">
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>

        <div className="flex shrink-0 flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex min-w-0 flex-1 gap-3">
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={searchPlaceholder}
              className="rounded-2xl bg-card/60"
            />
            {search ? (
              <Button
                variant="outline"
                className="rounded-2xl"
                onClick={() => setSearch("")}
              >
                Limpar
              </Button>
            ) : null}
          </div>
          <ExportButton
            onExport={(format) =>
              onExport
                ? onExport(format)
                : exportRows(format, exportTitle, exportFilename, exportColumns, filteredRows)
            }
          />
        </div>

        <div className="min-h-0 overflow-y-auto pr-1">
          <DataTable
            columns={columns}
            data={filteredRows}
            emptyMessage={emptyMessage}
            pageSize={pageSize}
            pageSizeOptions={[10, 20, 50]}
            currentPage={currentPage}
            totalPages={totalPages}
            onPageChange={onPageChange}
            loading={isLoading}
            skeletonRows={8}
          />
        </div>
      </DialogContent>
    </Dialog>
  );
}
