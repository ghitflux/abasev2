"use client";

import * as React from "react";
import { format } from "date-fns";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BadgeCheckIcon,
  BriefcaseBusinessIcon,
  HandCoinsIcon,
  PaperclipIcon,
  SlidersHorizontalIcon,
  Trash2Icon,
} from "lucide-react";
import { toast } from "sonner";

import type {
  PagamentoAgenteItem,
  PagamentoAgenteResumo,
  PaginatedPagamentosAgenteResponse,
} from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import {
  describeReportScope,
  exportRouteReport,
  fetchAllPaginatedRows,
  filterRowsByReportScope,
} from "@/lib/reports";
import CalendarCompetencia from "@/components/custom/calendar-competencia";
import DatePicker from "@/components/custom/date-picker";
import {
  ASSOCIADO_STATUS_OPTIONS,
  buildPagamentoColumns,
  EMPTY_RESUMO,
  NUMERO_CICLOS_OPTIONS,
  PAGAMENTO_INICIAL_OPTIONS,
  PagamentoExpandido,
  PRESET_OPTIONS,
  resolveCount,
  STATUS_OPTIONS,
} from "@/components/pagamentos/pagamentos-shared";
import DataTable from "@/components/shared/data-table";
import ReportExportDialog, {
  type ReportExportFilters,
} from "@/components/shared/report-export-dialog";
import { MetricCardSkeleton } from "@/components/shared/page-skeletons";
import StatsCard from "@/components/shared/stats-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { usePermissions } from "@/hooks/use-permissions";

const PAGE_SIZE = 15;

type AdvancedFiltersState = {
  agente: string;
  status: string;
  associadoStatus: string;
  pagamentoInicialStatus: string;
  numeroCiclos: string;
  preset: string;
  competencia?: Date;
  dataInicio?: Date;
  dataFim?: Date;
};

const EMPTY_FILTERS: AdvancedFiltersState = {
  agente: "",
  status: "todos",
  associadoStatus: "todos",
  pagamentoInicialStatus: "todos",
  numeroCiclos: "todos",
  preset: "todos",
  competencia: undefined,
  dataInicio: undefined,
  dataFim: undefined,
};

function countActiveAdvancedFilters(filters: AdvancedFiltersState) {
  return [
    Boolean(filters.agente),
    filters.status !== "todos",
    filters.associadoStatus !== "todos",
    filters.pagamentoInicialStatus !== "todos",
    filters.numeroCiclos !== "todos",
    filters.preset !== "todos",
    Boolean(filters.competencia),
    Boolean(filters.dataInicio),
    Boolean(filters.dataFim),
  ].filter(Boolean).length;
}

