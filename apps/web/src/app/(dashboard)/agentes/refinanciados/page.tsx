"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BadgeCheckIcon,
  ClipboardCheckIcon,
  HandCoinsIcon,
  PaperclipIcon,
  RefreshCcwIcon,
  SlidersHorizontalIcon,
  WalletIcon,
} from "lucide-react";
import { toast } from "sonner";

import type {
  ContratoListItem,
  PaginatedResponse,
  RefinanciamentoItem,
  RefinanciamentoResumo,
  SimpleUser,
} from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import { buildBackendFileUrl } from "@/lib/backend-files";
import {
  formatDateValue,
  formatMonthValue,
  parseDateValue,
  parseMonthValue,
} from "@/lib/date-value";
import {
  formatCurrency,
  formatDate,
  formatDateTime,
  formatMonthYear,
} from "@/lib/formatters";
import { maskCPFCNPJ } from "@/lib/masks";
import { exportPaginatedRouteReport } from "@/lib/reports";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { usePermissions } from "@/hooks/use-permissions";
import AssociadoDetailsDialog from "@/components/associados/associado-details-dialog";
import FileUploadDropzone from "@/components/custom/file-upload-dropzone";
import CalendarCompetencia from "@/components/custom/calendar-competencia";
import DatePicker from "@/components/custom/date-picker";
import SearchableSelect from "@/components/custom/searchable-select";
import StatusBadge from "@/components/custom/status-badge";
import CopySnippet from "@/components/shared/copy-snippet";
import DataTable, { type DataTableColumn } from "@/components/shared/data-table";
import ExportButton from "@/components/shared/export-button";
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Sheet,
  SheetContent,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

type RefinanciadosTab = "historico" | "aptos";
type HistoryAdvancedFilters = {
  status: string;
  competenciaStart: string;
  competenciaEnd: string;
};
type AptosAdvancedFilters = {
  dataInicio: string;
  dataFim: string;
  agente: string;
};

const HISTORY_STATUS_OPTIONS = [
  { value: "todos", label: "Todos no fluxo" },
  { value: "solicitado_para_liquidacao", label: "Solicitada para liquidação" },
  { value: "em_analise_renovacao", label: "Em análise" },
  { value: "pendente_termo_analista", label: "Pendente termo no analista" },
  { value: "pendente_termo_agente", label: "Pendente termo no agente" },
  { value: "aprovado_analise_renovacao", label: "Aguardando coordenação" },
  { value: "aprovado_para_renovacao", label: "Aguardando tesouraria" },
  { value: "efetivado", label: "Efetivados" },
  { value: "concluido", label: "Concluídos" },
  { value: "bloqueado", label: "Bloqueados" },
  { value: "revertido", label: "Revertidos" },
  { value: "desativado", label: "Desativados" },
];

const TERMO_ACCEPT = {
  "application/pdf": [".pdf"],
  "image/png": [".png"],
  "image/jpeg": [".jpg", ".jpeg"],
};

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

const INITIAL_HISTORY_FILTERS: HistoryAdvancedFilters = {
  status: "todos",
  competenciaStart: "",
  competenciaEnd: "",
};
const INITIAL_APTOS_FILTERS: AptosAdvancedFilters = {
  dataInicio: "",
  dataFim: "",
  agente: "",
};
const APTOS_STATUS_RENOVACAO = ["apto_a_renovar", "pendente_termo_agente"];

function toCompetenciaDate(value: string) {
  return value ? `${value}-01` : undefined;
}

function countActiveHistoryFilters(filters: HistoryAdvancedFilters) {
  return [
    filters.status !== "todos" ? filters.status : "",
    filters.competenciaStart,
    filters.competenciaEnd,
  ].filter(Boolean).length;
}

function countActiveAptosFilters(
  filters: AptosAdvancedFilters,
  includeAgentFilter: boolean,
) {
  return [
    filters.dataInicio,
    filters.dataFim,
    includeAgentFilter ? filters.agente : "",
  ].filter(Boolean).length;
}

