"use client";

import * as React from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { format, parseISO } from "date-fns";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CalendarCheck2Icon,
  ChevronRightIcon,
  HandCoinsIcon,
  ReceiptTextIcon,
  RotateCcwIcon,
  SlidersHorizontalIcon,
  Trash2Icon,
  WalletCardsIcon,
} from "lucide-react";
import { toast } from "sonner";

import type {
  LiquidacaoContratoItem,
  LiquidacaoKpis,
  PaginatedResponse,
  SimpleUser,
} from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import { buildBackendFileUrl } from "@/lib/backend-files";
import {
  dashboardOptionsQueryOptions,
  dashboardRetainedQueryOptions,
} from "@/lib/dashboard-query";
import { usePermissions } from "@/hooks/use-permissions";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { formatCurrency, formatDate, formatMonthYear } from "@/lib/formatters";
import {
  describeReportScope,
  exportRouteReport,
  fetchAllPaginatedRows,
  filterRowsByReportScope,
} from "@/lib/reports";
import DatePicker from "@/components/custom/date-picker";
import FileUploadDropzone from "@/components/custom/file-upload-dropzone";
import InputCurrency from "@/components/custom/input-currency";
import SearchableSelect from "@/components/custom/searchable-select";
import StatusBadge from "@/components/custom/status-badge";
import CopySnippet from "@/components/shared/copy-snippet";
import DataTable, { type DataTableColumn } from "@/components/shared/data-table";
import ReportExportDialog, {
  type ReportExportFilters,
} from "@/components/shared/report-export-dialog";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";

type ListingStatus = "elegivel" | "liquidado";
type LiquidacaoResponse = PaginatedResponse<LiquidacaoContratoItem> & {
  kpis: LiquidacaoKpis;
};

type LiquidarState = {
  row: LiquidacaoContratoItem;
  comprovantes: File[];
  dataLiquidacao: string;
  valorTotal: string;
  origemSolicitacao: string;
  observacao: string;
};

const ORIGEM_SOLICITACAO_OPTIONS = [
  { value: "agente", label: "Agente" },
  { value: "coordenacao", label: "Coordenação" },
  { value: "administracao", label: "Administração" },
  { value: "renovacao", label: "Renovação" },
] as const;

const ASSOCIADO_STATUS_OPTIONS = [
  { value: "todos", label: "Todos os status" },
  { value: "ciclo_aberto", label: "Ativo" },
  { value: "apto_a_renovar", label: "Apto para Renovação" },
  { value: "solicitado_para_liquidacao", label: "Solicitado para Liquidação" },
  { value: "renovacao_em_analise", label: "Renovação em Análise" },
  { value: "aguardando_coordenacao", label: "Aguardando Coordenação" },
  { value: "aprovado_para_renovacao", label: "Aguardando Pagamento" },
  { value: "ciclo_renovado", label: "Concluído" },
  { value: "em_analise", label: "Em Análise" },
  { value: "contrato_desativado", label: "Contrato Desativado" },
  { value: "contrato_encerrado", label: "Contrato Encerrado" },
] as const;

const ETAPA_FLUXO_OPTIONS = [
  { value: "todas", label: "Todas as etapas" },
  { value: "cadastro", label: "Cadastro" },
  { value: "analise", label: "Análise" },
  { value: "coordenacao", label: "Coordenação" },
  { value: "tesouraria", label: "Tesouraria" },
  { value: "concluido", label: "Concluído" },
] as const;

const ELIGIBLE_PARCELA_STATUSES = new Set([
  "futuro",
  "em_previsao",
  "em_aberto",
  "nao_descontado",
]);

function isRenewalOrigin(row: LiquidacaoContratoItem) {
  return row.origem_solicitacao === "renovacao";
}

function getOrigemSolicitacaoLabel(origem: string) {
  return ORIGEM_SOLICITACAO_OPTIONS.find((option) => option.value === origem)?.label ?? origem;
}

function isEligibleParcelaStatus(status: string) {
  return ELIGIBLE_PARCELA_STATUSES.has(status);
}

function parseApiDateValue(value: string) {
  return value ? parseISO(value) : undefined;
}

function parseDecimalToCents(value: string) {
  const parsed = Number.parseFloat(value);
  if (!Number.isFinite(parsed)) {
    return null;
  }
  return Math.round(parsed * 100);
}

function getOperationalStatusDescription(row: LiquidacaoContratoItem) {
  if (row.data_liquidacao) {
    return `Em ${formatDate(row.data_liquidacao)}`;
  }
  if (row.pode_liquidar_agora && row.quantidade_parcelas === 0) {
    return "Pronto para inativação imediata, sem baixa de parcelas.";
  }
  if (row.pode_liquidar_agora) {
    return "Pronto para liquidação imediata.";
  }
  if (row.status_operacional === "sem_contrato") {
    return "Associado sem contrato operacional vinculado.";
  }
  return "Sem parcelas aptas para liquidação neste momento.";
}

function getLiquidarButtonTitle(row: LiquidacaoContratoItem) {
  if (row.pode_liquidar_agora && row.contrato_id != null) {
    return row.quantidade_parcelas === 0
      ? "Confirmar inativação do contrato"
      : "Confirmar liquidação";
  }
  if (row.status_operacional === "sem_contrato") {
    return "Associado sem contrato operacional vinculado";
  }
  return "Associado sem parcelas elegíveis no momento";
}

const comprovanteAccept = {
  "application/pdf": [".pdf"],
  "image/png": [".png"],
  "image/jpeg": [".jpg", ".jpeg"],
};

