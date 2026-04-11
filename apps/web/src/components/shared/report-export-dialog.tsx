"use client";

import * as React from "react";
import { format, isValid } from "date-fns";
import { ptBR } from "date-fns/locale";
import { CalendarIcon, DownloadIcon } from "lucide-react";

import type { ReportScope } from "@/lib/reports";
import CalendarCompetencia from "@/components/custom/calendar-competencia";
import DatePicker from "@/components/custom/date-picker";
import SearchableSelect, {
  type SelectOption,
} from "@/components/custom/searchable-select";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export type ReportExportFilters = {
  scope: ReportScope;
  referenceDate: Date;
  agente?: string;
  status?: string;
  esteira?: string;
};

type ReportExportDialogProps = {
  disabled?: boolean;
  label?: string;
  agentOptions?: SelectOption[];
  statusOptions?: Array<{ value: string; label: string }>;
  esteiraOptions?: Array<{ value: string; label: string }>;
  showFilters?: boolean;
  /** Oculta o seletor de período/data — use quando os dados já estão filtrados externamente */
  hideScope?: boolean;
  onExport: (
    filters: ReportExportFilters,
    format: "pdf" | "xlsx",
  ) => void | Promise<void>;
};

export default function ReportExportDialog({
  disabled = false,
  label = "Exportar",
  agentOptions = [],
  statusOptions = [],
  esteiraOptions = [],
  showFilters = false,
  hideScope = false,
  onExport,
}: ReportExportDialogProps) {
  const [open, setOpen] = React.useState(false);
  const [scope, setScope] = React.useState<ReportScope>("month");
  const [dayRef, setDayRef] = React.useState<Date>(new Date());
  const [monthRef, setMonthRef] = React.useState<Date>(
    new Date(new Date().getFullYear(), new Date().getMonth(), 1),
  );
  const [agente, setAgente] = React.useState("");
  const [status, setStatus] = React.useState("todos");
  const [esteira, setEsteira] = React.useState("todos");
  const [isExporting, setIsExporting] = React.useState(false);

  const referenceDate = scope === "day" ? dayRef : monthRef;
  const referenceDateValid = hideScope || isValid(referenceDate);

  const handleExport = async (fmt: "pdf" | "xlsx") => {
    if (!referenceDateValid) return;
    setIsExporting(true);
    try {
      await onExport(
        {
          scope,
          referenceDate: hideScope ? new Date() : referenceDate,
          agente: agente || undefined,
          status: status === "todos" ? undefined : status,
          esteira: esteira === "todos" ? undefined : esteira,
        },
        fmt,
      );
      setOpen(false);
    } finally {
      setIsExporting(false);
    }
  };

  const scopeLabel = referenceDateValid
    ? scope === "day"
      ? format(referenceDate, "dd/MM/yyyy")
      : format(referenceDate, "MMMM/yyyy", { locale: ptBR })
    : "—";

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" className="rounded-2xl" disabled={disabled}>
          <DownloadIcon className="size-4" />
          {label}
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Exportar relatório</DialogTitle>
          <DialogDescription>
            {hideScope
              ? `Escolha o formato de exportação${showFilters ? " e os filtros" : ""}.`
              : `Escolha o período de referência${showFilters ? ", filtros" : ""} e o formato de exportação.`}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-5 py-2">
          {!hideScope && (
            <>
              {/* Scope selector */}
              <div className="space-y-2">
                <Label>Período</Label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setScope("day")}
                    className={[
                      "flex items-center gap-2 rounded-xl border px-4 py-2.5 text-sm font-medium transition-colors",
                      scope === "day"
                        ? "border-primary/60 bg-primary/10 text-primary"
                        : "border-border/60 bg-card/60 text-muted-foreground hover:border-primary/30",
                    ].join(" ")}
                  >
                    <CalendarIcon className="size-4" />
                    Do dia
                  </button>
                  <button
                    type="button"
                    onClick={() => setScope("month")}
                    className={[
                      "flex items-center gap-2 rounded-xl border px-4 py-2.5 text-sm font-medium transition-colors",
                      scope === "month"
                        ? "border-primary/60 bg-primary/10 text-primary"
                        : "border-border/60 bg-card/60 text-muted-foreground hover:border-primary/30",
                    ].join(" ")}
                  >
                    <CalendarIcon className="size-4" />
                    Do mês
                  </button>
                </div>
              </div>

              {/* Reference date */}
              <div className="space-y-2">
                <Label>
                  {scope === "day" ? "Data de referência" : "Mês de referência"}
                </Label>
                {scope === "day" ? (
                  <DatePicker value={dayRef} onChange={setDayRef} />
                ) : (
                  <CalendarCompetencia
                    value={monthRef}
                    onChange={setMonthRef}
                    placeholder="Selecionar mês"
                  />
                )}
                <p className="text-xs text-muted-foreground">
                  Referência selecionada:{" "}
                  <span className="font-medium text-foreground">{scopeLabel}</span>
                </p>
              </div>
            </>
          )}

          {/* Optional filters */}
          {showFilters && (
            <>
              {agentOptions.length > 0 && (
                <div className="space-y-2">
                  <Label>Agente</Label>
                  <SearchableSelect
                    options={agentOptions}
                    value={agente}
                    onChange={setAgente}
                    placeholder="Todos os agentes"
                    searchPlaceholder="Buscar agente"
                    clearLabel="Limpar agente"
                  />
                </div>
              )}

              {statusOptions.length > 0 && (
                <div className="space-y-2">
                  <Label>Status do contrato</Label>
                  <Select value={status} onValueChange={setStatus}>
                    <SelectTrigger className="rounded-xl border-border/60 bg-card/60">
                      <SelectValue placeholder="Todos" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="todos">Todos</SelectItem>
                      {statusOptions.map((opt) => (
                        <SelectItem key={opt.value} value={opt.value}>
                          {opt.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}

              {esteiraOptions.length > 0 && (
                <div className="space-y-2">
                  <Label>Situação na esteira</Label>
                  <Select value={esteira} onValueChange={setEsteira}>
                    <SelectTrigger className="rounded-xl border-border/60 bg-card/60">
                      <SelectValue placeholder="Todas" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="todos">Todas</SelectItem>
                      {esteiraOptions.map((opt) => (
                        <SelectItem key={opt.value} value={opt.value}>
                          {opt.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )}
            </>
          )}
        </div>

        <DialogFooter className="flex flex-col-reverse gap-2 pt-2 sm:flex-row sm:justify-end">
          <Button
            variant="ghost"
            onClick={() => setOpen(false)}
            disabled={isExporting}
            className="rounded-xl"
          >
            Cancelar
          </Button>
          <Button
            variant="outline"
            onClick={() => void handleExport("xlsx")}
            disabled={isExporting || !referenceDateValid}
            className="rounded-xl"
          >
            <DownloadIcon className="size-4" />
            {isExporting ? "Exportando…" : "Exportar XLS"}
          </Button>
          <Button
            onClick={() => void handleExport("pdf")}
            disabled={isExporting || !referenceDateValid}
            className="rounded-xl bg-primary text-primary-foreground hover:bg-primary/90"
          >
            <DownloadIcon className="size-4" />
            {isExporting ? "Exportando…" : "Exportar PDF"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
