"use client";

import { DownloadIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { ReportScope } from "@/lib/reports";

type ExportButtonProps = {
  onExport?: (format: "csv" | "pdf" | "excel" | "xlsx") => void;
  onExportScoped?: (scope: ReportScope, format: "pdf" | "xlsx") => void;
  disabled?: boolean;
  label?: string;
  enableScopeSelection?: boolean;
};

export default function ExportButton({
  onExport,
  onExportScoped,
  disabled = false,
  label = "Exportar",
  enableScopeSelection = false,
}: ExportButtonProps) {
  const useScopeSelection = enableScopeSelection && Boolean(onExportScoped);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" className="rounded-2xl" disabled={disabled}>
          <DownloadIcon className="size-4" />
          {label}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="rounded-xl">
        {useScopeSelection ? (
          <>
            <DropdownMenuItem onClick={() => onExportScoped?.("day", "pdf")}>
              Relatório do dia · PDF
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => onExportScoped?.("day", "xlsx")}>
              Relatório do dia · XLS
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => onExportScoped?.("month", "pdf")}>
              Relatório do mês · PDF
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => onExportScoped?.("month", "xlsx")}>
              Relatório do mês · XLS
            </DropdownMenuItem>
          </>
        ) : (
          <>
            <DropdownMenuItem onClick={() => onExport?.("pdf")}>PDF</DropdownMenuItem>
            <DropdownMenuItem onClick={() => onExport?.("xlsx")}>XLS</DropdownMenuItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
