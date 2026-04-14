"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BadgeCheckIcon,
  EyeIcon,
  ForwardIcon,
  PlayIcon,
  ShieldCheckIcon,
  SlidersHorizontalIcon,
} from "lucide-react";
import { toast } from "sonner";

import type {
  PaginatedResponse,
  RefinanciamentoItem,
  RefinanciamentoResumo,
} from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import { formatMonthYear } from "@/lib/formatters";
import { exportPaginatedRouteReport } from "@/lib/reports";
import { RefinanciamentoDetalhesDialog } from "@/components/refinanciamento/refinanciamento-detalhes-dialog";
import MultiSelect from "@/components/custom/multi-select";
import SearchableSelect, { type SelectOption } from "@/components/custom/searchable-select";
import StatusBadge from "@/components/custom/status-badge";
import CopySnippet from "@/components/shared/copy-snippet";
import DataTable, { type DataTableColumn } from "@/components/shared/data-table";
import ReportExportDialog, {
  type ReportExportFilters,
} from "@/components/shared/report-export-dialog";
import { MetricCardSkeleton } from "@/components/shared/page-skeletons";
import StatsCard from "@/components/shared/stats-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Sheet,
  SheetContent,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";

type AnaliseAdvancedFilters = {
  competenciaStart: string;
  competenciaEnd: string;
  agent: string;
  statuses: string[];
  origins: string[];
  assignment: string;
};

type KpiFilterKey = "total" | "em_analise" | "assumidos" | "aprovados";

const STATUS_OPTIONS: SelectOption[] = [
  { value: "em_analise_renovacao", label: "Em análise para renovação" },
  {
    value: "pendente_termo_analista",
    label: "Pendente termo para o analista",
  },
  {
    value: "aprovado_analise_renovacao",
    label: "Aguardando validação da coordenação",
  },
];

const ORIGIN_OPTIONS: SelectOption[] = [
  { value: "legado", label: "Legado" },
  { value: "operacional", label: "Operacional" },
];

const ASSIGNMENT_OPTIONS: SelectOption[] = [
  { value: "todas", label: "Todas" },
  { value: "minhas", label: "Minhas" },
  { value: "nao_assumidas", label: "Não assumidas" },
  { value: "assumidas", label: "Assumidas" },
];

const INITIAL_FILTERS: AnaliseAdvancedFilters = {
  competenciaStart: "",
  competenciaEnd: "",
  agent: "",
  statuses: [],
  origins: [],
  assignment: "todas",
};

function countActiveFilters(filters: AnaliseAdvancedFilters) {
  return [
    filters.competenciaStart,
    filters.competenciaEnd,
    filters.agent,
    filters.statuses.length ? "status" : "",
    filters.origins.length ? "origem" : "",
    filters.assignment !== "todas" ? filters.assignment : "",
  ].filter(Boolean).length;
}

function toCompetenciaDate(value: string) {
  return value ? `${value}-01` : undefined;
}

const EMPTY_RESUMO: RefinanciamentoResumo = {
  total: 0,
  em_analise: 0,
  assumidos: 0,
  aprovados: 0,
  efetivados: 0,
  concluidos: 0,
  bloqueados: 0,
  revertidos: 0,
  em_fluxo: 0,
  com_anexo_agente: 0,
  repasse_total: "0.00",
};

function getKpiLabel(value: KpiFilterKey) {
  if (value === "em_analise") return "Em análise";
  if (value === "assumidos") return "Assumidos";
  if (value === "aprovados") return "Aprovados";
  return "Total";
}