export default function TesourariaPagamentosPage() {
  const { hasAnyRole } = usePermissions();
  const canRemoverFila = hasAnyRole(["ADMIN", "COORDENADOR"]);
  const queryClient = useQueryClient();
  const [search, setSearch] = React.useState("");
  const [page, setPage] = React.useState(1);
  const [isExporting, setIsExporting] = React.useState(false);
  const [excluirTarget, setExcluirTarget] = React.useState<PagamentoAgenteItem | null>(null);
  const [filtersOpen, setFiltersOpen] = React.useState(false);
  const [filters, setFilters] = React.useState<AdvancedFiltersState>(EMPTY_FILTERS);
  const [draftFilters, setDraftFilters] = React.useState<AdvancedFiltersState>(EMPTY_FILTERS);

  const query = useQuery({
    queryKey: [
      "tesouraria-pagamentos",
      page,
      search,
      filters.agente,
      filters.status,
      filters.associadoStatus,
      filters.pagamentoInicialStatus,
      filters.numeroCiclos,
      filters.preset,
      filters.competencia?.toISOString(),
      filters.dataInicio?.toISOString(),
      filters.dataFim?.toISOString(),
    ],
    queryFn: () =>
      apiFetch<PaginatedPagamentosAgenteResponse>("tesouraria/pagamentos", {
        query: {
          page,
          page_size: PAGE_SIZE,
          search: search || undefined,
          status: filters.status === "todos" ? undefined : filters.status,
          agente: filters.agente || undefined,
          associado_status:
            filters.associadoStatus === "todos" ? undefined : filters.associadoStatus,
          pagamento_inicial_status:
            filters.pagamentoInicialStatus === "todos"
              ? undefined
              : filters.pagamentoInicialStatus,
          numero_ciclos:
            filters.numeroCiclos === "todos" ? undefined : filters.numeroCiclos,
          preset: filters.preset === "todos" ? undefined : filters.preset,
          mes: filters.competencia ? format(filters.competencia, "yyyy-MM") : undefined,
          data_inicio: filters.dataInicio ? format(filters.dataInicio, "yyyy-MM-dd") : undefined,
          data_fim: filters.dataFim ? format(filters.dataFim, "yyyy-MM-dd") : undefined,
        },
      }),
  });

  const excluirMutation = useMutation({
    mutationFn: async (contratoId: number) =>
      apiFetch(`tesouraria/pagamentos/${contratoId}/excluir`, {
        method: "POST",
        body: {},
      }),
    onSuccess: () => {
      toast.success("Contrato removido da fila.");
      setExcluirTarget(null);
      void queryClient.invalidateQueries({ queryKey: ["tesouraria-pagamentos"] });
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Falha ao remover da fila.");
    },
  });

  const rows = query.data?.results ?? [];
  const resumo: PagamentoAgenteResumo = {
    total: resolveCount(query.data?.resumo?.total ?? EMPTY_RESUMO.total),
    efetivados: resolveCount(query.data?.resumo?.efetivados ?? EMPTY_RESUMO.efetivados),
    com_anexos: resolveCount(query.data?.resumo?.com_anexos ?? EMPTY_RESUMO.com_anexos),
    parcelas_pagas: resolveCount(query.data?.resumo?.parcelas_pagas ?? EMPTY_RESUMO.parcelas_pagas),
    parcelas_total: resolveCount(query.data?.resumo?.parcelas_total ?? EMPTY_RESUMO.parcelas_total),
  };
  const totalPages = Math.max(1, Math.ceil((query.data?.count ?? 0) / PAGE_SIZE));
  const columns = React.useMemo(
    () => buildPagamentoColumns({ onExcluir: setExcluirTarget, canRemoverFila }),
    [canRemoverFila],
  );
  const activeAdvancedFilters = countActiveAdvancedFilters(filters);

  const handleExport = React.useCallback(
    async (exportFilters: ReportExportFilters, exportFormat: "pdf" | "xlsx") => {
      const { scope, referenceDate } = exportFilters;
      setIsExporting(true);
      try {
        const sourceQuery = {
          search: search || undefined,
          status: filters.status === "todos" ? undefined : filters.status,
          agente: filters.agente || undefined,
          associado_status:
            filters.associadoStatus === "todos" ? undefined : filters.associadoStatus,
          pagamento_inicial_status:
            filters.pagamentoInicialStatus === "todos"
              ? undefined
              : filters.pagamentoInicialStatus,
          numero_ciclos:
            filters.numeroCiclos === "todos" ? undefined : filters.numeroCiclos,
          preset: filters.preset === "todos" ? undefined : filters.preset,
          mes: filters.competencia ? format(filters.competencia, "yyyy-MM") : undefined,
          data_inicio: filters.dataInicio ? format(filters.dataInicio, "yyyy-MM-dd") : undefined,
          data_fim: filters.dataFim ? format(filters.dataFim, "yyyy-MM-dd") : undefined,
        };
        const fetchedRows = await fetchAllPaginatedRows<PagamentoAgenteItem>({
          sourcePath: "tesouraria/pagamentos",
          sourceQuery,
        });
        const rows = filterRowsByReportScope({
          rows: fetchedRows,
          scope,
          referenceDate,
          getCandidates: (row) => [
            row.pagamento_inicial_paid_at,
            row.data_solicitacao,
            row.auxilio_liberado_em,
            row.data_contrato,
          ],
        }).map((row) => ({
            contrato_codigo: row.contrato_codigo,
            nome: row.nome,
            agente_nome: row.agente_nome,
            data_solicitacao: row.data_solicitacao,
            status_visual_label: row.status_visual_label,
            pagamento_inicial_status_label: row.pagamento_inicial_status_label,
            pagamento_inicial_valor: row.pagamento_inicial_valor,
            cancelamento_tipo: row.cancelamento_tipo ?? "",
            cancelamento_motivo: row.cancelamento_motivo ?? "",
          }));

        await exportRouteReport({
          route: "/tesouraria/pagamentos",
          format: exportFormat,
          rows,
          filters: {
            ...sourceQuery,
            ...describeReportScope(scope, referenceDate),
          },
        });
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "Falha ao exportar pagamentos.");
      } finally {
        setIsExporting(false);
      }
    },
    [filters, search],
  );

  return (
    <div className="space-y-6">
      <section className="rounded-[1.75rem] border border-border/60 bg-card/70 p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-1">
            <p className="text-sm uppercase tracking-[0.28em] text-muted-foreground">
              Tesouraria
            </p>
            <h1 className="text-3xl font-semibold">Pagamentos</h1>
            <p className="text-sm text-muted-foreground">
              Painel operacional de contratos já pagos, efetivados e em acompanhamento
              financeiro.
            </p>
          </div>
          <ReportExportDialog
            disabled={isExporting}
            label={isExporting ? "Exportando..." : "Exportar"}
            onExport={handleExport}
          />
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {query.isLoading && !query.data ? (
          Array.from({ length: 4 }).map((_, index) => <MetricCardSkeleton key={index} />)
        ) : (
          <>
            <StatsCard
              title="Contratos com repasse"
              value={resolveCount(resumo.total).toLocaleString("pt-BR")}
              delta={`${resolveCount(resumo.efetivados).toLocaleString("pt-BR")} efetivados no recorte`}
              icon={BriefcaseBusinessIcon}
              tone="neutral"
            />
            <StatsCard
              title="Efetivados"
              value={resolveCount(resumo.efetivados).toLocaleString("pt-BR")}
              delta="Pagamentos iniciais já confirmados"
              icon={BadgeCheckIcon}
              tone="positive"
            />
            <StatsCard
              title="Com anexos"
              value={resolveCount(resumo.com_anexos).toLocaleString("pt-BR")}
              delta="Contratos com evidência disponível"
              icon={PaperclipIcon}
              tone="neutral"
            />
            <StatsCard
              title="Parcelas pagas"
              value={`${resolveCount(resumo.parcelas_pagas).toLocaleString("pt-BR")}/${resolveCount(resumo.parcelas_total).toLocaleString("pt-BR")}`}
              delta={`${Math.max(resolveCount(resumo.parcelas_total) - resolveCount(resumo.parcelas_pagas), 0).toLocaleString("pt-BR")} ainda pendentes`}
              icon={HandCoinsIcon}
              tone="positive"
            />
          </>
        )}
      </section>

      <section className="grid gap-3 rounded-[1.75rem] border border-border/60 bg-card/50 p-4 lg:grid-cols-[minmax(0,1fr)_auto_auto]">
        <Input
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
            setPage(1);
          }}
          placeholder="Buscar por nome, CPF, matrícula ou código do contrato..."
          className="rounded-2xl border-border/60 bg-card/60"
        />
        <Sheet
          open={filtersOpen}
          onOpenChange={(open) => {
            if (open) {
              setDraftFilters(filters);
            }
            setFiltersOpen(open);
          }}
        >
          <SheetTrigger asChild>
            <Button variant="outline" className="rounded-2xl">
              <SlidersHorizontalIcon className="size-4" />
              Filtros avançados
              {activeAdvancedFilters ? (
                <Badge className="ml-1 rounded-full bg-primary/15 px-2 py-0 text-primary">
                  {activeAdvancedFilters}
                </Badge>
              ) : null}
            </Button>
          </SheetTrigger>
          <SheetContent className="w-full border-l border-border/60 sm:max-w-xl">
            <SheetHeader>
              <SheetTitle>Filtros avançados</SheetTitle>
              <SheetDescription>
                Refine por agente, fila, status operacionais, competência e período.
              </SheetDescription>
            </SheetHeader>

            <div className="space-y-5 overflow-y-auto px-4 pb-4">
              <FilterField label="Agente">
                <Input
                  value={draftFilters.agente}
                  onChange={(event) =>
                    setDraftFilters((current) => ({
                      ...current,
                      agente: event.target.value,
                    }))
                  }
                  placeholder="Nome ou e-mail do agente"
                  className="rounded-2xl border-border/60 bg-card/60"
                />
              </FilterField>

              <div className="grid gap-4 md:grid-cols-2">
                <FilterField label="Status do contrato">
                  <Select
                    value={draftFilters.status}
                    onValueChange={(value) =>
                      setDraftFilters((current) => ({
                        ...current,
                        status: value,
                      }))
                    }
                  >
                    <SelectTrigger className="rounded-2xl bg-card/60">
                      <SelectValue placeholder="Todos status" />
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

                <FilterField label="Status do associado">
                  <Select
                    value={draftFilters.associadoStatus}
                    onValueChange={(value) =>
                      setDraftFilters((current) => ({
                        ...current,
                        associadoStatus: value,
                      }))
                    }
                  >
                    <SelectTrigger className="rounded-2xl bg-card/60">
                      <SelectValue placeholder="Todos associados" />
                    </SelectTrigger>
                    <SelectContent>
                      {ASSOCIADO_STATUS_OPTIONS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </FilterField>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <FilterField label="Pagamento inicial">
                  <Select
                    value={draftFilters.pagamentoInicialStatus}
                    onValueChange={(value) =>
                      setDraftFilters((current) => ({
                        ...current,
                        pagamentoInicialStatus: value,
                      }))
                    }
                  >
                    <SelectTrigger className="rounded-2xl bg-card/60">
                      <SelectValue placeholder="Todos pagamentos iniciais" />
                    </SelectTrigger>
                    <SelectContent>
                      {PAGAMENTO_INICIAL_OPTIONS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </FilterField>

                <FilterField label="Fila operacional">
                  <Select
                    value={draftFilters.preset}
                    onValueChange={(value) =>
                      setDraftFilters((current) => ({
                        ...current,
                        preset: value,
                      }))
                    }
                  >
                    <SelectTrigger className="rounded-2xl bg-card/60">
                      <SelectValue placeholder="Todas as filas" />
                    </SelectTrigger>
                    <SelectContent>
                      {PRESET_OPTIONS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </FilterField>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <FilterField label="Número de ciclos">
                  <Select
                    value={draftFilters.numeroCiclos}
                    onValueChange={(value) =>
                      setDraftFilters((current) => ({
                        ...current,
                        numeroCiclos: value,
                      }))
                    }
                  >
                    <SelectTrigger className="rounded-2xl bg-card/60">
                      <SelectValue placeholder="Todos ciclos" />
                    </SelectTrigger>
                    <SelectContent>
                      {NUMERO_CICLOS_OPTIONS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </FilterField>

                <FilterField label="Competência">
                  <CalendarCompetencia
                    value={draftFilters.competencia}
                    onChange={(value) =>
                      setDraftFilters((current) => ({
                        ...current,
                        competencia: value,
                      }))
                    }
                    className="w-full"
                  />
                </FilterField>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <FilterField label="Data inicial">
                  <DatePicker
                    value={draftFilters.dataInicio}
                    onChange={(value) =>
                      setDraftFilters((current) => ({
                        ...current,
                        dataInicio: value,
                      }))
                    }
                  />
                </FilterField>

                <FilterField label="Data final">
                  <DatePicker
                    value={draftFilters.dataFim}
                    onChange={(value) =>
                      setDraftFilters((current) => ({
                        ...current,
                        dataFim: value,
                      }))
                    }
                  />
                </FilterField>
              </div>
            </div>

            <SheetFooter className="border-t border-border/60">
              <Button
                variant="outline"
                onClick={() => {
                  setDraftFilters(EMPTY_FILTERS);
                  setFilters(EMPTY_FILTERS);
                  setPage(1);
                  setFiltersOpen(false);
                }}
              >
                Limpar avançados
              </Button>
              <Button
                onClick={() => {
                  setFilters(draftFilters);
                  setPage(1);
                  setFiltersOpen(false);
                }}
              >
                Aplicar
              </Button>
            </SheetFooter>
          </SheetContent>
        </Sheet>

        <Button
          variant="outline"
          onClick={() => {
            setSearch("");
            setFilters(EMPTY_FILTERS);
            setDraftFilters(EMPTY_FILTERS);
            setPage(1);
          }}
        >
          Limpar
        </Button>
      </section>

      {query.isError ? (
        <div className="rounded-[1.75rem] border border-destructive/40 bg-destructive/10 px-6 py-5 text-sm text-destructive">
          {query.error instanceof Error
            ? query.error.message
            : "Falha ao carregar pagamentos da tesouraria."}
        </div>
      ) : (
        <DataTable
          data={rows}
          columns={columns}
          renderExpanded={(row) => <PagamentoExpandido row={row} />}
          currentPage={page}
          totalPages={totalPages}
          onPageChange={setPage}
          emptyMessage="Nenhum contrato encontrado para os filtros informados."
          loading={query.isLoading}
          skeletonRows={6}
        />
      )}

      <Dialog open={excluirTarget != null} onOpenChange={(open) => { if (!open) setExcluirTarget(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Remover contrato da fila</DialogTitle>
            <DialogDescription>
              O contrato de <strong>{excluirTarget?.nome}</strong> será removido da fila
              operacional. O histórico será preservado.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setExcluirTarget(null)}>
              Cancelar
            </Button>
            <Button
              variant="destructive"
              disabled={excluirMutation.isPending}
              onClick={() => excluirTarget && excluirMutation.mutate(excluirTarget.id)}
            >
              <Trash2Icon className="size-4" />
              Remover da fila
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function FilterField({
  label,
  children,
}: React.PropsWithChildren<{ label: string }>) {
  return (
    <div className="space-y-2">
      <Label className="text-[11px] uppercase tracking-[0.22em] text-muted-foreground">
        {label}
      </Label>
      {children}
    </div>
  );
}
