"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BadgeCheckIcon,
  Clock3Icon,
  EyeIcon,
  FileTextIcon,
  Layers3Icon,
  SlidersHorizontalIcon,
  XCircleIcon,
} from "lucide-react";
import { toast } from "sonner";

import type {
  ComprovanteResumo,
  PaginatedResponse,
  RefinanciamentoItem,
} from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import { buildBackendFileUrl } from "@/lib/backend-files";
import { formatMonthYear } from "@/lib/formatters";
import { exportRouteReport, fetchAllPaginatedRows } from "@/lib/reports";
import { RefinanciamentoDetalhesDialog } from "@/components/refinanciamento/refinanciamento-detalhes-dialog";
import MultiSelect from "@/components/custom/multi-select";
import SearchableSelect, {
  type SelectOption,
} from "@/components/custom/searchable-select";
import StatusBadge from "@/components/custom/status-badge";
import { MetricCardSkeleton } from "@/components/shared/page-skeletons";
import CopySnippet from "@/components/shared/copy-snippet";
import DataTable, { type DataTableColumn } from "@/components/shared/data-table";
import ReportExportDialog, {
  type ReportExportFilters,
} from "@/components/shared/report-export-dialog";
import StatsCard from "@/components/shared/stats-card";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Sheet,
  SheetContent,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";

type CoordAdvancedFilters = {
  year: string;
  competenciaStart: string;
  competenciaEnd: string;
  agent: string;
  statuses: string[];
  origins: string[];
  eligibilityBand: string;
};

type SectionQueryResult = {
  data?: PaginatedResponse<RefinanciamentoItem>;
  isLoading: boolean;
};

const PROCESS_STATUS_SET = [
  "aprovado_analise_renovacao",
  "aprovado_para_renovacao",
];
const RENEWED_STATUS_SET = ["efetivado"];
const LIQUIDATION_STATUS_SET = ["solicitado_para_liquidacao"];

const STATUS_OPTIONS: SelectOption[] = [
  {
    value: "aprovado_analise_renovacao",
    label: "Aguardando validação da coordenação",
  },
  { value: "aprovado_para_renovacao", label: "Enviado para tesouraria" },
  { value: "efetivado", label: "Renovado" },
  { value: "solicitado_para_liquidacao", label: "Em liquidação" },
];

const ORIGIN_OPTIONS: SelectOption[] = [
  { value: "legado", label: "Legado" },
  { value: "operacional", label: "Operacional" },
];

const ELIGIBILITY_OPTIONS: SelectOption[] = [
  { value: "", label: "Todas as faixas" },
  { value: "2_3", label: "2/3" },
  { value: "3_3", label: "3/3" },
  { value: "3_4", label: "3/4" },
  { value: "4_4", label: "4/4" },
];

const INITIAL_FILTERS: CoordAdvancedFilters = {
  year: String(new Date().getFullYear()),
  competenciaStart: "",
  competenciaEnd: "",
  agent: "",
  statuses: [],
  origins: [],
  eligibilityBand: "",
};

function countActiveFilters(filters: CoordAdvancedFilters) {
  return [
    filters.year && filters.year !== INITIAL_FILTERS.year ? filters.year : "",
    filters.competenciaStart,
    filters.competenciaEnd,
    filters.agent,
    filters.statuses.length ? "status" : "",
    filters.origins.length ? "origem" : "",
    filters.eligibilityBand,
  ].filter(Boolean).length;
}

function toCompetenciaDate(value: string) {
  return value ? `${value}-01` : undefined;
}

function getSolicitacaoAttachment(
  comprovantes: RefinanciamentoItem["comprovantes"],
) {
  return (
    comprovantes.find(
      (comprovante) =>
        comprovante.tipo === "termo_antecipacao" ||
        comprovante.origem === "solicitacao_renovacao",
    ) ?? null
  );
}

function resolveSectionStatuses(
  selectedStatuses: string[],
  defaultStatuses: string[],
) {
  if (!selectedStatuses.length) {
    return defaultStatuses;
  }

  const resolved = defaultStatuses.filter((status) =>
    selectedStatuses.includes(status),
  );
  return resolved.length ? resolved : ["__none__"];
}