export default function AgenteRefinanciadosPage() {
  const { hasAnyRole } = usePermissions();
  const queryClient = useQueryClient();
  const [tab, setTab] = React.useState<RefinanciadosTab>("historico");
  const [search, setSearch] = React.useState("");
  const [isExporting, setIsExporting] = React.useState(false);
  const [historyFilters, setHistoryFilters] =
    React.useState<HistoryAdvancedFilters>(INITIAL_HISTORY_FILTERS);
  const [draftHistoryFilters, setDraftHistoryFilters] =
    React.useState<HistoryAdvancedFilters>(INITIAL_HISTORY_FILTERS);
  const [aptosFilters, setAptosFilters] =
    React.useState<AptosAdvancedFilters>(INITIAL_APTOS_FILTERS);
  const [draftAptosFilters, setDraftAptosFilters] =
    React.useState<AptosAdvancedFilters>(INITIAL_APTOS_FILTERS);
  const [historySheetOpen, setHistorySheetOpen] = React.useState(false);
  const [aptosSheetOpen, setAptosSheetOpen] = React.useState(false);
  const [pageSize, setPageSize] = React.useState("15");
  const [page, setPage] = React.useState(1);
  const [sendTarget, setSendTarget] = React.useState<ContratoListItem | null>(null);
  const [liquidacaoTarget, setLiquidacaoTarget] = React.useState<ContratoListItem | null>(null);
  const [termo, setTermo] = React.useState<File | null>(null);
  const [detailAssociadoId, setDetailAssociadoId] = React.useState<number | null>(null);
  const debouncedSearch = useDebouncedValue(search, 300);
  const canViewGlobalAptos = hasAnyRole(["ADMIN", "COORDENADOR", "ANALISTA"]);
  const canStartRenewal = hasAnyRole(["ADMIN", "COORDENADOR", "ANALISTA", "AGENTE"]);
  const canRequestLiquidation = hasAnyRole(["ADMIN", "AGENTE"]);
  const aptosDescription = canViewGlobalAptos
    ? "Esta aba mostra todos os contratos do sistema que já podem receber o termo de antecipação e seguir para a análise."
    : "Esta aba mostra somente os contratos do agente que já podem receber o termo de antecipação e seguir para a análise.";

  const resolvedHistoryStatus =
    historyFilters.status === "todos"
      ? [
          "solicitado_para_liquidacao",
          "em_analise_renovacao",
          "pendente_termo_analista",
          "pendente_termo_agente",
          "aprovado_analise_renovacao",
          "aprovado_para_renovacao",
          "efetivado",
          "concluido",
          "bloqueado",
          "revertido",
          "desativado",
        ].join(",")
      : historyFilters.status;
  const activeHistoryFiltersCount = countActiveHistoryFilters(historyFilters);
  const activeAptosFiltersCount = countActiveAptosFilters(
    aptosFilters,
    canViewGlobalAptos,
  );

  const aptosAgentQuery = useQuery({
    queryKey: ["agente-refinanciados", "aptos", "agentes"],
    enabled: canViewGlobalAptos,
    queryFn: () => apiFetch<SimpleUser[]>("associados/agentes"),
  });

  const aptosAgentOptions = React.useMemo(
    () =>
      (aptosAgentQuery.data ?? []).map((agent) => ({
        value: String(agent.id),
        label: agent.full_name,
      })),
    [aptosAgentQuery.data],
  );

  const aptosQueryFilters = React.useMemo(
    () => ({
      associado: debouncedSearch || undefined,
      status_renovacao: APTOS_STATUS_RENOVACAO,
      data_inicio: aptosFilters.dataInicio || undefined,
      data_fim: aptosFilters.dataFim || undefined,
      agente:
        canViewGlobalAptos && aptosFilters.agente
          ? aptosFilters.agente
          : undefined,
    }),
    [
      aptosFilters.agente,
      aptosFilters.dataFim,
      aptosFilters.dataInicio,
      canViewGlobalAptos,
      debouncedSearch,
    ],
  );

  const refinanciamentosQuery = useQuery({
    queryKey: [
      "agente-refinanciados",
      "historico",
      debouncedSearch,
      resolvedHistoryStatus,
      historyFilters.competenciaStart,
      historyFilters.competenciaEnd,
      pageSize,
      page,
    ],
    enabled: tab === "historico",
    queryFn: () =>
      apiFetch<PaginatedResponse<RefinanciamentoItem>>("refinanciamentos", {
        query: {
          page,
          page_size: Number(pageSize),
          search: debouncedSearch || undefined,
          status: resolvedHistoryStatus,
          competencia_start: toCompetenciaDate(historyFilters.competenciaStart),
          competencia_end: toCompetenciaDate(historyFilters.competenciaEnd),
        },
      }),
  });

  const resumoQuery = useQuery({
    queryKey: [
      "agente-refinanciados",
      "resumo",
      debouncedSearch,
      resolvedHistoryStatus,
      historyFilters.competenciaStart,
      historyFilters.competenciaEnd,
    ],
    enabled: tab === "historico",
    queryFn: () =>
      apiFetch<RefinanciamentoResumo>("refinanciamentos/resumo", {
        query: {
          search: debouncedSearch || undefined,
          status: resolvedHistoryStatus,
          competencia_start: toCompetenciaDate(historyFilters.competenciaStart),
          competencia_end: toCompetenciaDate(historyFilters.competenciaEnd),
        },
      }),
  });

  const aptosQuery = useQuery({
    queryKey: ["agente-refinanciados", "aptos", aptosQueryFilters, pageSize, page],
    enabled: tab === "aptos",
    queryFn: () =>
      apiFetch<PaginatedResponse<ContratoListItem>>("contratos", {
        query: {
          page,
          page_size: Number(pageSize),
          ...aptosQueryFilters,
        },
      }),
  });

  const solicitarMutation = useMutation({
    mutationFn: async ({
      contratoId,
      file,
    }: {
      contratoId: number;
      file: File;
    }) => {
      const formData = new FormData();
      formData.set("termo_antecipacao", file);
      return apiFetch<RefinanciamentoItem>(`refinanciamentos/${contratoId}/solicitar`, {
        method: "POST",
        formData,
      });
    },
    onSuccess: () => {
      toast.success("Renovação enviada para análise.");
      setSendTarget(null);
      setTermo(null);
      setTab("historico");
      setHistoryFilters((current) => ({
        ...current,
        status: "em_analise_renovacao",
      }));
      setDraftHistoryFilters((current) => ({
        ...current,
        status: "em_analise_renovacao",
      }));
      setPage(1);
      void queryClient.invalidateQueries({ queryKey: ["agente-refinanciados"] });
      void queryClient.invalidateQueries({ queryKey: ["analise-refinanciamentos"] });
      void queryClient.invalidateQueries({
        queryKey: ["analise-refinanciamentos-resumo"],
      });
      void queryClient.invalidateQueries({ queryKey: ["contratos"] });
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : "Falha ao enviar renovação para análise.",
      );
    },
  });

  const solicitarLiquidacaoMutation = useMutation({
    mutationFn: async ({ contratoId }: { contratoId: number }) =>
      apiFetch<RefinanciamentoItem>(`refinanciamentos/${contratoId}/solicitar-liquidacao`, {
        method: "POST",
        body: {},
      }),
    onSuccess: () => {
      toast.success("Solicitação de liquidação enviada para tesouraria.");
      setLiquidacaoTarget(null);
      setTab("historico");
      setHistoryFilters((current) => ({
        ...current,
        status: "solicitado_para_liquidacao",
      }));
      setDraftHistoryFilters((current) => ({
        ...current,
        status: "solicitado_para_liquidacao",
      }));
      setPage(1);
      void queryClient.invalidateQueries({ queryKey: ["agente-refinanciados"] });
      void queryClient.invalidateQueries({ queryKey: ["tesouraria-liquidacoes"] });
      void queryClient.invalidateQueries({ queryKey: ["contratos"] });
    },
    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : "Falha ao solicitar a liquidação do contrato.",
      );
    },
  });

  const refinanciadosRows = refinanciamentosQuery.data?.results ?? [];
  const aptosRows = aptosQuery.data?.results ?? [];
  const resumo = resumoQuery.data ?? EMPTY_RESUMO;

  const refinanciadosColumns = React.useMemo<DataTableColumn<RefinanciamentoItem>[]>(
    () => [
      {
        id: "associado",
        header: "Associado",
        cellClassName: "min-w-[20rem]",
        cell: (row) => (
          <AssociadoSummary
            nome={row.associado_nome}
            cpf={row.cpf_cnpj}
            matricula={row.matricula_display || row.matricula}
          />
        ),
      },
      {
        id: "contrato",
        header: "Contrato",
        cellClassName: "min-w-[14rem]",
        cell: (row) => (
          <div className="space-y-2">
            <p className="font-mono text-xs text-foreground">{row.contrato_codigo}</p>
            <StatusBadge status={row.status} />
          </div>
        ),
      },
      {
        id: "ciclo",
        header: "Ciclo",
        cellClassName: "min-w-[14rem]",
        cell: (row) => <CycleSignature cicloKey={row.ciclo_key} />,
      },
      {
        id: "refs",
        header: "Referências",
        cellClassName: "min-w-[14rem]",
        cell: (row) => <ReferenceList referencias={row.referencias} />,
      },
      {
        id: "ativacao",
        header: "Renovação",
        cellClassName: "min-w-[15rem]",
        cell: (row) => <RenovacaoSummary row={row} />,
      },
      {
        id: "repasse",
        header: "Repasse agente",
        cellClassName: "whitespace-nowrap",
        cell: (row) => (
          <span className="font-medium text-emerald-400">
            {formatCurrency(row.repasse_agente)}
          </span>
        ),
      },
      {
        id: "comprovantes",
        header: "Anexo do agente",
        cellClassName: "min-w-[16rem]",
        cell: (row) => <AgentAttachmentList comprovantes={row.comprovantes} />,
      },
    ],
    [],
  );

  const aptosColumns = React.useMemo<DataTableColumn<ContratoListItem>[]>(
    () => {
      const columns: DataTableColumn<ContratoListItem>[] = [
        {
          id: "nome",
          header: "Nome",
          cellClassName: "min-w-[16rem]",
          cell: (row) => (
            <CopySnippet
              label="Nome"
              value={row.associado.nome_completo}
              inline
              className="max-w-full"
            />
          ),
        },
        {
          id: "cpf",
          header: "CPF",
          cellClassName: "min-w-[11rem]",
          cell: (row) => <CopySnippet label="CPF" value={row.associado.cpf_cnpj} mono inline />,
        },
        {
          id: "matricula",
          header: "Matrícula do Servidor",
          cellClassName: "min-w-[12rem]",
          cell: (row) => (
            <CopySnippet
              label="Matrícula do Servidor"
              value={row.associado.matricula_display || row.associado.matricula || "N/I"}
              mono
              inline
            />
          ),
        },
      ];

      if (canViewGlobalAptos) {
        columns.push({
          id: "agente",
          header: "Agente responsável",
          cellClassName: "min-w-[14rem]",
          cell: (row) => (
            <div className="space-y-1">
              <p className="font-medium">{row.agente?.full_name || "Sem agente"}</p>
              <p className="text-xs text-muted-foreground">
                Data do contrato: {formatDate(row.data_contrato)}
              </p>
            </div>
          ),
        });
      }

      columns.push(
        {
          id: "contrato",
          header: "Contrato atual",
          cellClassName: "min-w-[15rem]",
          cell: (row) => (
            <div className="space-y-2">
              <p className="font-mono text-xs text-foreground">{row.codigo}</p>
              <StatusBadge
                status={row.status_renovacao || "apto_a_renovar"}
                label={
                  row.status_renovacao === "pendente_termo_agente"
                    ? "Aguardando novo termo"
                    : "Apto a renovar"
                }
              />
            </div>
          ),
        },
        {
          id: "ciclo_apto",
          header: "Ciclo que gerou o apto",
          cellClassName: "min-w-[15rem]",
          cell: (row) => (
            <div className="space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <p className="font-medium">
                  Ciclo {row.ciclo_apto?.numero ?? "N/I"}
                </p>
                {row.ciclo_apto ? (
                  <StatusBadge
                    status={row.ciclo_apto.status_visual_slug}
                    label={row.ciclo_apto.status_visual_label}
                  />
                ) : null}
              </div>
              <p className="text-xs text-muted-foreground">
                {row.ciclo_apto?.resumo_referencias || row.mensalidades.descricao}
              </p>
              <p className="text-xs text-muted-foreground">
                {row.ciclo_apto
                  ? `${row.ciclo_apto.parcelas_pagas}/${row.ciclo_apto.parcelas_total} parcela(s) quitadas`
                  : `${row.mensalidades.pagas}/${row.mensalidades.total} parcela(s) quitadas`}
              </p>
            </div>
          ),
        },
        {
          id: "financeiro",
          header: "Auxílio liberado / Repasse",
          cellClassName: "min-w-[15rem]",
          cell: (row) => (
            <div className="space-y-1">
              <p className="font-medium">
                Auxílio liberado: {formatCurrency(row.valor_auxilio_liberado)}
              </p>
              <p className="text-xs text-muted-foreground">
                Repasse: {formatCurrency(row.comissao_agente)} · {row.percentual_repasse}%
              </p>
            </div>
          ),
        },
      );

      if (canStartRenewal || canRequestLiquidation) {
      }

      columns.push({
        id: "acoes",
        header: "Ações",
        cellClassName: "min-w-[320px]",
        cell: (row) => (
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={() => setDetailAssociadoId(row.associado.id)}
            >
              Ver detalhes do associado
            </Button>
            {canStartRenewal ? (
              <Button size="sm" onClick={() => setSendTarget(row)}>
                <ClipboardCheckIcon className="size-4" />
                {row.status_renovacao === "pendente_termo_agente"
                  ? "Reenviar termo"
                  : "Enviar para renovação"}
              </Button>
            ) : null}
            {canRequestLiquidation ? (
              <Button size="sm" variant="outline" onClick={() => setLiquidacaoTarget(row)}>
                <HandCoinsIcon className="size-4" />
                Enviar para liquidação
              </Button>
            ) : null}
          </div>
        ),
      });

      return columns;
    },
    [canRequestLiquidation, canStartRenewal, canViewGlobalAptos],
  );

  const handleExport = React.useCallback(
    async (format: "csv" | "pdf" | "excel" | "xlsx") => {
      if (format !== "pdf" && format !== "xlsx") {
        return;
      }

      setIsExporting(true);
      try {
        if (tab === "historico") {
          await exportPaginatedRouteReport<RefinanciamentoItem>({
            route: "/agentes/refinanciados",
            format,
            sourcePath: "refinanciamentos",
            sourceQuery: {
              search: debouncedSearch || undefined,
              status: resolvedHistoryStatus,
              competencia_start: toCompetenciaDate(historyFilters.competenciaStart),
              competencia_end: toCompetenciaDate(historyFilters.competenciaEnd),
            },
            mapRow: (row) => ({
              contrato_codigo: row.contrato_codigo,
              associado_nome: row.associado_nome,
              status: row.status,
              data_solicitacao: row.data_solicitacao,
              valor_refinanciamento: row.valor_refinanciamento,
              repasse_agente: row.repasse_agente,
              analista_note: row.analista_note ?? "",
              coordenador_note: row.coordenador_note ?? "",
            }),
          });
        } else {
          await exportPaginatedRouteReport<ContratoListItem>({
            route: "/agentes/refinanciados",
            format,
            sourcePath: "contratos",
            sourceQuery: aptosQueryFilters,
            filters: {
              ...aptosQueryFilters,
              agente_label:
                aptosAgentOptions.find((agent) => agent.value === aptosFilters.agente)?.label ||
                undefined,
            },
            mapRow: (row) => ({
              contrato_codigo: row.codigo,
              associado_nome: row.associado.nome_completo,
              cpf_cnpj: row.associado.cpf_cnpj,
              matricula: row.associado.matricula_display || row.associado.matricula || "",
              agente_nome: row.agente?.full_name || "",
              status: row.status_renovacao,
              data_contrato: row.data_contrato,
              ciclo_apto: row.ciclo_apto?.numero ?? "",
              referencias_ciclo: row.ciclo_apto?.resumo_referencias || row.mensalidades.descricao,
              valor_refinanciamento: row.valor_auxilio_liberado,
              repasse_agente: row.comissao_agente,
            }),
          });
        }
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "Falha ao exportar renovações.");
      } finally {
        setIsExporting(false);
      }
    },
    [
      aptosAgentOptions,
      aptosFilters.agente,
      aptosQueryFilters,
      debouncedSearch,
      historyFilters.competenciaEnd,
      historyFilters.competenciaStart,
      resolvedHistoryStatus,
      tab,
    ],
  );

  return (
    <Tabs
      value={tab}
      onValueChange={(value) => {
        setTab(value as RefinanciadosTab);
        setPage(1);
      }}
      className="space-y-6"
    >
      <section className="rounded-[1.75rem] border border-border/60 bg-card/70 p-6 shadow-xl shadow-black/15">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-2">
            <h1 className="text-3xl font-semibold tracking-tight">
              Aptos a renovar
            </h1>
            <p className="max-w-3xl text-sm text-muted-foreground">
              {canViewGlobalAptos
                ? "Acompanhe as renovações do sistema e monitore os contratos aptos a renovar por toda a operação."
                : "O agente envia o termo de antecipação dos próprios contratos aptos para a fila do analista e acompanha o andamento até a tesouraria."}
            </p>
            <TabsList variant="line" className="w-fit">
              <TabsTrigger value="historico">Solicitações e histórico</TabsTrigger>
              <TabsTrigger value="aptos">Aptos a renovar</TabsTrigger>
            </TabsList>
          </div>
          <ExportButton
            disabled={isExporting}
            label={isExporting ? "Exportando..." : "Exportar"}
            onExport={(format) => void handleExport(format)}
          />
        </div>
      </section>

      <TabsContent value="historico" className="space-y-6">
        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {resumoQuery.isLoading && !resumoQuery.data ? (
            Array.from({ length: 4 }).map((_, index) => (
              <MetricCardSkeleton key={index} />
            ))
          ) : (
            <>
              <StatsCard
                title="Solicitações do agente"
                value={String(resumo.total)}
                delta={`${resumo.em_analise} em análise no recorte`}
                icon={RefreshCcwIcon}
                tone="neutral"
              />
              <StatsCard
                title="Em análise"
                value={String(resumo.em_analise)}
                delta={`${resumo.aprovados} validadas pela análise`}
                icon={ClipboardCheckIcon}
                tone="warning"
              />
              <StatsCard
                title="Aguardando coordenação"
                value={String(resumo.aprovados)}
                delta={`${resumo.efetivados} efetivadas pela tesouraria`}
                icon={BadgeCheckIcon}
                tone="positive"
              />
              <StatsCard
                title="Com termo do agente"
                value={String(resumo.com_anexo_agente)}
                delta="Anexo do agente disponível na solicitação"
                icon={PaperclipIcon}
                tone="neutral"
              />
            </>
          )}
        </section>

        <section className="grid gap-3 rounded-[1.75rem] border border-border/60 bg-card/50 p-4 xl:grid-cols-[minmax(0,1fr)_160px_auto_auto]">
          <Input
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
            placeholder="Buscar por nome, CPF, matrícula ou contrato..."
            className="rounded-2xl border-border/60 bg-card/60"
          />
          <PageSizeSelect
            value={pageSize}
            onValueChange={(value) => {
              setPageSize(value);
              setPage(1);
            }}
          />
          <Sheet open={historySheetOpen} onOpenChange={setHistorySheetOpen}>
            <SheetTrigger asChild>
              <Button variant="outline" className="rounded-2xl">
                <SlidersHorizontalIcon className="size-4" />
                Filtros avançados
                {activeHistoryFiltersCount > 0 ? (
                  <Badge className="ml-1 rounded-full bg-primary/15 px-2 py-0 text-[11px] text-primary">
                    {activeHistoryFiltersCount}
                  </Badge>
                ) : null}
              </Button>
            </SheetTrigger>
            <SheetContent className="w-full border-l border-border/60 bg-background/95 sm:max-w-lg">
              <SheetHeader>
                <SheetTitle>Filtros avançados</SheetTitle>
              </SheetHeader>
              <div className="mt-8 space-y-6">
                <div className="space-y-2">
                  <p className="text-sm font-medium text-foreground">Status</p>
                  <Select
                    value={draftHistoryFilters.status}
                    onValueChange={(value) =>
                      setDraftHistoryFilters((current) => ({
                        ...current,
                        status: value,
                      }))
                    }
                  >
                    <SelectTrigger className="rounded-2xl bg-card/60">
                      <SelectValue placeholder="Todos no fluxo" />
                    </SelectTrigger>
                    <SelectContent>
                      {HISTORY_STATUS_OPTIONS.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <p className="text-sm font-medium text-foreground">
                      Competência inicial
                    </p>
                    <CalendarCompetencia
                      value={parseMonthValue(draftHistoryFilters.competenciaStart)}
                      onChange={(value) =>
                        setDraftHistoryFilters((current) => ({
                          ...current,
                          competenciaStart: formatMonthValue(value),
                        }))
                      }
                    />
                  </div>
                  <div className="space-y-2">
                    <p className="text-sm font-medium text-foreground">
                      Competência final
                    </p>
                    <CalendarCompetencia
                      value={parseMonthValue(draftHistoryFilters.competenciaEnd)}
                      onChange={(value) =>
                        setDraftHistoryFilters((current) => ({
                          ...current,
                          competenciaEnd: formatMonthValue(value),
                        }))
                      }
                    />
                  </div>
                </div>
              </div>
              <SheetFooter className="mt-8 gap-3 sm:flex-col">
                <Button
                  variant="outline"
                  className="w-full rounded-2xl"
                  onClick={() => setDraftHistoryFilters(INITIAL_HISTORY_FILTERS)}
                >
                  Limpar filtros avançados
                </Button>
                <Button
                  className="w-full rounded-2xl"
                  onClick={() => {
                    setHistoryFilters(draftHistoryFilters);
                    setPage(1);
                    setHistorySheetOpen(false);
                  }}
                >
                  Aplicar filtros
                </Button>
              </SheetFooter>
            </SheetContent>
          </Sheet>
          <Button
            variant="outline"
            onClick={() => {
              setSearch("");
              setHistoryFilters(INITIAL_HISTORY_FILTERS);
              setDraftHistoryFilters(INITIAL_HISTORY_FILTERS);
              setPageSize("15");
              setPage(1);
            }}
          >
            Limpar
          </Button>
        </section>

        <DataTable
          data={refinanciadosRows}
          columns={refinanciadosColumns}
          currentPage={page}
          totalPages={Math.max(
            1,
            Math.ceil(
              (refinanciamentosQuery.data?.count ?? 0) / Number(pageSize),
            ),
          )}
          onPageChange={setPage}
          emptyMessage="Nenhuma solicitação de renovação encontrada."
          loading={refinanciamentosQuery.isLoading}
          skeletonRows={6}
        />
      </TabsContent>

      <TabsContent value="aptos" className="space-y-6">
        <section className="rounded-[1.75rem] border border-border/60 bg-card/60 p-5">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="space-y-1">
              <p className="text-sm font-medium text-foreground">
                Contratos aptos a renovar
              </p>
              <p className="text-sm text-muted-foreground">
                {aptosDescription}
              </p>
            </div>
            <StatsCard
              title="Aptos a renovar"
              value={String(aptosQuery.data?.count ?? 0)}
              delta={`${aptosRows.length} exibidos na página atual`}
              icon={WalletIcon}
              tone="neutral"
            />
          </div>
        </section>

        <section className="grid gap-3 rounded-[1.75rem] border border-border/60 bg-card/50 p-4 xl:grid-cols-[minmax(0,1fr)_160px_auto_auto]">
          <Input
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
            placeholder="Buscar por nome, CPF, matrícula ou contrato..."
            className="rounded-2xl border-border/60 bg-card/60"
          />
          <PageSizeSelect
            value={pageSize}
            onValueChange={(value) => {
              setPageSize(value);
              setPage(1);
            }}
          />
          <Sheet open={aptosSheetOpen} onOpenChange={setAptosSheetOpen}>
            <SheetTrigger asChild>
              <Button variant="outline" className="rounded-2xl">
                <SlidersHorizontalIcon className="size-4" />
                Filtros avançados
                {activeAptosFiltersCount > 0 ? (
                  <Badge className="ml-1 rounded-full bg-primary/15 px-2 py-0 text-[11px] text-primary">
                    {activeAptosFiltersCount}
                  </Badge>
                ) : null}
              </Button>
            </SheetTrigger>
            <SheetContent className="w-full border-l border-border/60 bg-background/95 sm:max-w-lg">
              <SheetHeader>
                <SheetTitle>Filtros avançados</SheetTitle>
              </SheetHeader>
              <div className="mt-8 space-y-6">
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <p className="text-sm font-medium text-foreground">
                      Data inicial do contrato
                    </p>
                    <DatePicker
                      value={parseDateValue(draftAptosFilters.dataInicio)}
                      onChange={(value) =>
                        setDraftAptosFilters((current) => ({
                          ...current,
                          dataInicio: formatDateValue(value),
                        }))
                      }
                      className="rounded-2xl"
                    />
                  </div>
                  <div className="space-y-2">
                    <p className="text-sm font-medium text-foreground">
                      Data final do contrato
                    </p>
                    <DatePicker
                      value={parseDateValue(draftAptosFilters.dataFim)}
                      onChange={(value) =>
                        setDraftAptosFilters((current) => ({
                          ...current,
                          dataFim: formatDateValue(value),
                        }))
                      }
                      className="rounded-2xl"
                    />
                  </div>
                </div>

                {canViewGlobalAptos ? (
                  <div className="space-y-2">
                    <p className="text-sm font-medium text-foreground">
                      Agente responsável
                    </p>
                    <SearchableSelect
                      options={aptosAgentOptions}
                      value={draftAptosFilters.agente}
                      onChange={(value) =>
                        setDraftAptosFilters((current) => ({
                          ...current,
                          agente: value,
                        }))
                      }
                      placeholder={
                        aptosAgentQuery.isLoading
                          ? "Carregando agentes..."
                          : "Todos os agentes"
                      }
                      searchPlaceholder="Buscar agente..."
                      clearLabel="Todos os agentes"
                    />
                  </div>
                ) : null}
              </div>
              <SheetFooter className="mt-8 gap-3 sm:flex-col">
                <Button
                  variant="outline"
                  className="w-full rounded-2xl"
                  onClick={() => setDraftAptosFilters(INITIAL_APTOS_FILTERS)}
                >
                  Limpar filtros avançados
                </Button>
                <Button
                  className="w-full rounded-2xl"
                  onClick={() => {
                    setAptosFilters(draftAptosFilters);
                    setPage(1);
                    setAptosSheetOpen(false);
                  }}
                >
                  Aplicar filtros
                </Button>
              </SheetFooter>
            </SheetContent>
          </Sheet>
          <Button
            variant="outline"
            onClick={() => {
              setSearch("");
              setAptosFilters(INITIAL_APTOS_FILTERS);
              setDraftAptosFilters(INITIAL_APTOS_FILTERS);
              setPageSize("15");
              setPage(1);
            }}
          >
            Limpar
          </Button>
        </section>

        <DataTable
          data={aptosRows}
          columns={aptosColumns}
          currentPage={page}
          totalPages={Math.max(
            1,
            Math.ceil((aptosQuery.data?.count ?? 0) / Number(pageSize)),
          )}
          onPageChange={setPage}
          emptyMessage="Nenhum contrato apto a renovar encontrado."
          loading={aptosQuery.isLoading}
          skeletonRows={6}
        />
      </TabsContent>

      <Dialog
        open={!!sendTarget}
        onOpenChange={(open) => {
          if (!open) {
            setSendTarget(null);
            setTermo(null);
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Enviar renovação</DialogTitle>
            <DialogDescription>
              {sendTarget
                ? `${sendTarget.associado.nome_completo} · ${sendTarget.codigo}`
                : "Anexe o termo de antecipação para encaminhar a renovação ao analista."}
              {sendTarget?.status_renovacao === "pendente_termo_agente"
                ? " Reenvie o termo solicitado pelo analista no mesmo refinanciamento."
                : ""}
            </DialogDescription>
          </DialogHeader>
          <FileUploadDropzone
            accept={TERMO_ACCEPT}
            file={termo}
            onUpload={setTermo}
            emptyTitle="Selecione o termo de antecipação"
          />
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setSendTarget(null);
                setTermo(null);
              }}
            >
              Cancelar
            </Button>
            <Button
              disabled={!sendTarget || !termo || solicitarMutation.isPending}
              onClick={() => {
                if (!sendTarget || !termo) return;
                solicitarMutation.mutate({
                  contratoId: sendTarget.id,
                  file: termo,
                });
              }}
            >
              {sendTarget?.status_renovacao === "pendente_termo_agente"
                ? "Reenviar termo"
                : "Enviar para renovação"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={!!liquidacaoTarget}
        onOpenChange={(open) => {
          if (!open) {
            setLiquidacaoTarget(null);
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Enviar para liquidação</DialogTitle>
            <DialogDescription>
              {liquidacaoTarget
                ? `${liquidacaoTarget.associado.nome_completo} · ${liquidacaoTarget.codigo}`
                : "A solicitação será encaminhada para a tesouraria tratar a liquidação do contrato."}
            </DialogDescription>
          </DialogHeader>
          <div className="rounded-2xl border border-border/60 bg-card/50 p-4 text-sm text-muted-foreground">
            Esta ação remove o contrato da lista de aptos a renovar e registra no histórico do agente
            que o caso deve seguir para liquidação.
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setLiquidacaoTarget(null);
              }}
            >
              Cancelar
            </Button>
            <Button
              variant="outline"
              disabled={!liquidacaoTarget || solicitarLiquidacaoMutation.isPending}
              onClick={() => {
                if (!liquidacaoTarget) return;
                solicitarLiquidacaoMutation.mutate({
                  contratoId: liquidacaoTarget.id,
                });
              }}
            >
              Enviar para liquidação
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AssociadoDetailsDialog
        associadoId={detailAssociadoId}
        open={detailAssociadoId != null}
        onOpenChange={(open) => {
          if (!open) {
            setDetailAssociadoId(null);
          }
        }}
        description="Consulta expandida do associado, contratos e ciclos sem sair da fila de aptos a renovar."
      />
    </Tabs>
  );
}

function AssociadoSummary({
  nome,
  cpf,
  matricula,
}: {
  nome: string;
  cpf: string;
  matricula: string;
}) {
  return (
    <div className="space-y-1.5">
      <p className="font-semibold leading-tight text-foreground">{nome}</p>
      <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
        <span>{maskCPFCNPJ(cpf)}</span>
        <span>Mat.: {matricula || "N/I"}</span>
      </div>
    </div>
  );
}

function CycleSignature({ cicloKey }: { cicloKey: string }) {
  const parts = cicloKey
    .split("|")
    .map((value) => value.trim())
    .filter(Boolean);

  if (!parts.length) {
    return <span className="text-sm text-muted-foreground">Sem ciclo definido</span>;
  }

  return (
    <div className="flex flex-wrap gap-2">
      {parts.map((part) => (
        <Badge
          key={part}
          variant="outline"
          className="rounded-full border-border/60 bg-background/40 font-mono text-[11px]"
        >
          {part}
        </Badge>
      ))}
    </div>
  );
}

function ReferenceList({ referencias }: { referencias: string[] }) {
  if (!referencias.length) {
    return <span className="text-sm text-muted-foreground">Sem referências</span>;
  }

  return (
    <div className="flex flex-wrap gap-2">
      {referencias.map((referencia) => (
        <Badge
          key={referencia}
          className="rounded-full bg-sky-500/15 text-sky-200"
        >
          {formatMonthYear(referencia)}
        </Badge>
      ))}
    </div>
  );
}

function RenovacaoSummary({ row }: { row: RefinanciamentoItem }) {
  const activationDate =
    row.data_ativacao_ciclo ||
    row.executado_em ||
    row.reviewed_at ||
    row.data_solicitacao_renovacao ||
    row.created_at;
  const helperLabel = row.data_ativacao_ciclo
    ? "Ciclo ativado"
    : row.executado_em
      ? "Efetivado na tesouraria"
      : row.status === "solicitado_para_liquidacao"
        ? "Solicitada para liquidação"
      : row.status === "aprovado_para_renovacao"
        ? "Aguardando tesouraria"
        : row.status === "aprovado_analise_renovacao"
          ? "Aprovado na análise"
          : "Enviado para análise";

  if (!activationDate) {
    return <span className="text-sm text-muted-foreground">N/I</span>;
  }

  return (
    <div className="space-y-1.5">
      <p className="text-sm font-medium">{formatDateTime(activationDate, "N/I")}</p>
      <div className="flex flex-wrap gap-2">
        <Badge className="rounded-full bg-emerald-500/15 text-emerald-200">
          {helperLabel}
        </Badge>
        {row.ativacao_inferida ? (
          <Badge className="rounded-full bg-amber-500/15 text-amber-200">
            Inferido
          </Badge>
        ) : null}
      </div>
    </div>
  );
}

function AgentAttachmentList({
  comprovantes,
}: {
  comprovantes: RefinanciamentoItem["comprovantes"];
}) {
  if (!comprovantes.length) {
    return (
      <span className="text-sm text-muted-foreground">
        Sem anexo do agente.
      </span>
    );
  }

  return (
    <div className="flex flex-wrap gap-2">
      {comprovantes.map((comprovante) =>
        comprovante.arquivo_disponivel_localmente ? (
          <Button key={comprovante.id} size="sm" variant="outline" asChild>
            <a
              href={buildBackendFileUrl(comprovante.arquivo)}
              target="_blank"
              rel="noreferrer"
            >
              {comprovante.nome_original || "Abrir anexo"}
            </a>
          </Button>
        ) : (
          <span
            key={comprovante.id}
            className="inline-flex items-center rounded-full border border-dashed border-border/60 px-3 py-1 text-xs text-muted-foreground"
            title={comprovante.arquivo_referencia}
          >
            Referência legado
          </span>
        ),
      )}
    </div>
  );
}

function PageSizeSelect({
  value,
  onValueChange,
}: {
  value: string;
  onValueChange: (value: string) => void;
}) {
  return (
    <Select value={value} onValueChange={onValueChange}>
      <SelectTrigger className="rounded-2xl bg-card/60">
        <SelectValue placeholder="15" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="15">15 / página</SelectItem>
        <SelectItem value="30">30 / página</SelectItem>
        <SelectItem value="50">50 / página</SelectItem>
      </SelectContent>
    </Select>
  );
}