export default function AnaliseAptosPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = React.useState(1);
  const [search, setSearch] = React.useState("");
  const [isExporting, setIsExporting] = React.useState(false);
  const [sheetOpen, setSheetOpen] = React.useState(false);
  const [filters, setFilters] = React.useState<AnaliseAdvancedFilters>(INITIAL_FILTERS);
  const [draftFilters, setDraftFilters] = React.useState<AnaliseAdvancedFilters>(INITIAL_FILTERS);
  const [selected, setSelected] = React.useState<RefinanciamentoItem | null>(null);
  const [dialogAction, setDialogAction] = React.useState<
    "aprovar" | "devolver_agente" | null
  >(null);
  const [detailItem, setDetailItem] = React.useState<RefinanciamentoItem | null>(null);
  const [observacao, setObservacao] = React.useState("");
  const [activeKpi, setActiveKpi] = React.useState<KpiFilterKey>("total");

  const resolvedStatuses = React.useMemo(() => {
    if (activeKpi === "em_analise") {
      return ["em_analise_renovacao", "pendente_termo_analista"];
    }
    if (activeKpi === "aprovados") {
      return ["aprovado_analise_renovacao"];
    }
    return filters.statuses;
  }, [activeKpi, filters.statuses]);

  const resolvedAssignment = React.useMemo(() => {
    if (activeKpi === "assumidos") {
      return "assumidas";
    }
    return filters.assignment;
  }, [activeKpi, filters.assignment]);

  const refinanciamentosQuery = useQuery({
    queryKey: [
      "analise-refinanciamentos",
      page,
      search,
      filters.competenciaStart,
      filters.competenciaEnd,
      filters.agent,
      resolvedStatuses.join(","),
      filters.origins.join(","),
      resolvedAssignment,
      activeKpi,
    ],
    queryFn: () =>
      apiFetch<PaginatedResponse<RefinanciamentoItem>>("analise/refinanciamentos", {
        query: {
          page,
          page_size: 20,
          search: search || undefined,
          competencia_start: toCompetenciaDate(filters.competenciaStart),
          competencia_end: toCompetenciaDate(filters.competenciaEnd),
          agent: filters.agent || undefined,
          status: resolvedStatuses,
          origem: filters.origins,
          assignment: resolvedAssignment !== "todas" ? resolvedAssignment : undefined,
        },
      }),
  });

  const resumoQuery = useQuery({
    queryKey: [
      "analise-refinanciamentos-resumo",
      search,
      filters.competenciaStart,
      filters.competenciaEnd,
      filters.agent,
      filters.statuses.join(","),
      filters.origins.join(","),
      filters.assignment,
    ],
    queryFn: () =>
      apiFetch<RefinanciamentoResumo>("analise/refinanciamentos/resumo", {
        query: {
          search: search || undefined,
          competencia_start: toCompetenciaDate(filters.competenciaStart),
          competencia_end: toCompetenciaDate(filters.competenciaEnd),
          agent: filters.agent || undefined,
          status: filters.statuses,
          origem: filters.origins,
          assignment: filters.assignment !== "todas" ? filters.assignment : undefined,
        },
      }),
  });

  const assumirMutation = useMutation({
    mutationFn: async (id: number) =>
      apiFetch<RefinanciamentoItem>(`refinanciamentos/${id}/assumir_analise`, {
        method: "POST",
      }),
    onSuccess: () => {
      toast.success("Renovação assumida na análise.");
      void queryClient.invalidateQueries({ queryKey: ["analise-refinanciamentos"] });
      void queryClient.invalidateQueries({
        queryKey: ["analise-refinanciamentos-resumo"],
      });
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Falha ao assumir renovação.");
    },
  });

  const aprovarMutation = useMutation({
    mutationFn: async ({
      id,
      note,
    }: {
      id: number;
      note: string;
    }) => {
      return apiFetch<RefinanciamentoItem>(`refinanciamentos/${id}/aprovar_analise`, {
        method: "POST",
        body: { observacao: note },
      });
    },
    onSuccess: () => {
      toast.success("Renovação aprovada e enviada para validação da coordenação.");
      setSelected(null);
      setObservacao("");
      void queryClient.invalidateQueries({ queryKey: ["analise-refinanciamentos"] });
      void queryClient.invalidateQueries({
        queryKey: ["analise-refinanciamentos-resumo"],
      });
      void queryClient.invalidateQueries({ queryKey: ["coordenacao-refinanciamento"] });
      void queryClient.invalidateQueries({ queryKey: ["agente-refinanciados"] });
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Falha ao aprovar renovação.");
    },
  });

  const devolverAgenteMutation = useMutation({
    mutationFn: async ({
      id,
      note,
    }: {
      id: number;
      note: string;
    }) =>
      apiFetch<RefinanciamentoItem>(`refinanciamentos/${id}/devolver-agente`, {
        method: "POST",
        body: { observacao: note },
      }),
    onSuccess: () => {
      toast.success("Renovação devolvida para o agente.");
      setSelected(null);
      setDialogAction(null);
      setObservacao("");
      void queryClient.invalidateQueries({ queryKey: ["analise-refinanciamentos"] });
      void queryClient.invalidateQueries({
        queryKey: ["analise-refinanciamentos-resumo"],
      });
      void queryClient.invalidateQueries({ queryKey: ["agente-refinanciados"] });
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Falha ao devolver renovação.");
    },
  });

  const rows = refinanciamentosQuery.data?.results ?? [];
  const totalCount = refinanciamentosQuery.data?.count ?? 0;
  const activeAdvancedFiltersCount = countActiveFilters(filters);
  const resumo = resumoQuery.data ?? EMPTY_RESUMO;

  const columns = React.useMemo<DataTableColumn<RefinanciamentoItem>[]>(
    () => [
      {
        id: "associado",
        header: "Associado",
        cell: (row) => (
          <div className="space-y-1">
            <p className="font-medium">{row.associado_nome}</p>
            <CopySnippet label="CPF" value={row.cpf_cnpj} mono inline />
          </div>
        ),
      },
      {
        id: "contrato",
        header: "Contrato",
        cell: (row) => (
          <div className="space-y-1">
            <p>{row.contrato_codigo}</p>
            <p className="text-xs text-muted-foreground">
              {row.referencias.map((item) => formatMonthYear(item)).join(", ")}
            </p>
          </div>
        ),
      },
      {
        id: "status",
        header: "Status",
        cell: (row) => (
          <div className="space-y-1">
            <StatusBadge status={row.status} />
            <p className="text-xs text-muted-foreground">
              {row.mensalidades_pagas}/{row.mensalidades_total} parcelas quitadas
            </p>
          </div>
        ),
      },
      {
        id: "motivo",
        header: "Motivo",
        cell: (row) => (
          <p className="max-w-sm text-sm text-muted-foreground">
            {row.coordenador_note?.trim() ||
              row.analista_note?.trim() ||
              row.motivo_apto_renovacao}
          </p>
        ),
      },
      {
        id: "origem",
        header: "Origem",
        cell: (row) => (
          <Badge variant="outline" className="rounded-full border-border/60">
            {row.origem.replaceAll("_", " ")}
          </Badge>
        ),
      },
      {
        id: "acoes",
        header: "Ações",
        cell: (row) => (
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="outline" onClick={() => setDetailItem(row)}>
              <EyeIcon className="size-4" />
              Detalhes
            </Button>
            {["em_analise_renovacao", "pendente_termo_analista"].includes(row.status) ? (
              <Button
                size="sm"
                variant="outline"
                onClick={() => assumirMutation.mutate(row.id)}
              >
                <PlayIcon className="size-4" />
                Assumir
              </Button>
            ) : null}
            {["em_analise_renovacao", "pendente_termo_analista"].includes(row.status) ? (
              <Button
                size="sm"
                onClick={() => {
                  setSelected(row);
                  setDialogAction("aprovar");
                }}
              >
                <ForwardIcon className="size-4" />
                Aprovar
              </Button>
            ) : null}
            {["em_analise_renovacao", "pendente_termo_analista"].includes(row.status) ? (
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  setSelected(row);
                  setDialogAction("devolver_agente");
                }}
              >
                Devolver para agente
              </Button>
            ) : null}
          </div>
        ),
      },
    ],
    [assumirMutation],
  );

  const handleExport = React.useCallback(
    async (
      exportFilters: ReportExportFilters,
      format: "csv" | "pdf" | "excel" | "xlsx",
    ) => {
      if (format !== "pdf" && format !== "xlsx") {
        return;
      }
      const { pagamentoFeito, columns: selectedColumns } = exportFilters;

      setIsExporting(true);
      try {
        await exportPaginatedRouteReport<RefinanciamentoItem>({
          route: "/analise/aptos",
          format,
          sourcePath: "analise/refinanciamentos",
          sourceQuery: {
            search: search || undefined,
            competencia_start: toCompetenciaDate(filters.competenciaStart),
            competencia_end: toCompetenciaDate(filters.competenciaEnd),
            agent: filters.agent || undefined,
            status: resolvedStatuses,
            origem: filters.origins,
            assignment: resolvedAssignment !== "todas" ? resolvedAssignment : undefined,
            pagamento_feito: pagamentoFeito,
          },
          mapRow: (row) => ({
            contrato_codigo: row.contrato_codigo,
            associado_nome: row.associado_nome,
            status: row.status,
            motivo_apto_renovacao: row.motivo_apto_renovacao,
            analista_note: row.analista_note ?? "",
            coordenador_note: row.coordenador_note ?? "",
            data_pagamento_associado: row.data_pagamento_associado,
          }),
          filters: {
            columns: selectedColumns,
            pagamento_feito: pagamentoFeito,
          },
        });
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "Falha ao exportar a fila da análise.");
      } finally {
        setIsExporting(false);
      }
    },
    [filters.agent, filters.competenciaEnd, filters.competenciaStart, filters.origins, resolvedAssignment, resolvedStatuses, search],
  );

  return (
    <div className="space-y-6">
      <section className="rounded-[1.75rem] border border-border/60 bg-card/70 p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-2">
            <p className="text-sm uppercase tracking-[0.28em] text-muted-foreground">
              Análise
            </p>
            <h1 className="text-3xl font-semibold">Contratos para Renovação</h1>
            <p className="text-sm text-muted-foreground">
              Fila do analista para revisar solicitações enviadas pelo agente e encaminhá-las
              para validação da coordenação. Total filtrado: {resumo.total}
            </p>
          </div>
          <ReportExportDialog
            hideScope
            disabled={isExporting}
            label={isExporting ? "Exportando..." : "Exportar"}
            paymentOptions={[
              { value: "sim", label: "Somente pagos" },
              { value: "nao", label: "Somente não pagos" },
            ]}
            onExport={(filters, fmt) => void handleExport(filters, fmt)}
          />
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {resumoQuery.isLoading && !resumoQuery.data ? (
          Array.from({ length: 4 }).map((_, index) => <MetricCardSkeleton key={index} />)
        ) : (
          <>
            <StatsCard
              title="Total"
              value={String(resumo.total)}
              delta={`${resumo.em_analise} em análise no recorte`}
              icon={EyeIcon}
              tone="neutral"
              active={activeKpi === "total"}
              onClick={() => {
                setActiveKpi("total");
                setPage(1);
              }}
            />
            <StatsCard
              title="Em análise"
              value={String(resumo.em_analise)}
              delta={`${resumo.assumidos} já assumidos na fila`}
              icon={ShieldCheckIcon}
              tone="warning"
              active={activeKpi === "em_analise"}
              onClick={() => {
                setActiveKpi("em_analise");
                setPage(1);
              }}
            />
            <StatsCard
              title="Assumidos"
              value={String(resumo.assumidos)}
              delta={`${resumo.aprovados} já aprovados pela análise`}
              icon={PlayIcon}
              tone="neutral"
              active={activeKpi === "assumidos"}
              onClick={() => {
                setActiveKpi("assumidos");
                setPage(1);
              }}
            />
            <StatsCard
              title="Aprovados"
              value={String(resumo.aprovados)}
              delta="Prontos para validação da coordenação"
              icon={BadgeCheckIcon}
              tone="positive"
              active={activeKpi === "aprovados"}
              onClick={() => {
                setActiveKpi("aprovados");
                setPage(1);
              }}
            />
          </>
        )}
      </section>

      <section className="grid gap-3 rounded-[1.75rem] border border-border/60 bg-card/50 p-4 lg:grid-cols-[minmax(0,1fr)_auto]">
        <Input
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
            setPage(1);
          }}
          placeholder="Buscar por associado, CPF ou contrato"
          className="rounded-2xl border-border/60 bg-card/60"
        />
        <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
          <SheetTrigger asChild>
            <Button variant="outline" className="rounded-2xl">
              <SlidersHorizontalIcon className="size-4" />
              Filtros avançados
              {activeAdvancedFiltersCount ? (
                <Badge className="ml-1 rounded-full bg-primary/15 text-primary">
                  {activeAdvancedFiltersCount}
                </Badge>
              ) : null}
            </Button>
          </SheetTrigger>
          <SheetContent className="w-full border-l border-border/60 bg-background/95 sm:max-w-xl">
            <SheetHeader>
              <SheetTitle>Filtros avançados</SheetTitle>
            </SheetHeader>
            <div className="mt-8 space-y-6">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <p className="text-sm font-medium">Competência inicial</p>
                  <Input
                    type="month"
                    value={draftFilters.competenciaStart}
                    onChange={(event) =>
                      setDraftFilters((current) => ({
                        ...current,
                        competenciaStart: event.target.value,
                      }))
                    }
                  />
                </div>
                <div className="space-y-2">
                  <p className="text-sm font-medium">Competência final</p>
                  <Input
                    type="month"
                    value={draftFilters.competenciaEnd}
                    onChange={(event) =>
                      setDraftFilters((current) => ({
                        ...current,
                        competenciaEnd: event.target.value,
                      }))
                    }
                  />
                </div>
                <div className="space-y-2 md:col-span-2">
                  <p className="text-sm font-medium">Agente</p>
                  <Input
                    value={draftFilters.agent}
                    onChange={(event) =>
                      setDraftFilters((current) => ({
                        ...current,
                        agent: event.target.value,
                      }))
                    }
                    placeholder="Nome do agente"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <p className="text-sm font-medium">Status</p>
                <MultiSelect
                  options={STATUS_OPTIONS}
                  value={draftFilters.statuses}
                  onChange={(statuses) =>
                    setDraftFilters((current) => ({ ...current, statuses }))
                  }
                  placeholder="Todos os status"
                />
              </div>

              <div className="space-y-2">
                <p className="text-sm font-medium">Origem</p>
                <MultiSelect
                  options={ORIGIN_OPTIONS}
                  value={draftFilters.origins}
                  onChange={(origins) =>
                    setDraftFilters((current) => ({ ...current, origins }))
                  }
                  placeholder="Todas as origens"
                />
              </div>

              <div className="space-y-2">
                <p className="text-sm font-medium">Atribuição</p>
                <SearchableSelect
                  options={ASSIGNMENT_OPTIONS}
                  value={draftFilters.assignment}
                  onChange={(assignment) =>
                    setDraftFilters((current) => ({
                      ...current,
                      assignment: assignment || "todas",
                    }))
                  }
                  placeholder="Todas"
                />
              </div>
            </div>
            <SheetFooter className="mt-8 flex-row gap-3 sm:justify-between">
              <Button
                variant="outline"
                onClick={() => {
                  setDraftFilters(INITIAL_FILTERS);
                  setFilters(INITIAL_FILTERS);
                  setPage(1);
                  setSheetOpen(false);
                }}
              >
                Limpar filtros
              </Button>
              <Button
                onClick={() => {
                  setFilters(draftFilters);
                  setPage(1);
                  setSheetOpen(false);
                }}
              >
                Aplicar filtros
              </Button>
            </SheetFooter>
          </SheetContent>
        </Sheet>
      </section>

      {activeKpi !== "total" ? (
        <section className="flex flex-wrap items-center gap-3 rounded-[1.5rem] border border-primary/20 bg-primary/5 px-4 py-3">
          <Badge className="rounded-full bg-primary/15 text-primary">
            Filtro rápido: {getKpiLabel(activeKpi)}
          </Badge>
          <p className="text-sm text-muted-foreground">
            A tabela abaixo está recortada pelo card KPI selecionado.
          </p>
          <Button
            variant="ghost"
            size="sm"
            className="ml-auto"
            onClick={() => {
              setActiveKpi("total");
              setPage(1);
            }}
          >
            Limpar filtro rápido
          </Button>
        </section>
      ) : null}

      <DataTable
        data={rows}
        columns={columns}
        currentPage={page}
        totalPages={Math.max(1, Math.ceil(totalCount / 20))}
        onPageChange={setPage}
        emptyMessage="Nenhuma renovação disponível para análise."
        loading={refinanciamentosQuery.isLoading}
        skeletonRows={6}
      />

      <Dialog
        open={!!selected}
        onOpenChange={(open) => {
          if (!open) {
            setSelected(null);
            setDialogAction(null);
            setObservacao("");
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {dialogAction === "devolver_agente"
                ? "Devolver termo para o agente"
                : "Aprovar e enviar à coordenação"}
            </DialogTitle>
            <DialogDescription>
              {dialogAction === "devolver_agente"
                ? "Informe o motivo da devolução. O agente reenviará o termo no mesmo refinanciamento."
                : "O termo enviado pelo agente permanece no histórico. Aqui o analista só registra a observação da validação."}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <Textarea
              value={observacao}
              onChange={(event) => setObservacao(event.target.value)}
              placeholder="Observação do analista"
              className="min-h-28"
            />
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setSelected(null);
                setDialogAction(null);
                setObservacao("");
              }}
            >
              Cancelar
            </Button>
            <Button
              disabled={
                !selected ||
                aprovarMutation.isPending ||
                devolverAgenteMutation.isPending ||
                (dialogAction === "devolver_agente" && !observacao.trim())
              }
              onClick={() => {
                if (!selected) return;
                if (dialogAction === "devolver_agente") {
                  devolverAgenteMutation.mutate({
                    id: selected.id,
                    note: observacao,
                  });
                  return;
                }
                aprovarMutation.mutate({
                  id: selected.id,
                  note: observacao,
                });
              }}
            >
              {dialogAction === "devolver_agente"
                ? "Devolver para agente"
                : "Aprovar e enviar à coordenação"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <RefinanciamentoDetalhesDialog
        open={!!detailItem}
        associadoId={detailItem?.associado_id ?? null}
        refinanciamentoId={detailItem?.id ?? null}
        onOpenChange={(open) => {
          if (!open) {
            setDetailItem(null);
          }
        }}
      />
    </div>
  );
}