function AttachmentCell({
  comprovante,
}: {
  comprovante: ComprovanteResumo | null;
}) {
  if (!comprovante) {
    return (
      <span className="text-xs text-muted-foreground">
        Sem termo anexado.
      </span>
    );
  }

  if (comprovante.arquivo_disponivel_localmente) {
    return (
      <Button asChild size="sm" variant="outline">
        <a
          href={buildBackendFileUrl(comprovante.arquivo)}
          target="_blank"
          rel="noreferrer"
        >
          <FileTextIcon className="size-4" />
          Ver termo
        </a>
      </Button>
    );
  }

  return (
    <span
      className="inline-flex rounded-full border border-dashed border-border/60 px-3 py-1 text-xs text-muted-foreground"
      title={comprovante.arquivo_referencia}
    >
      Referência legado
    </span>
  );
}

function SectionTable({
  title,
  description,
  query,
  page,
  onPageChange,
  columns,
  emptyMessage,
}: {
  title: string;
  description: string;
  query: SectionQueryResult;
  page: number;
  onPageChange: (page: number) => void;
  columns: DataTableColumn<RefinanciamentoItem>[];
  emptyMessage: string;
}) {
  const rows = query.data?.results ?? [];
  const totalCount = query.data?.count ?? 0;

  return (
    <section className="space-y-3">
      <div className="space-y-1 px-1">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-xl font-semibold">{title}</h2>
          <Badge className="rounded-full bg-primary/15 text-primary">
            {totalCount}
          </Badge>
        </div>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>

      <DataTable
        data={rows}
        columns={columns}
        currentPage={page}
        totalPages={Math.max(1, Math.ceil(totalCount / 20))}
        onPageChange={onPageChange}
        emptyMessage={emptyMessage}
        loading={query.isLoading}
        skeletonRows={5}
      />
    </section>
  );
}

export default function CoordenacaoRefinanciadosPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = React.useState("");
  const [isExporting, setIsExporting] = React.useState(false);
  const [sheetOpen, setSheetOpen] = React.useState(false);
  const [filters, setFilters] = React.useState<CoordAdvancedFilters>(INITIAL_FILTERS);
  const [draftFilters, setDraftFilters] = React.useState<CoordAdvancedFilters>(
    INITIAL_FILTERS,
  );
  const [renovadosPage, setRenovadosPage] = React.useState(1);
  const [processoPage, setProcessoPage] = React.useState(1);
  const [liquidacaoPage, setLiquidacaoPage] = React.useState(1);
  const [detailItem, setDetailItem] = React.useState<RefinanciamentoItem | null>(null);
  const [cancelTarget, setCancelTarget] = React.useState<RefinanciamentoItem | null>(
    null,
  );

  const activeAdvancedFiltersCount = countActiveFilters(filters);
  const renovadosStatuses = React.useMemo(
    () => resolveSectionStatuses(filters.statuses, RENEWED_STATUS_SET),
    [filters.statuses],
  );
  const processoStatuses = React.useMemo(
    () => resolveSectionStatuses(filters.statuses, PROCESS_STATUS_SET),
    [filters.statuses],
  );
  const liquidacaoStatuses = React.useMemo(
    () => resolveSectionStatuses(filters.statuses, LIQUIDATION_STATUS_SET),
    [filters.statuses],
  );

  React.useEffect(() => {
    setRenovadosPage(1);
    setProcessoPage(1);
    setLiquidacaoPage(1);
  }, [
    search,
    filters.year,
    filters.competenciaStart,
    filters.competenciaEnd,
    filters.agent,
    filters.statuses.join(","),
    filters.origins.join(","),
    filters.eligibilityBand,
  ]);

  const buildQuery = React.useCallback(
    (page: number, statuses: string[]) => ({
      page,
      page_size: 20,
      search: search || undefined,
      year: filters.year || undefined,
      competencia_start: toCompetenciaDate(filters.competenciaStart),
      competencia_end: toCompetenciaDate(filters.competenciaEnd),
      agent: filters.agent || undefined,
      status: statuses,
      origem: filters.origins,
      eligibility_band: filters.eligibilityBand || undefined,
    }),
    [
      search,
      filters.year,
      filters.competenciaStart,
      filters.competenciaEnd,
      filters.agent,
      filters.origins,
      filters.eligibilityBand,
    ],
  );

  const renovadosQuery = useQuery({
    queryKey: [
      "coordenacao-refinanciados",
      "renovados",
      renovadosPage,
      search,
      filters.year,
      filters.competenciaStart,
      filters.competenciaEnd,
      filters.agent,
      filters.statuses.join(","),
      filters.origins.join(","),
      filters.eligibilityBand,
    ],
    queryFn: () =>
      apiFetch<PaginatedResponse<RefinanciamentoItem>>("coordenacao/refinanciados", {
        query: buildQuery(renovadosPage, renovadosStatuses),
      }),
  });

  const processoQuery = useQuery({
    queryKey: [
      "coordenacao-refinanciados",
      "processo",
      processoPage,
      search,
      filters.year,
      filters.competenciaStart,
      filters.competenciaEnd,
      filters.agent,
      filters.statuses.join(","),
      filters.origins.join(","),
      filters.eligibilityBand,
    ],
    queryFn: () =>
      apiFetch<PaginatedResponse<RefinanciamentoItem>>("coordenacao/refinanciados", {
        query: buildQuery(processoPage, processoStatuses),
      }),
  });

  const liquidacaoQuery = useQuery({
    queryKey: [
      "coordenacao-refinanciados",
      "liquidacao",
      liquidacaoPage,
      search,
      filters.year,
      filters.competenciaStart,
      filters.competenciaEnd,
      filters.agent,
      filters.statuses.join(","),
      filters.origins.join(","),
      filters.eligibilityBand,
    ],
    queryFn: () =>
      apiFetch<PaginatedResponse<RefinanciamentoItem>>("coordenacao/refinanciados", {
        query: buildQuery(liquidacaoPage, liquidacaoStatuses),
      }),
  });

  const cancelMutation = useMutation({
    mutationFn: async (id: number) =>
      apiFetch<RefinanciamentoItem>(`refinanciamentos/${id}/encaminhar-liquidacao`, {
        method: "POST",
      }),
    onSuccess: () => {
      toast.success("Contrato enviado para a fila de liquidação pendente.");
      setCancelTarget(null);
      void queryClient.invalidateQueries({ queryKey: ["coordenacao-refinanciados"] });
      void queryClient.invalidateQueries({ queryKey: ["coordenacao-refinanciamento"] });
      void queryClient.invalidateQueries({ queryKey: ["tesouraria-liquidacoes"] });
    },
    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : "Falha ao cancelar a renovação.",
      );
    },
  });

  const totalRenovados = renovadosQuery.data?.count ?? 0;
  const totalProcesso = processoQuery.data?.count ?? 0;
  const totalLiquidacao = liquidacaoQuery.data?.count ?? 0;
  const totalGeral = totalRenovados + totalProcesso + totalLiquidacao;
  const kpisLoading =
    (renovadosQuery.isLoading && !renovadosQuery.data) ||
    (processoQuery.isLoading && !processoQuery.data) ||
    (liquidacaoQuery.isLoading && !liquidacaoQuery.data);

  const baseColumns = React.useMemo<DataTableColumn<RefinanciamentoItem>[]>(
    () => [
      {
        id: "agente",
        header: "Agente",
        cell: (row) => row.agente?.full_name ?? "—",
      },
      {
        id: "associado",
        header: "Associado",
        cell: (row) => <p className="font-medium">{row.associado_nome}</p>,
      },
      {
        id: "matricula_cpf",
        header: "Matrícula / CPF",
        cell: (row) => (
          <div className="space-y-1">
            <p>{row.matricula_display || row.matricula || "—"}</p>
            <CopySnippet label="CPF" value={row.cpf_cnpj} mono inline />
          </div>
        ),
      },
      {
        id: "referencias",
        header: "Referências",
        cell: (row) => (
          <div className="space-y-1">
            {row.referencias.map((referencia) => (
              <p key={referencia}>{formatMonthYear(referencia)}</p>
            ))}
          </div>
        ),
      },
      {
        id: "mensalidades",
        header: "Mensalidades",
        cell: (row) => `${row.mensalidades_pagas}/${row.mensalidades_total}`,
      },
      {
        id: "ciclos",
        header: "Nº de ciclos",
        cell: (row) => row.numero_ciclos,
      },
      {
        id: "status",
        header: "Status / Motivo",
        cellClassName: "min-w-[240px]",
        cell: (row) => (
          <div className="space-y-2">
            <StatusBadge status={row.status} />
            <p className="text-xs text-muted-foreground">
              {row.coordenador_note?.trim() ||
                row.analista_note?.trim() ||
                row.motivo_apto_renovacao}
            </p>
          </div>
        ),
      },
      {
        id: "anexo",
        header: "Anexo",
        cell: (row) => (
          <AttachmentCell
            comprovante={getSolicitacaoAttachment(row.comprovantes)}
          />
        ),
      },
    ],
    [],
  );

  const readOnlyColumns = React.useMemo<DataTableColumn<RefinanciamentoItem>[]>(
    () => [
      ...baseColumns,
      {
        id: "acoes",
        header: "Ações",
        cellClassName: "min-w-[180px]",
        cell: (row) => (
          <Button size="sm" variant="outline" onClick={() => setDetailItem(row)}>
            <EyeIcon className="size-4" />
            Ver detalhes
          </Button>
        ),
      },
    ],
    [baseColumns],
  );

  const processoColumns = React.useMemo<DataTableColumn<RefinanciamentoItem>[]>(
    () => [
      ...baseColumns,
      {
        id: "acoes",
        header: "Ações",
        cellClassName: "min-w-[260px]",
        cell: (row) => (
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="outline" onClick={() => setDetailItem(row)}>
              <EyeIcon className="size-4" />
              Ver detalhes
            </Button>
            <Button size="sm" variant="outline" onClick={() => setCancelTarget(row)}>
              Cancelar renovação
            </Button>
          </div>
        ),
      },
    ],
    [baseColumns],
  );

  const handleExport = React.useCallback(
    async (exportFilters: ReportExportFilters, format: "pdf" | "xlsx") => {
      const { pagamentoFeito, columns: selectedColumns } = exportFilters;
      setIsExporting(true);
      try {
        const baseQuery = {
          ...buildQuery(1, renovadosStatuses),
          page: undefined,
          page_size: undefined,
          pagamento_feito: pagamentoFeito,
        };
        const [renovados, processo, liquidacao] = await Promise.all([
          fetchAllPaginatedRows<RefinanciamentoItem>({
            sourcePath: "coordenacao/refinanciados",
            sourceQuery: { ...baseQuery, status: renovadosStatuses },
          }),
          fetchAllPaginatedRows<RefinanciamentoItem>({
            sourcePath: "coordenacao/refinanciados",
            sourceQuery: { ...baseQuery, status: processoStatuses },
          }),
          fetchAllPaginatedRows<RefinanciamentoItem>({
            sourcePath: "coordenacao/refinanciados",
            sourceQuery: { ...baseQuery, status: liquidacaoStatuses },
          }),
        ]);

        await exportRouteReport({
          route: "/coordenacao/refinanciados",
          format,
          rows: [...renovados, ...processo, ...liquidacao].map((row) => ({
            contrato_codigo: row.contrato_codigo,
            associado_nome: row.associado_nome,
            status: row.status,
            data_solicitacao: row.data_solicitacao,
            executado_em: row.executado_em,
            data_pagamento_associado: row.data_pagamento_associado,
            valor_refinanciamento: row.valor_liberado_associado,
            repasse_agente: row.repasse_agente,
            analista_note: row.analista_note ?? "",
            coordenador_note: row.coordenador_note ?? "",
          })),
          filters: {
            ...baseQuery,
            columns: selectedColumns,
          },
        });
      } catch (error) {
        toast.error(
          error instanceof Error
            ? error.message
            : "Falha ao exportar refinanciados da coordenação.",
        );
      } finally {
        setIsExporting(false);
      }
    },
    [buildQuery, liquidacaoStatuses, processoStatuses, renovadosStatuses],
  );

  return (
    <div className="space-y-6">
      <section className="rounded-[1.75rem] border border-border/60 bg-card/70 p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-2">
            <p className="text-sm uppercase tracking-[0.28em] text-muted-foreground">
              Coordenação
            </p>
            <h1 className="text-3xl font-semibold">Refinanciados</h1>
          </div>
          <ReportExportDialog
            hideScope
            disabled={isExporting}
            label={isExporting ? "Exportando..." : "Exportar"}
            paymentOptions={[
              { value: "sim", label: "Somente pagos" },
              { value: "nao", label: "Somente não pagos" },
            ]}
            onExport={handleExport}
          />
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {kpisLoading ? (
          Array.from({ length: 4 }).map((_, index) => (
            <MetricCardSkeleton key={index} />
          ))
        ) : (
          <>
            <StatsCard
              title="Total"
              value={String(totalGeral)}
              delta="Itens distribuídos nas três esteiras"
              icon={Layers3Icon}
              tone="neutral"
            />
            <StatsCard
              title="Renovados"
              value={String(totalRenovados)}
              delta="Contratos efetivados pela tesouraria"
              icon={BadgeCheckIcon}
              tone="positive"
            />
            <StatsCard
              title="Em processo"
              value={String(totalProcesso)}
              delta="Renovações ainda em andamento"
              icon={Clock3Icon}
              tone="neutral"
            />
            <StatsCard
              title="Em liquidação"
              value={String(totalLiquidacao)}
              delta="Contratos retirados da renovação"
              icon={XCircleIcon}
              tone="warning"
            />
          </>
        )}
      </section>

      <section className="grid gap-3 rounded-[1.75rem] border border-border/60 bg-card/50 p-4 lg:grid-cols-[minmax(0,1fr)_auto]">
        <Input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Buscar por associado, CPF, matrícula, contrato ou agente"
          className="rounded-2xl border-border/60 bg-card/60"
        />
        <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
          <SheetTrigger asChild>
            <Button variant="outline" className="rounded-2xl">
              <SlidersHorizontalIcon className="size-4" />
              Filtros avançados
              {activeAdvancedFiltersCount ? (
                <Badge className="ml-1 rounded-full bg-primary/15 px-2 py-0 text-[11px] text-primary">
                  {activeAdvancedFiltersCount}
                </Badge>
              ) : null}
            </Button>
          </SheetTrigger>
          <SheetContent className="w-full border-l border-border/60 bg-background/95 sm:max-w-xl">
            <SheetHeader className="border-b border-border/60">
              <SheetTitle>Filtros avançados</SheetTitle>
            </SheetHeader>
            <div className="flex min-h-0 flex-1 flex-col">
              <div className="flex-1 overflow-y-auto px-4 py-4">
                <div className="space-y-6">
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                      <p className="text-sm font-medium">Ano</p>
                      <Input
                        value={draftFilters.year}
                        onChange={(event) =>
                          setDraftFilters((current) => ({
                            ...current,
                            year: event.target.value,
                          }))
                        }
                        placeholder="2026"
                      />
                    </div>
                    <div className="space-y-2">
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
                    <p className="text-sm font-medium">Faixa de elegibilidade</p>
                    <SearchableSelect
                      options={ELIGIBILITY_OPTIONS}
                      value={draftFilters.eligibilityBand}
                      onChange={(eligibilityBand) =>
                        setDraftFilters((current) => ({
                          ...current,
                          eligibilityBand,
                        }))
                      }
                      placeholder="Todas as faixas"
                      clearValue=""
                    />
                  </div>
                </div>
              </div>

              <SheetFooter className="border-t border-border/60 sm:flex-row sm:justify-between">
                <Button
                  variant="outline"
                  onClick={() => {
                    setDraftFilters(INITIAL_FILTERS);
                    setFilters(INITIAL_FILTERS);
                    setSheetOpen(false);
                  }}
                >
                  Limpar filtros
                </Button>
                <Button
                  onClick={() => {
                    setFilters(draftFilters);
                    setSheetOpen(false);
                  }}
                >
                  Aplicar filtros
                </Button>
              </SheetFooter>
            </div>
          </SheetContent>
        </Sheet>
      </section>

      <SectionTable
        title="Contratos renovados"
        description="Contratos já efetivados pela tesouraria dentro desta esteira."
        query={renovadosQuery}
        page={renovadosPage}
        onPageChange={setRenovadosPage}
        columns={readOnlyColumns}
        emptyMessage="Nenhum contrato renovado encontrado."
      />

      <SectionTable
        title="Contratos em processo de renovação"
        description="Renovações que ainda estão sendo acompanhadas pela coordenação ou aguardando tratativa da tesouraria."
        query={processoQuery}
        page={processoPage}
        onPageChange={setProcessoPage}
        columns={processoColumns}
        emptyMessage="Nenhum contrato em processo de renovação."
      />

      <SectionTable
        title="Contratos em liquidação"
        description="Contratos retirados da renovação e encaminhados para a fila de liquidações pendentes."
        query={liquidacaoQuery}
        page={liquidacaoPage}
        onPageChange={setLiquidacaoPage}
        columns={readOnlyColumns}
        emptyMessage="Nenhum contrato encaminhado para liquidação."
      />

      <AlertDialog
        open={!!cancelTarget}
        onOpenChange={(open) => !open && setCancelTarget(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Cancelar renovação</AlertDialogTitle>
            <AlertDialogDescription>
              O contrato sairá da esteira de renovação e será movido para a fila
              de liquidações pendentes da tesouraria.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              disabled={cancelMutation.isPending}
              onClick={(event) => {
                event.preventDefault();
                if (!cancelTarget) return;
                cancelMutation.mutate(cancelTarget.id);
              }}
            >
              Confirmar cancelamento
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

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