function useLiquidacoesQuery({
  page,
  tab,
  search,
  agente,
  statusAssociado,
  etapaFluxo,
  dataInicio,
  dataFim,
  estado,
  contractId,
}: {
  page: number;
  tab: ListingStatus;
  search: string;
  agente: string;
  statusAssociado: string;
  etapaFluxo: string;
  dataInicio?: Date;
  dataFim?: Date;
  estado: string;
  contractId?: number;
}) {
  return useQuery({
    queryKey: [
      "tesouraria-liquidacoes",
      tab,
      page,
      search,
      agente,
      statusAssociado,
      etapaFluxo,
      dataInicio?.toISOString(),
      dataFim?.toISOString(),
      estado,
      contractId,
    ],
    queryFn: () =>
      apiFetch<LiquidacaoResponse>("tesouraria/liquidacoes", {
        query: {
          page,
          page_size: 20,
          status: tab,
          search: search || undefined,
          agente: agente || undefined,
          status_associado:
            statusAssociado !== "todos" ? statusAssociado : undefined,
          etapa_fluxo: etapaFluxo !== "todas" ? etapaFluxo : undefined,
          data_inicio: dataInicio ? format(dataInicio, "yyyy-MM-dd") : undefined,
          data_fim: dataFim ? format(dataFim, "yyyy-MM-dd") : undefined,
          estado: tab === "liquidado" && estado !== "todos" ? estado : undefined,
          contract_id: contractId,
        },
      }),
    ...dashboardRetainedQueryOptions,
  });
}

