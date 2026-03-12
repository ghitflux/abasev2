"use client";

import { DownloadIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

type ExportButtonProps = {
  onExport: (format: "csv" | "pdf" | "excel") => void;
};

export default function ExportButton({ onExport }: ExportButtonProps) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" className="rounded-2xl">
          <DownloadIcon className="size-4" />
          Exportar
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="rounded-xl">
        <DropdownMenuItem onClick={() => onExport("csv")}>CSV</DropdownMenuItem>
        <DropdownMenuItem onClick={() => onExport("pdf")}>PDF</DropdownMenuItem>
        <DropdownMenuItem onClick={() => onExport("excel")}>Excel</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