export default function LiquidacoesTesourariaPage() {
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const { hasRole } = usePermissions();
  const isAdmin = hasRole("ADMIN");
  const contractId = React.useMemo(() => {
    const value = searchParams.get("contrato");
    const parsed = Number(value);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : undefined;
  }, [searchParams]);
  const origem = searchParams.get("origem");
  const refinanciamentoId = searchParams.get("refinanciamento");
  const initialTab = searchParams.get("status") === "liquidado" ? "liquidado" : "elegivel";
  const [tab, setTab] = React.useState<ListingStatus>(initialTab);
  const [page, setPage] = React.useState(1);
  const [search, setSearch] = React.useState("");
  const [agente, setAgente] = React.useState("");
  const [statusAssociado, setStatusAssociado] = React.useState("todos");
  const [etapaFluxo, setEtapaFluxo] = React.useState("todas");
  const [dataInicio, setDataInicio] = React.useState<Date | undefined>();
  const [dataFim, setDataFim] = React.useState<Date | undefined>();
  const [estado, setEstado] = React.useState("todos");
  const [filtersOpen, setFiltersOpen] = React.useState(false);
  const [draftAgente, setDraftAgente] = React.useState("");
  const [draftStatusAssociado, setDraftStatusAssociado] = React.useState("todos");
  const [draftEtapaFluxo, setDraftEtapaFluxo] = React.useState("todas");
  const [draftDataInicio, setDraftDataInicio] = React.useState<Date | undefined>();
  const [draftDataFim, setDraftDataFim] = React.useState<Date | undefined>();
  const [draftEstado, setDraftEstado] = React.useState("todos");
  const [isExporting, setIsExporting] = React.useState(false);
  const [liquidarState, setLiquidarState] = React.useState<LiquidarState | null>(null);
  const [reverterTarget, setReverterTarget] = React.useState<LiquidacaoContratoItem | null>(null);
  const [motivoReversao, setMotivoReversao] = React.useState("");
  const [deleteTarget, setDeleteTarget] = React.useState<LiquidacaoContratoItem | null>(null);
  const [motivoExclusao, setMotivoExclusao] = React.useState("");
  const debouncedSearch = useDebouncedValue(search, 300);

  const agentesQuery = useQuery({
    queryKey: ["liquidacoes-agentes"],
    queryFn: () => apiFetch<SimpleUser[]>("associados/agentes"),
    ...dashboardOptionsQueryOptions,
  });

  const agentOptions = React.useMemo(
    () =>
      (agentesQuery.data ?? []).map((item) => ({
        value: String(item.id),
        label: item.full_name,
      })),
    [agentesQuery.data],
  );

  const agenteFiltro = React.useMemo(() => {
    if (!agente) {
      return "";
    }
    const match = (agentesQuery.data ?? []).find((item) => String(item.id) === agente);
    return match?.full_name ?? agente;
  }, [agente, agentesQuery.data]);

  React.useEffect(() => {
    setPage(1);
  }, [tab, debouncedSearch, agenteFiltro, statusAssociado, etapaFluxo, dataInicio, dataFim, estado]);

  const query = useLiquidacoesQuery({
    page,
    tab,
    search: debouncedSearch,
    agente: agenteFiltro,
    statusAssociado,
    etapaFluxo,
    dataInicio,
    dataFim,
    estado,
    contractId,
  });

  const handleExport = React.useCallback(
    async (exportFilters: ReportExportFilters, formatValue: "pdf" | "xlsx") => {
      const { scope, referenceDate } = exportFilters;
      setIsExporting(true);
      try {
        const sourceQuery = {
          status: tab,
          search: debouncedSearch || undefined,
          agente: agenteFiltro || undefined,
          status_associado: statusAssociado !== "todos" ? statusAssociado : undefined,
          etapa_fluxo: etapaFluxo !== "todas" ? etapaFluxo : undefined,
          data_inicio: dataInicio ? format(dataInicio, "yyyy-MM-dd") : undefined,
          data_fim: dataFim ? format(dataFim, "yyyy-MM-dd") : undefined,
          estado: tab === "liquidado" && estado !== "todos" ? estado : undefined,
          contract_id: contractId,
        };
        const fetchedRows = await fetchAllPaginatedRows<LiquidacaoContratoItem>({
          sourcePath: "tesouraria/liquidacoes",
          sourceQuery,
        });
        const rows = filterRowsByReportScope({
          rows: fetchedRows,
          scope,
          referenceDate,
          getCandidates: (row) => [row.data_liquidacao, row.referencia_inicial, row.referencia_final],
        }).map((row) => ({
          nome: row.nome,
          cpf_cnpj: row.cpf_cnpj,
          matricula: row.matricula,
          agente_nome: row.agente_nome,
          contrato_codigo: row.contrato_codigo,
          quantidade_parcelas: row.quantidade_parcelas,
          valor_total: row.valor_total,
          referencia_inicial: row.referencia_inicial ?? "",
          referencia_final: row.referencia_final ?? "",
          status_liquidacao: row.status_liquidacao,
          status_operacional: row.status_operacional,
          status_associado: row.status_associado_label,
          origem_solicitacao: row.origem_solicitacao,
          data_liquidacao: row.data_liquidacao ?? "",
          observacao: row.observacao,
        }));

        await exportRouteReport({
          route: "/tesouraria/liquidacoes",
          format: formatValue,
          rows,
          filters: {
            ...sourceQuery,
            ...describeReportScope(scope, referenceDate),
          },
        });
      } catch (error) {
        toast.error(
          error instanceof Error ? error.message : "Falha ao exportar liquidações.",
        );
      } finally {
        setIsExporting(false);
      }
    },
    [
      agenteFiltro,
      contractId,
      dataFim,
      dataInicio,
      debouncedSearch,
      estado,
      etapaFluxo,
      statusAssociado,
      tab,
    ],
  );

  const liquidarMutation = useMutation({
    mutationFn: async (payload: LiquidarState) => {
      if (payload.row.contrato_id == null) {
        throw new Error("O associado não possui contrato operacional para liquidação.");
      }
      const formData = new FormData();
      payload.comprovantes.forEach((arquivo) => {
        formData.append("comprovantes", arquivo);
      });
      formData.append("data_liquidacao", payload.dataLiquidacao);
      formData.append("valor_total", payload.valorTotal);
      formData.append("origem_solicitacao", payload.origemSolicitacao);
      formData.append("observacao", payload.observacao);
      return apiFetch<LiquidacaoContratoItem>(
        `tesouraria/liquidacoes/${payload.row.contrato_id}/liquidar`,
        {
          method: "POST",
          formData,
        },
      );
    },
    onSuccess: () => {
      toast.success("Liquidação registrada com sucesso.");
      setLiquidarState(null);
      void queryClient.invalidateQueries({ queryKey: ["tesouraria-liquidacoes"] });
      void queryClient.invalidateQueries({ queryKey: ["associados"] });
      void queryClient.invalidateQueries({ queryKey: ["contratos"] });
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Não foi possível liquidar o contrato.");
    },
  });

  const reverterMutation = useMutation({
    mutationFn: async ({
      contratoId,
      motivo,
    }: {
      contratoId: number;
      motivo: string;
    }) =>
      apiFetch<LiquidacaoContratoItem>(`tesouraria/liquidacoes/${contratoId}/reverter`, {
        method: "POST",
        body: { motivo_reversao: motivo },
      }),
    onSuccess: () => {
      toast.success("Liquidação revertida com sucesso.");
      setReverterTarget(null);
      setMotivoReversao("");
      void queryClient.invalidateQueries({ queryKey: ["tesouraria-liquidacoes"] });
      void queryClient.invalidateQueries({ queryKey: ["associados"] });
      void queryClient.invalidateQueries({ queryKey: ["contratos"] });
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Não foi possível reverter a liquidação.");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async ({ liquidacaoId, motivo }: { liquidacaoId: number; motivo: string }) =>
      apiFetch<{ message: string }>(`tesouraria/liquidacoes/${liquidacaoId}/excluir`, {
        method: "POST",
        body: { motivo_exclusao: motivo },
      }),
    onSuccess: () => {
      toast.success("Registro de liquidação excluído com sucesso.");
      setDeleteTarget(null);
      setMotivoExclusao("");
      void queryClient.invalidateQueries({ queryKey: ["tesouraria-liquidacoes"] });
      void queryClient.invalidateQueries({ queryKey: ["associados"] });
      void queryClient.invalidateQueries({ queryKey: ["contratos"] });
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Não foi possível excluir a liquidação.");
    },
  });

  const rows = query.data?.results ?? [];
  const kpis = query.data?.kpis;
  const totalCount = query.data?.count ?? 0;
  const activeFiltersCount =
    Number(Boolean(agente.trim())) +
    Number(statusAssociado !== "todos") +
    Number(etapaFluxo !== "todas") +
    Number(Boolean(dataInicio)) +
    Number(Boolean(dataFim)) +
    Number(tab === "liquidado" && estado !== "todos");
  const liquidacaoParcelas = React.useMemo(
    () =>
      liquidarState
        ? liquidarState.row.parcelas.filter((parcela) => isEligibleParcelaStatus(parcela.status))
        : [],
    [liquidarState],
  );

  const columns = React.useMemo<DataTableColumn<LiquidacaoContratoItem>[]>(
    () => [
      {
        id: "expand",
        header: "",
        headerClassName: "w-8 px-3",
        cellClassName: "w-8 px-3",
        cell: () => (
          <ChevronRightIcon className="size-4 text-muted-foreground transition-transform duration-200 group-data-[expanded=true]:rotate-90" />
        ),
      },
      {
        id: "associado",
        header: "Associado",
        cell: (row) => (
          <div className="space-y-3">
            <p className="font-medium">{row.nome}</p>
            <div className="flex flex-wrap gap-2">
              <CopySnippet label="CPF" value={row.cpf_cnpj} mono />
              <CopySnippet label="Matric." value={row.matricula} mono />
            </div>
          </div>
        ),
      },
      {
        id: "agente",
        header: "Agente",
        cell: (row) => (
          <span className="text-sm font-medium text-muted-foreground">
            {row.agente_nome || "Sem agente"}
          </span>
        ),
      },
      {
        id: "referencias",
        header: tab === "elegivel" ? "Parcelas / Referências" : "Parcelas Liquidadas",
        cell: (row) => (
          <div>
            <p className="font-medium">
              {tab === "elegivel" && row.pode_liquidar_agora && row.quantidade_parcelas === 0
                ? "Encerramento sem parcelas pendentes"
                : `${row.quantidade_parcelas} parcela(s)${
                    tab === "elegivel" ? " elegível(is) agora" : " registrada(s)"
                  }`}
            </p>
            <p className="text-xs text-muted-foreground">
              {row.referencia_inicial && row.referencia_final
                ? `${formatMonthYear(row.referencia_inicial)} até ${formatMonthYear(row.referencia_final)}`
                : row.pode_liquidar_agora && row.quantidade_parcelas === 0
                  ? "Nenhuma parcela em aberto para quitar."
                  : "Sem referências"}
            </p>
            <p className="text-xs text-muted-foreground">
              {row.quantidade_parcelas_contrato} parcela(s) no contrato
            </p>
          </div>
        ),
      },
      {
        id: "valor_total",
        header: tab === "elegivel" ? "Valor Potencial" : "Valor Liquidado",
        cell: (row) => <span className="font-semibold">{formatCurrency(row.valor_total)}</span>,
      },
      {
        id: "status_associado",
        header: "Status do Associado",
        cell: (row) => (
          <StatusBadge
            status={row.status_associado}
            label={row.status_associado_label || undefined}
          />
        ),
      },
      {
        id: "status",
        header: tab === "elegivel" ? "Situação da Liquidação" : "Situação",
        cell: (row) => (
          <div className="space-y-2">
            <StatusBadge
              status={tab === "elegivel" ? row.status_operacional : row.status_liquidacao}
            />
            {isRenewalOrigin(row) ? (
              <StatusBadge
                status="solicitado_para_liquidacao"
                label="Solicitado via renovação"
              />
            ) : null}
            {row.data_liquidacao ? (
              <p className="text-xs text-muted-foreground">
                {getOperationalStatusDescription(row)}
              </p>
            ) : tab === "elegivel" ? (
              <p className="text-xs text-muted-foreground">
                {getOperationalStatusDescription(row)}
              </p>
            ) : (
              <p className="text-xs text-muted-foreground">Liquidação registrada no histórico.</p>
            )}
          </div>
        ),
      },
      {
        id: "acoes",
        header: "Ações",
        cellClassName: "w-[320px]",
        cell: (row) => (
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="outline">
              <Link
                href={`/associados/${row.associado_id}`}
                onClick={(event) => event.stopPropagation()}
              >
                Ver cadastro
              </Link>
            </Button>
            {tab === "elegivel" ? (
              <Button
                size="sm"
                variant="success"
                disabled={!row.pode_liquidar_agora || row.contrato_id == null}
                onClick={(event) => {
                  event.stopPropagation();
                  if (!row.pode_liquidar_agora || row.contrato_id == null) {
                    return;
                  }
                  setLiquidarState({
                    row,
                    comprovantes: [],
                    dataLiquidacao: format(new Date(), "yyyy-MM-dd"),
                    valorTotal: row.valor_total,
                    origemSolicitacao: isRenewalOrigin(row) ? "renovacao" : "",
                    observacao: "",
                  });
                }}
                title={getLiquidarButtonTitle(row)}
              >
                Liquidar
              </Button>
            ) : null}
            {tab === "liquidado" && isAdmin && row.pode_reverter ? (
              <Button
                size="sm"
                variant="outline"
                onClick={(event) => {
                  event.stopPropagation();
                  setReverterTarget(row);
                }}
              >
                <RotateCcwIcon className="mr-1.5 size-3.5" />
                Reverter
              </Button>
            ) : null}
            {tab === "liquidado" && isAdmin && row.liquidacao_id ? (
              <Button
                size="sm"
                variant="destructive"
                onClick={(event) => {
                  event.stopPropagation();
                  setDeleteTarget(row);
                  setMotivoExclusao("");
                }}
              >
                <Trash2Icon className="mr-1.5 size-3.5" />
                Excluir
              </Button>
            ) : null}
          </div>
        ),
      },
    ],
    [isAdmin, tab],
  );

  const renderExpanded = React.useCallback(
    (row: LiquidacaoContratoItem) => (
      <div className="space-y-3">
        <div className="space-y-1">
          <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
            {tab === "elegivel" ? "Parcelas do contrato operacional" : "Parcelas liquidadas"} —{" "}
            {row.nome}
          </p>
          <p className="text-sm text-muted-foreground">
            {tab === "elegivel"
              ? row.contrato_codigo
                ? row.pode_liquidar_agora && row.quantidade_parcelas === 0
                  ? `${row.contrato_codigo} · contrato apto para encerramento direto sem baixa de parcelas.`
                  : `${row.contrato_codigo} · ${row.quantidade_parcelas} elegível(is) agora de ${row.quantidade_parcelas_contrato} parcela(s) do contrato.`
                : "Associado sem contrato operacional vinculado."
              : `${row.contrato_codigo} · ${row.quantidade_parcelas} parcela(s) registradas nesta liquidação.`}
          </p>
        </div>
        {row.parcelas.length ? (
          <div className="overflow-hidden rounded-xl border border-border/60">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/60 bg-muted/20">
                  <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Parcela
                  </th>
                  <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Referência
                  </th>
                  <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Vencimento
                  </th>
                  <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Valor
                  </th>
                  <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Status
                  </th>
                  <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Pagamento
                  </th>
                </tr>
              </thead>
              <tbody>
                {row.parcelas.map((parcela) => (
                  <tr
                    key={`${row.contrato_id ?? row.id}-${parcela.id}-${parcela.referencia_mes}`}
                    className="border-b border-border/40 transition-colors last:border-0 hover:bg-white/3"
                  >
                    <td className="px-4 py-3 font-medium">Parcela {parcela.numero}</td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {formatMonthYear(parcela.referencia_mes)}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {formatDate(parcela.data_vencimento)}
                    </td>
                    <td className="px-4 py-3 font-semibold">
                      {formatCurrency(parcela.valor)}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={parcela.status} />
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {parcela.data_pagamento ? formatDate(parcela.data_pagamento) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="rounded-2xl border border-border/60 bg-background/50 p-4 text-sm text-muted-foreground">
            {row.contrato_codigo
              ? "Nenhuma parcela foi encontrada para este contrato."
              : "Nenhum contrato operacional foi encontrado para este associado."}
          </div>
        )}
        {row.origem_solicitacao ? (
          <div className="rounded-2xl border border-border/60 bg-background/50 p-4 text-sm">
            <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
              Origem da solicitação
            </p>
            <p className="mt-2 font-medium">{getOrigemSolicitacaoLabel(row.origem_solicitacao)}</p>
          </div>
        ) : null}
        {row.anexos.length ? (
          <div className="rounded-2xl border border-border/60 bg-background/50 p-4 text-sm">
            <p className="font-medium">Comprovantes da liquidação</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {row.anexos.map((anexo) => (
                <Button
                  key={`${row.id}-${anexo.arquivo_referencia}-${anexo.nome}`}
                  asChild
                  size="sm"
                  variant="outline"
                >
                  <a href={buildBackendFileUrl(anexo.url)} target="_blank" rel="noreferrer">
                    {anexo.nome}
                  </a>
                </Button>
              ))}
            </div>
          </div>
        ) : null}
        {row.observacao ? (
          <div className="rounded-2xl border border-border/60 bg-background/50 p-4 text-sm text-muted-foreground">
            {row.observacao}
          </div>
        ) : null}
      </div>
    ),
    [tab],
  );

  return (
    <div className="space-y-6">
      <section className="rounded-[1.75rem] border border-border/60 bg-card/70 p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-1">
            <h1 className="text-3xl font-semibold">Liquidação</h1>
            <p className="text-sm text-muted-foreground">
              Acompanhe todos os associados e registre liquidações pela tesouraria com comprovante,
              trilha financeira e reversão administrativa controlada.
            </p>
          </div>
          <ReportExportDialog
            disabled={isExporting}
            label={isExporting ? "Exportando..." : "Exportar"}
            onExport={handleExport}
          />
        </div>
      </section>

      {origem === "renovacao" ? (
        <section className="rounded-[1.5rem] border border-amber-500/30 bg-amber-500/10 p-4">
          <p className="text-sm text-amber-100">
            Solicitação aberta a partir do fluxo de renovação.
            {contractId ? ` Contrato pré-selecionado: ${contractId}.` : ""}
            {refinanciamentoId ? ` Refinanciamento de origem: ${refinanciamentoId}.` : ""}
          </p>
        </section>
      ) : null}

      <Tabs value={tab} onValueChange={(value) => setTab(value as ListingStatus)}>
        <TabsList variant="line" className="justify-start">
          <TabsTrigger value="elegivel">Fila</TabsTrigger>
          <TabsTrigger value="liquidado">Liquidados</TabsTrigger>
        </TabsList>

        <TabsContent value={tab} className="space-y-6">
          <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {tab === "elegivel" ? (
              <>
                <StatsCard
                  title="Total na Fila"
                  value={String(kpis?.total_contratos ?? "0")}
                  delta="associados monitorados"
                  icon={HandCoinsIcon}
                  tone="neutral"
                />
                <StatsCard
                  title="Liquidáveis Agora"
                  value={String(kpis?.liquidaveis_agora ?? "0")}
                  delta="com parcelas aptas"
                  icon={CalendarCheck2Icon}
                  tone="positive"
                />
                <StatsCard
                  title="Sem Parcelas Elegíveis"
                  value={String(kpis?.sem_parcelas_elegiveis ?? "0")}
                  delta="associados sem saldo liquidável"
                  icon={ReceiptTextIcon}
                  tone="warning"
                />
                <StatsCard
                  title="Valor Potencial"
                  value={kpis ? formatCurrency(kpis.valor_total) : "—"}
                  delta="parcelas liquidáveis agora"
                  icon={WalletCardsIcon}
                  tone="positive"
                />
              </>
            ) : (
              <>
                <StatsCard
                  title="Contratos Liquidados"
                  value={String(kpis?.total_contratos ?? "0")}
                  delta="histórico no recorte"
                  icon={HandCoinsIcon}
                  tone="neutral"
                />
                <StatsCard
                  title="Parcelas Liquidadas"
                  value={String(kpis?.total_parcelas ?? "0")}
                  delta="parcelas registradas"
                  icon={ReceiptTextIcon}
                  tone="warning"
                />
                <StatsCard
                  title="Valor Liquidado"
                  value={kpis ? formatCurrency(kpis.valor_total) : "—"}
                  delta="valor consolidado"
                  icon={WalletCardsIcon}
                  tone="positive"
                />
                <StatsCard
                  title="Liquidações Revertidas"
                  value={String(kpis?.revertidas ?? 0)}
                  delta="histórico revertido"
                  icon={RotateCcwIcon}
                  tone="warning"
                />
              </>
            )}
          </section>

          <section className="rounded-[1.75rem] border border-border/60 bg-card/70 p-4">
            <div className="flex flex-col gap-3 xl:flex-row xl:items-center">
              <div className="flex-1">
                <Input
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder={
                    contractId
                      ? "Filtro travado no contrato vindo da renovação"
                      : "Buscar por nome, CPF, matrícula ou contrato..."
                  }
                  className="rounded-2xl border-border/60 bg-background/60"
                  disabled={Boolean(contractId)}
                />
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Sheet
                  open={filtersOpen}
                  onOpenChange={(open) => {
                    if (open) {
                      setDraftAgente(agente);
                      setDraftStatusAssociado(statusAssociado);
                      setDraftEtapaFluxo(etapaFluxo);
                      setDraftDataInicio(dataInicio);
                      setDraftDataFim(dataFim);
                      setDraftEstado(estado);
                    }
                    setFiltersOpen(open);
                  }}
                >
                  <SheetTrigger asChild>
                    <Button variant="outline" className="rounded-2xl">
                      <SlidersHorizontalIcon className="size-4" />
                      Filtros avançados
                      {activeFiltersCount ? (
                        <Badge className="ml-1 rounded-full bg-primary/15 px-2 py-0 text-primary">
                          {activeFiltersCount}
                        </Badge>
                      ) : null}
                    </Button>
                  </SheetTrigger>
                  <SheetContent className="w-full border-l border-border/60 sm:max-w-xl">
                    <SheetHeader>
                      <SheetTitle>Filtros avançados</SheetTitle>
                      <SheetDescription>
                        Refine a fila por agente, status visual, etapa do fluxo e intervalo de datas.
                      </SheetDescription>
                    </SheetHeader>

                    <div className="space-y-5 overflow-y-auto px-4 pb-4">
                      <div className="space-y-2">
                        <Label>Agente</Label>
                        <SearchableSelect
                          options={agentOptions}
                          value={draftAgente}
                          onChange={setDraftAgente}
                          placeholder="Todos os agentes"
                          searchPlaceholder="Buscar agente"
                          clearLabel="Limpar agente"
                          className="rounded-2xl border-border/60 bg-background/60"
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>Status</Label>
                        <Select value={draftStatusAssociado} onValueChange={setDraftStatusAssociado}>
                          <SelectTrigger className="rounded-2xl border-border/60 bg-background/60">
                            <SelectValue placeholder="Todos os status" />
                          </SelectTrigger>
                          <SelectContent>
                            {ASSOCIADO_STATUS_OPTIONS.map((option) => (
                              <SelectItem key={option.value} value={option.value}>
                                {option.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-2">
                        <Label>Etapa no fluxo</Label>
                        <Select value={draftEtapaFluxo} onValueChange={setDraftEtapaFluxo}>
                          <SelectTrigger className="rounded-2xl border-border/60 bg-background/60">
                            <SelectValue placeholder="Todas as etapas" />
                          </SelectTrigger>
                          <SelectContent>
                            {ETAPA_FLUXO_OPTIONS.map((option) => (
                              <SelectItem key={option.value} value={option.value}>
                                {option.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="grid gap-4 md:grid-cols-2">
                        <div className="space-y-2">
                          <Label>{tab === "liquidado" ? "Liquidado de" : "Data inicial"}</Label>
                          <DatePicker value={draftDataInicio} onChange={setDraftDataInicio} />
                        </div>
                        <div className="space-y-2">
                          <Label>{tab === "liquidado" ? "Liquidado até" : "Data final"}</Label>
                          <DatePicker value={draftDataFim} onChange={setDraftDataFim} />
                        </div>
                      </div>
                      {tab === "liquidado" ? (
                        <div className="space-y-2">
                          <Label>Situação</Label>
                          <Select value={draftEstado} onValueChange={setDraftEstado}>
                            <SelectTrigger className="rounded-2xl border-border/60 bg-background/60">
                              <SelectValue placeholder="Status da liquidação" />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="todos">Todos status</SelectItem>
                              <SelectItem value="ativa">Ativas</SelectItem>
                              <SelectItem value="revertida">Revertidas</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                      ) : null}
                    </div>

                    <SheetFooter>
                      <Button
                        variant="outline"
                        onClick={() => {
                          setDraftAgente("");
                          setDraftStatusAssociado("todos");
                          setDraftEtapaFluxo("todas");
                          setDraftDataInicio(undefined);
                          setDraftDataFim(undefined);
                          setDraftEstado("todos");
                          setAgente("");
                          setStatusAssociado("todos");
                          setEtapaFluxo("todas");
                          setDataInicio(undefined);
                          setDataFim(undefined);
                          setEstado("todos");
                          setFiltersOpen(false);
                        }}
                      >
                        Limpar
                      </Button>
                      <Button
                        onClick={() => {
                          setAgente(draftAgente);
                          setStatusAssociado(draftStatusAssociado);
                          setEtapaFluxo(draftEtapaFluxo);
                          setDataInicio(draftDataInicio);
                          setDataFim(draftDataFim);
                          setEstado(draftEstado);
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
                    setAgente("");
                    setStatusAssociado("todos");
                    setEtapaFluxo("todas");
                    setDataInicio(undefined);
                    setDataFim(undefined);
                    setEstado("todos");
                    setDraftAgente("");
                    setDraftStatusAssociado("todos");
                    setDraftEtapaFluxo("todas");
                    setDraftDataInicio(undefined);
                    setDraftDataFim(undefined);
                    setDraftEstado("todos");
                  }}
                >
                  Limpar
                </Button>
              </div>
            </div>
          </section>

          <DataTable
            columns={columns}
            data={rows}
            renderExpanded={renderExpanded}
            pageSize={20}
            currentPage={page}
            totalPages={Math.max(1, Math.ceil(totalCount / 20))}
            onPageChange={setPage}
            loading={query.isLoading}
            emptyMessage={
              tab === "elegivel"
                ? "Nenhum associado encontrado na fila de liquidação."
                : "Nenhuma liquidação encontrada."
            }
          />
        </TabsContent>
      </Tabs>

      <Dialog
        open={!!liquidarState}
        onOpenChange={(open) => {
          if (!open) {
            setLiquidarState(null);
          }
        }}
      >
        <DialogContent className="grid h-[min(94dvh,66rem)] w-[96vw] max-h-[94dvh] !max-w-[1440px] grid-rows-[auto_minmax(0,1fr)_auto] gap-0 overflow-hidden rounded-[2rem] border border-border/60 bg-card/95 p-0 shadow-2xl shadow-black/40">
          <DialogHeader className="border-b border-border/60 px-6 pb-4 pt-6 pr-14">
            <DialogTitle>Registrar liquidação</DialogTitle>
            <DialogDescription>
              {liquidarState ? (
                <>
                  <strong>{liquidarState.row.nome}</strong> ·{" "}
                  {liquidarState.row.contrato_codigo || "Sem contrato operacional"}
                </>
              ) : null}
            </DialogDescription>
          </DialogHeader>
          {liquidarState ? (
            <div className="grid min-h-0 grid-rows-[auto_minmax(0,1fr)] overflow-hidden">
              <div className="border-b border-border/60 px-6 py-6">
                <div className="grid gap-4 sm:grid-cols-2 2xl:grid-cols-4">
                  <div className="rounded-2xl border border-border/60 bg-background/60 p-4">
                    <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                      Parcelas
                    </p>
                    <p className="mt-2 text-lg font-semibold">
                      {liquidarState.row.quantidade_parcelas}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-border/60 bg-background/60 p-4">
                    <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                      Recorte
                    </p>
                    <p className="mt-2 break-words text-sm font-medium">
                      {liquidarState.row.referencia_inicial && liquidarState.row.referencia_final
                        ? `${formatMonthYear(liquidarState.row.referencia_inicial)} até ${formatMonthYear(
                            liquidarState.row.referencia_final,
                          )}`
                        : "Sem referências"}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-border/60 bg-background/60 p-4">
                    <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                      Valor sugerido
                    </p>
                    <p className="mt-2 text-sm font-medium">
                      {formatCurrency(liquidarState.row.valor_total)}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-border/60 bg-background/60 p-4">
                    <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                      Agente
                    </p>
                    <p className="mt-2 break-words text-sm font-medium">
                      {liquidarState.row.agente_nome || "Sem agente"}
                    </p>
                  </div>
                </div>
              </div>

              <div className="grid min-h-0 grid-cols-1 overflow-hidden xl:grid-cols-[minmax(0,1fr)_460px]">
                <div className="min-w-0 overflow-hidden xl:border-r xl:border-border/60">
                  <div className="flex h-full min-h-0 flex-col px-6 py-6">
                    <div className="space-y-6">
                      <div className="space-y-2">
                        <Label>Origem da solicitação *</Label>
                        <Select
                          disabled={isRenewalOrigin(liquidarState.row)}
                          value={liquidarState.origemSolicitacao}
                          onValueChange={(value) =>
                            setLiquidarState((current) =>
                              current ? { ...current, origemSolicitacao: value } : current,
                            )
                          }
                        >
                          <SelectTrigger className="w-full rounded-2xl border-border/60 bg-background/60">
                            <SelectValue placeholder="Selecione a origem da solicitação" />
                          </SelectTrigger>
                          <SelectContent>
                            {ORIGEM_SOLICITACAO_OPTIONS.map((option) => (
                              <SelectItem key={option.value} value={option.value}>
                                {option.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        {isRenewalOrigin(liquidarState.row) ? (
                          <p className="text-sm text-muted-foreground">
                            Origem preenchida automaticamente pelo fluxo de renovação.
                          </p>
                        ) : null}
                      </div>

                      <div className="space-y-3">
                        <div className="space-y-1">
                          <p className="text-sm font-medium">
                            {liquidacaoParcelas.length
                              ? "Parcelas incluídas na liquidação"
                              : "Encerramento sem baixa de parcelas"}
                          </p>
                          <p className="max-w-3xl text-sm text-muted-foreground">
                            {liquidacaoParcelas.length
                              ? "Confirme os comprovantes de pagamento das parcelas abaixo antes de registrar a liquidação."
                              : "Este registro apenas encerrará o contrato. Não há parcelas aptas para baixa neste momento."}
                          </p>
                        </div>
                      </div>
                    </div>

                    <div className="mt-6 min-h-0 flex-1">
                      {liquidacaoParcelas.length ? (
                        <div className="h-full overflow-auto rounded-xl border border-border/60">
                          <table className="min-w-[720px] w-full text-sm">
                            <thead>
                              <tr className="sticky top-0 border-b border-border/60 bg-muted/90 backdrop-blur">
                                <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                                  Parcela
                                </th>
                                <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                                  Referência
                                </th>
                                <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                                  Vencimento
                                </th>
                                <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                                  Valor
                                </th>
                                <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                                  Status
                                </th>
                              </tr>
                            </thead>
                            <tbody>
                              {liquidacaoParcelas.map((parcela) => (
                                <tr
                                  key={`${liquidarState.row.contrato_id ?? liquidarState.row.id}-${parcela.id}-${parcela.referencia_mes}`}
                                  className="border-b border-border/40 last:border-0 hover:bg-white/3"
                                >
                                  <td className="px-4 py-3 font-medium">Parcela {parcela.numero}</td>
                                  <td className="px-4 py-3 text-muted-foreground">
                                    {formatMonthYear(parcela.referencia_mes)}
                                  </td>
                                  <td className="px-4 py-3 text-muted-foreground">
                                    {formatDate(parcela.data_vencimento)}
                                  </td>
                                  <td className="px-4 py-3 font-semibold">
                                    {formatCurrency(parcela.valor)}
                                  </td>
                                  <td className="px-4 py-3">
                                    <StatusBadge status={parcela.status} />
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      ) : (
                        <div className="rounded-2xl border border-border/60 bg-background/60 p-4 text-sm text-muted-foreground">
                          Nenhuma parcela será baixada nesta operação. O comprovante anexado
                          documenta apenas o encerramento e a inativação do contrato.
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                <div className="min-w-0 overflow-y-auto">
                  <div className="space-y-6 px-6 py-6">
                    <div className="space-y-2">
                      <Label>Comprovantes de pagamento das parcelas da liquidação *</Label>
                      <FileUploadDropzone
                        accept={comprovanteAccept}
                        maxSize={10 * 1024 * 1024}
                        files={liquidarState.comprovantes}
                        multiple
                        onUploadMany={(files) =>
                          setLiquidarState((current) =>
                            current ? { ...current, comprovantes: files } : current,
                          )
                        }
                        isProcessing={false}
                      />
                      {liquidarState.comprovantes.length ? (
                        <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300">
                          <p>{liquidarState.comprovantes.length} anexo(s) pronto(s) para envio.</p>
                          {liquidarState.comprovantes.slice(0, 3).map((arquivo) => (
                            <p key={`${arquivo.name}-${arquivo.size}`} className="break-words">
                              {arquivo.name}
                            </p>
                          ))}
                        </div>
                      ) : null}
                    </div>

                    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
                      <div className="space-y-2">
                        <Label>Data da liquidação *</Label>
                        <DatePicker
                          value={parseApiDateValue(liquidarState.dataLiquidacao)}
                          onChange={(date) =>
                            setLiquidarState((current) =>
                              current
                                ? {
                                    ...current,
                                    dataLiquidacao: date ? format(date, "yyyy-MM-dd") : "",
                                  }
                                : current,
                            )
                          }
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>Valor total *</Label>
                        <InputCurrency
                          value={parseDecimalToCents(liquidarState.valorTotal)}
                          onChange={(value) =>
                            setLiquidarState((current) =>
                              current
                                ? {
                                    ...current,
                                    valorTotal:
                                      value != null ? (value / 100).toFixed(2) : "",
                                  }
                                : current,
                            )
                          }
                          className="h-11 rounded-xl border-border/60 bg-background/60 font-medium"
                        />
                      </div>
                    </div>

                    <div className="space-y-2">
                      <Label>Observação *</Label>
                      <Textarea
                        value={liquidarState.observacao}
                        onChange={(event) =>
                          setLiquidarState((current) =>
                            current ? { ...current, observacao: event.target.value } : current,
                          )
                        }
                        className="min-h-36 rounded-2xl border-border/60 bg-background/60"
                        placeholder="Descreva o encerramento e o contexto da liquidação..."
                      />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ) : null}
          <DialogFooter className="border-t border-border/60 px-6 pb-6 pt-4">
            <Button variant="outline" onClick={() => setLiquidarState(null)}>
              Cancelar
            </Button>
            <Button
              variant="success"
              disabled={
                liquidarMutation.isPending ||
                !liquidarState?.comprovantes.length ||
                !liquidarState?.dataLiquidacao ||
                !liquidarState?.valorTotal ||
                !liquidarState?.origemSolicitacao ||
                !liquidarState?.observacao.trim()
              }
              onClick={() => {
                if (!liquidarState) {
                  return;
                }
                if (!liquidarState?.comprovantes.length) {
                  toast.error("Envie pelo menos um comprovante de pagamento.");
                  return;
                }
                if (!liquidarState?.origemSolicitacao) {
                  toast.error("Selecione a origem da solicitação.");
                  return;
                }
                liquidarMutation.mutate(liquidarState);
              }}
            >
              Confirmar liquidação
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={!!reverterTarget}
        onOpenChange={(open) => {
          if (!open) {
            setReverterTarget(null);
            setMotivoReversao("");
          }
        }}
      >
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Reverter liquidação</DialogTitle>
            <DialogDescription>
              {reverterTarget ? (
                <>
                  <strong>{reverterTarget.nome}</strong> · {reverterTarget.contrato_codigo}
                </>
              ) : null}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label>Motivo da reversão *</Label>
            <Textarea
              value={motivoReversao}
              onChange={(event) => setMotivoReversao(event.target.value)}
              className="min-h-24"
              placeholder="Explique por que a liquidação precisa ser revertida..."
            />
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setReverterTarget(null);
                setMotivoReversao("");
              }}
            >
              Cancelar
            </Button>
            <Button
              disabled={
                reverterMutation.isPending ||
                !motivoReversao.trim() ||
                reverterTarget?.contrato_id == null
              }
              onClick={() => {
                if (!reverterTarget || reverterTarget.contrato_id == null) {
                  return;
                }
                reverterMutation.mutate({
                  contratoId: reverterTarget.contrato_id,
                  motivo: motivoReversao,
                });
              }}
            >
              Confirmar reversão
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={!!deleteTarget}
        onOpenChange={(open) => {
          if (!open) {
            setDeleteTarget(null);
            setMotivoExclusao("");
          }
        }}
      >
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Excluir liquidação</DialogTitle>
            <DialogDescription>
              {deleteTarget ? (
                <>
                  O registro de liquidação de <strong>{deleteTarget.nome}</strong> será excluído
                  da tesouraria. Se ainda estiver ativo, o sistema vai reverter o efeito da
                  liquidação antes de remover o registro.
                </>
              ) : null}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 rounded-2xl border border-border/60 bg-card/60 p-4">
            {deleteTarget ? (
              <>
                <div className="space-y-1 text-sm">
                  <p className="font-medium">
                    {deleteTarget.contrato_codigo} · {formatCurrency(deleteTarget.valor_total)}
                  </p>
                  <p className="text-muted-foreground">
                    {deleteTarget.quantidade_parcelas} parcela(s) ·{" "}
                    {deleteTarget.data_liquidacao
                      ? formatDate(deleteTarget.data_liquidacao)
                      : "sem data de liquidação"}
                  </p>
                </div>
                <div className="space-y-2">
                  <Label>Motivo da exclusão *</Label>
                  <Textarea
                    value={motivoExclusao}
                    onChange={(event) => setMotivoExclusao(event.target.value)}
                    className="min-h-24"
                    placeholder="Explique por que este registro deve ser excluído..."
                  />
                </div>
              </>
            ) : null}
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setDeleteTarget(null);
                setMotivoExclusao("");
              }}
            >
              Cancelar
            </Button>
            <Button
              variant="destructive"
              disabled={
                deleteMutation.isPending ||
                !deleteTarget?.liquidacao_id ||
                !motivoExclusao.trim()
              }
              onClick={() => {
                if (!deleteTarget?.liquidacao_id || !motivoExclusao.trim()) {
                  return;
                }
                deleteMutation.mutate({
                  liquidacaoId: deleteTarget.liquidacao_id,
                  motivo: motivoExclusao.trim(),
                });
              }}
            >
              Excluir liquidação
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
