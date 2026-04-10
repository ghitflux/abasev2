"use client";

import * as React from "react";
import { format } from "date-fns";
import { ptBR } from "date-fns/locale";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircleIcon,
  ChevronRightIcon,
  ClipboardCheckIcon,
  ClipboardListIcon,
  ExternalLinkIcon,
  HandCoinsIcon,
  SlidersHorizontalIcon,
  TrendingDownIcon,
  UploadIcon,
  UserXIcon,
  WalletCardsIcon,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { apiFetch } from "@/lib/api/client";
import { formatCurrency, formatDate } from "@/lib/formatters";
import {
  describeReportScope,
  exportRouteReport,
  fetchAllPaginatedRows,
  filterRowsByReportScope,
  resolveReportReferenceDate,
  type ReportScope,
} from "@/lib/reports";
import CalendarCompetencia from "@/components/custom/calendar-competencia";
import DatePicker from "@/components/custom/date-picker";
import FileUploadDropzone from "@/components/custom/file-upload-dropzone";
import SearchableSelect from "@/components/custom/searchable-select";
import StatusBadge from "@/components/custom/status-badge";
import CopySnippet from "@/components/shared/copy-snippet";
import DataTable, { type DataTableColumn } from "@/components/shared/data-table";
import ExportButton from "@/components/shared/export-button";
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
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";

type ListingTab = "pendentes" | "quitados";

type SimpleUser = {
  id: number;
  full_name: string;
};

type BaixaManualItem = {
  id: number;
  parcela_id: number | null;
  associado_id: number;
  nome: string;
  cpf_cnpj: string;
  matricula: string;
  agente_nome: string;
  contrato_id: number | null;
  contrato_codigo: string;
  referencia_mes: string;
  valor: string;
  status: string;
  data_vencimento: string | null;
  observacao: string;
  data_baixa: string | null;
  valor_pago: string | null;
  realizado_por_nome: string;
  nome_comprovante: string;
  origem: string;
  arquivo_retorno_item_id: number | null;
  pode_dar_baixa: boolean;
};

type BaixaManualKpis = {
  total_pendentes?: number;
  em_aberto?: number;
  nao_descontado?: number;
  valor_total_pendente?: string;
  baixas_realizadas_mes?: number;
  total_associados?: number;
  total_quitados?: number;
  total_inadimplentes?: number;
  valor_total_quitado?: string;
  quitados_este_mes?: number;
  valor_quitado_este_mes?: string;
  total_pendentes_com_parcela?: number;
};

type BaixaManualResponse = {
  count: number;
  results: BaixaManualItem[];
  kpis: BaixaManualKpis;
};

type AssociadoGroup = {
  id: number;
  associado_id: number;
  nome: string;
  cpf_cnpj: string;
  matricula: string;
  agente_nome: string;
  parcelas: BaixaManualItem[];
  total_parcelas: number;
  valor_total: number;
  ultima_baixa: string | null;
  possuiParcelaBaixavel: boolean;
};

type DarBaixaState = {
  item: BaixaManualItem;
  comprovante: File | null;
  valorPago: string;
  observacao: string;
};

type InativarAssociadoState = {
  group: AssociadoGroup;
  comprovante: File | null;
  observacao: string;
};

type AdvancedFilters = {
  agente: string;
  dataInicio?: Date;
  dataFim?: Date;
};

const comprovanteAccept = {
  "application/pdf": [".pdf"],
  "image/png": [".png"],
  "image/jpeg": [".jpg", ".jpeg"],
};

function formatMonthYear(value: string) {
  try {
    const [year, month] = value.split("-").map(Number);
    return format(new Date(year, month - 1, 1), "MMM/yyyy", { locale: ptBR });
  } catch {
    return value;
  }
}

function parseCurrencyValue(value?: string | null) {
  return Number.parseFloat(value ?? "") || 0;
}

function resolveItemAmount(item: BaixaManualItem, listing: ListingTab) {
  if (listing === "quitados") {
    return parseCurrencyValue(item.valor_pago ?? item.valor);
  }
  return parseCurrencyValue(item.valor);
}

function groupByAssociado(items: BaixaManualItem[], listing: ListingTab): AssociadoGroup[] {
  const map = new Map<number, AssociadoGroup>();

  for (const item of items) {
    const value = resolveItemAmount(item, listing);
    const existing = map.get(item.associado_id);

    if (existing) {
      existing.parcelas.push(item);
      existing.total_parcelas += 1;
      existing.valor_total += value;
      existing.possuiParcelaBaixavel =
        existing.possuiParcelaBaixavel || Boolean(item.pode_dar_baixa && item.parcela_id);
      if (listing === "quitados" && item.data_baixa) {
        existing.ultima_baixa =
          !existing.ultima_baixa || item.data_baixa > existing.ultima_baixa
            ? item.data_baixa
            : existing.ultima_baixa;
      }
      continue;
    }

    map.set(item.associado_id, {
      id: item.associado_id,
      associado_id: item.associado_id,
      nome: item.nome,
      cpf_cnpj: item.cpf_cnpj,
      matricula: item.matricula,
      agente_nome: item.agente_nome,
      parcelas: [item],
      total_parcelas: 1,
      valor_total: value,
      ultima_baixa: listing === "quitados" ? item.data_baixa : null,
      possuiParcelaBaixavel: Boolean(item.pode_dar_baixa && item.parcela_id),
    });
  }

  return Array.from(map.values());
}

function countActiveAdvancedFilters(filters: AdvancedFilters) {
  return [filters.agente, filters.dataInicio, filters.dataFim].filter(Boolean).length;
}

export default function BaixaManualPage() {
  const queryClient = useQueryClient();
  const router = useRouter();
  const [listing, setListing] = React.useState<ListingTab>("pendentes");
  const [page, setPage] = React.useState(1);
  const [search, setSearch] = React.useState("");
  const [isExporting, setIsExporting] = React.useState(false);
  const [statusFilter, setStatusFilter] = React.useState("nao_descontado");
  const [competencia, setCompetencia] = React.useState<Date | undefined>();
  const [agente, setAgente] = React.useState("");
  const [dataInicio, setDataInicio] = React.useState<Date | undefined>();
  const [dataFim, setDataFim] = React.useState<Date | undefined>();
  const [filtersOpen, setFiltersOpen] = React.useState(false);
  const [draftFilters, setDraftFilters] = React.useState<AdvancedFilters>({
    agente: "",
    dataInicio: undefined,
    dataFim: undefined,
  });
  const [darBaixaState, setDarBaixaState] = React.useState<DarBaixaState | null>(null);
  const [inativarAssociadoState, setInativarAssociadoState] =
    React.useState<InativarAssociadoState | null>(null);
  const [navigatingId, setNavigatingId] = React.useState<number | null>(null);

  const competenciaParam = competencia ? format(competencia, "yyyy-MM") : undefined;
  const activeAdvancedFiltersCount = countActiveAdvancedFilters({
    agente,
    dataInicio,
    dataFim,
  });

  const agentesQuery = useQuery({
    queryKey: ["baixa-manual-agentes"],
    queryFn: () => apiFetch<SimpleUser[]>("associados/agentes"),
  });

  const agentOptions = React.useMemo(
    () =>
      (agentesQuery.data ?? []).map((item) => ({
        value: String(item.id),
        label: item.full_name,
      })),
    [agentesQuery.data],
  );

  React.useEffect(() => {
    setPage(1);
  }, [listing, search, statusFilter, competenciaParam, agente, dataInicio, dataFim]);

  const query = useQuery({
    queryKey: [
      "tesouraria-baixa-manual",
      listing,
      page,
      search,
      statusFilter,
      competenciaParam,
      agente,
      dataInicio?.toISOString(),
      dataFim?.toISOString(),
    ],
    queryFn: () =>
      apiFetch<BaixaManualResponse>("tesouraria/baixa-manual", {
        query: {
          page,
          page_size: 50,
          listing,
          search: search || undefined,
          status:
            listing === "pendentes" && statusFilter !== "todos" ? statusFilter : undefined,
          competencia: competenciaParam,
          agente: agente || undefined,
          data_inicio: dataInicio ? format(dataInicio, "yyyy-MM-dd") : undefined,
          data_fim: dataFim ? format(dataFim, "yyyy-MM-dd") : undefined,
        },
      }),
  });

  const handleExport = React.useCallback(
    async (scope: ReportScope, formatValue: "pdf" | "xlsx") => {
      const referenceDate = resolveReportReferenceDate({
        scope,
        dayReference: dataInicio ?? dataFim,
        monthReference: competencia ?? dataInicio ?? dataFim,
      });

      setIsExporting(true);
      try {
        const sourceQuery = {
          listing,
          search: search || undefined,
          status:
            listing === "pendentes" && statusFilter !== "todos" ? statusFilter : undefined,
          competencia: competenciaParam,
          agente: agente || undefined,
          data_inicio: dataInicio ? format(dataInicio, "yyyy-MM-dd") : undefined,
          data_fim: dataFim ? format(dataFim, "yyyy-MM-dd") : undefined,
        };
        const fetchedRows = await fetchAllPaginatedRows<BaixaManualItem>({
          sourcePath: "tesouraria/baixa-manual",
          sourceQuery,
        });
        const rows = filterRowsByReportScope({
          rows: fetchedRows,
          scope,
          referenceDate,
          getCandidates: (row) =>
            listing === "quitados"
              ? [row.data_baixa, row.data_vencimento, row.referencia_mes]
              : [row.data_vencimento, row.referencia_mes, row.data_baixa],
        }).map((row) => ({
          nome: row.nome,
          cpf_cnpj: row.cpf_cnpj,
          matricula: row.matricula,
          agente_nome: row.agente_nome,
          contrato_codigo: row.contrato_codigo,
          referencia_mes: row.referencia_mes,
          valor: row.valor,
          status: row.status,
          data_vencimento: row.data_vencimento,
          data_baixa: row.data_baixa,
          valor_pago: row.valor_pago ?? "",
          observacao: row.observacao,
          realizado_por_nome: row.realizado_por_nome,
          nome_comprovante: row.nome_comprovante,
        }));

        await exportRouteReport({
          route: "/tesouraria/baixa-manual",
          format: formatValue,
          rows,
          filters: {
            ...sourceQuery,
            ...describeReportScope(scope, referenceDate),
          },
        });
      } catch (error) {
        toast.error(
          error instanceof Error ? error.message : "Falha ao exportar inadimplentes.",
        );
      } finally {
        setIsExporting(false);
      }
    },
    [
      agente,
      competencia,
      competenciaParam,
      dataFim,
      dataInicio,
      listing,
      search,
      statusFilter,
    ],
  );

  const darBaixaMutation = useMutation({
    mutationFn: async ({
      parcelaId,
      comprovante,
      valorPago,
      observacao,
    }: {
      parcelaId: number;
      comprovante: File;
      valorPago: string;
      observacao: string;
    }) => {
      const fd = new FormData();
      fd.append("comprovante", comprovante);
      fd.append("valor_pago", valorPago);
      if (observacao) {
        fd.append("observacao", observacao);
      }
      return apiFetch(`tesouraria/baixa-manual/${parcelaId}/dar-baixa`, {
        method: "POST",
        formData: fd,
      });
    },
    onSuccess: () => {
      toast.success("Baixa manual registrada com sucesso.");
      setDarBaixaState(null);
      void queryClient.invalidateQueries({ queryKey: ["tesouraria-baixa-manual"] });
      void queryClient.invalidateQueries({ queryKey: ["agente-pagamentos"] });
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Falha ao registrar baixa manual.");
    },
  });

  const inativarAssociadoMutation = useMutation({
    mutationFn: async ({
      associadoId,
      comprovante,
      observacao,
    }: {
      associadoId: number;
      comprovante: File;
      observacao: string;
    }) => {
      const fd = new FormData();
      fd.append("associado_id", String(associadoId));
      fd.append("comprovante", comprovante);
      if (observacao) {
        fd.append("observacao", observacao);
      }
      return apiFetch<{
        associado_id: number;
        parcelas_baixadas: number;
        total_baixado: string;
      }>("tesouraria/baixa-manual/inativar-associado", {
        method: "POST",
        formData: fd,
      });
    },
    onSuccess: (payload) => {
      toast.success(
        `Associado inativado e ${payload.parcelas_baixadas} parcela(s) baixada(s).`,
      );
      setInativarAssociadoState(null);
      void queryClient.invalidateQueries({ queryKey: ["tesouraria-baixa-manual"] });
      void queryClient.invalidateQueries({ queryKey: ["associado"] });
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : "Falha ao inativar associado.",
      );
    },
  });

  function handleVerDetalhes(associadoId: number) {
    setNavigatingId(associadoId);
    router.push(`/associados/${associadoId}`);
  }

  function resetFilters() {
    setSearch("");
    setStatusFilter("nao_descontado");
    setCompetencia(undefined);
    setAgente("");
    setDataInicio(undefined);
    setDataFim(undefined);
    setDraftFilters({
      agente: "",
      dataInicio: undefined,
      dataFim: undefined,
    });
    setPage(1);
  }

  const kpis = query.data?.kpis;
  const rows = query.data?.results ?? [];
  const totalCount = query.data?.count ?? 0;
  const groups = React.useMemo(() => groupByAssociado(rows, listing), [listing, rows]);

  const columns = React.useMemo<DataTableColumn<AssociadoGroup>[]>(() => {
    const baseColumns: DataTableColumn<AssociadoGroup>[] = [
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
        cell: (row) =>
          navigatingId === row.associado_id ? (
            <div className="space-y-2">
              <Skeleton className="h-4 w-40" />
              <Skeleton className="h-3 w-24" />
            </div>
          ) : (
            <p className="font-medium leading-tight">{row.nome}</p>
          ),
      },
      {
        id: "cpf",
        header: "CPF",
        cell: (row) =>
          navigatingId === row.associado_id ? (
            <Skeleton className="h-5 w-28" />
          ) : (
            <CopySnippet label="CPF" value={row.cpf_cnpj} mono inline />
          ),
      },
      {
        id: "matricula",
        header: "Matrícula do Servidor",
        cell: (row) =>
          navigatingId === row.associado_id ? (
            <Skeleton className="h-5 w-20" />
          ) : (
            <CopySnippet label="Matrícula do Servidor" value={row.matricula} mono inline />
          ),
      },
      {
        id: "agente",
        header: "Agente",
        cell: (row) => (
          <span className="text-sm text-muted-foreground">{row.agente_nome || "-"}</span>
        ),
      },
    ];

    if (listing === "quitados") {
      baseColumns.push({
        id: "ultima_baixa",
        header: "Última baixa",
        cell: (row) => (
          <span className="text-sm text-muted-foreground">
            {row.ultima_baixa ? formatDate(row.ultima_baixa) : "-"}
          </span>
        ),
      });
    }

    baseColumns.push(
      {
        id: "parcelas",
        header: listing === "quitados" ? "Quitações" : "Parcelas",
        cell: (row) => (
          <Badge variant="secondary" className="font-mono text-xs">
            {row.total_parcelas} item{row.total_parcelas !== 1 ? "s" : ""}
          </Badge>
        ),
      },
      {
        id: "valor_total",
        header: "Valor Total",
        cell: (row) => (
          <span className="font-semibold tabular-nums">
            {formatCurrency(row.valor_total.toFixed(2))}
          </span>
        ),
      },
      {
        id: "acoes",
        header: "",
        cell: (row) => (
          <div className="flex flex-wrap justify-end gap-2">
            {listing === "pendentes" ? (
              <Button
                size="sm"
                variant="outline"
                className="shrink-0"
                disabled={!row.possuiParcelaBaixavel}
                onClick={(event) => {
                  event.stopPropagation();
                  setInativarAssociadoState({
                    group: row,
                    comprovante: null,
                    observacao: "",
                  });
                }}
              >
                <UserXIcon className="mr-1.5 size-3.5" />
                Inativar
              </Button>
            ) : null}
            <Button
              size="sm"
              variant="outline"
              className="shrink-0"
              disabled={navigatingId === row.associado_id}
              onClick={(event) => {
                event.stopPropagation();
                handleVerDetalhes(row.associado_id);
              }}
            >
              {navigatingId === row.associado_id ? (
                <Spinner className="mr-1.5 size-3.5" />
              ) : (
                <ExternalLinkIcon className="mr-1.5 size-3.5" />
              )}
              Ver Detalhes
            </Button>
          </div>
        ),
      },
    );

    return baseColumns;
  }, [listing, navigatingId]);

  const renderExpanded = React.useCallback(
    (group: AssociadoGroup) =>
      listing === "quitados" ? (
        <div className="space-y-3">
          <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
            Inadimplentes Quitados - {group.nome}
          </p>
          <div className="overflow-hidden rounded-xl border border-border/60">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/60 bg-muted/20">
                  <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Contrato
                  </th>
                  <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Referência do Ciclo
                  </th>
                  <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Baixado em
                  </th>
                  <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Valor Pago
                  </th>
                  <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Status
                  </th>
                  <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Registrado por
                  </th>
                </tr>
              </thead>
              <tbody>
                {group.parcelas.map((parcela) => (
                  <tr
                    key={parcela.id}
                    className="border-b border-border/40 transition-colors last:border-0 hover:bg-white/3"
                  >
                    <td className="px-4 py-3">
                      <CopySnippet label="Contrato" value={parcela.contrato_codigo} mono inline />
                    </td>
                    <td className="px-4 py-3 font-medium">
                      {formatMonthYear(parcela.referencia_mes)}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {parcela.data_baixa ? formatDate(parcela.data_baixa) : "-"}
                    </td>
                    <td className="px-4 py-3 font-semibold tabular-nums">
                      {formatCurrency(parcela.valor_pago ?? parcela.valor)}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status="descontado" />
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {parcela.realizado_por_nome || "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
              Parcelas Pendentes - {group.nome}
            </p>
            <Button
              size="sm"
              variant="outline"
              disabled={!group.possuiParcelaBaixavel}
              onClick={() =>
                setInativarAssociadoState({
                  group,
                  comprovante: null,
                  observacao: "",
                })
              }
            >
              <UserXIcon className="mr-1.5 size-3.5" />
              Inativar associado
            </Button>
          </div>
          <div className="overflow-hidden rounded-xl border border-border/60">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/60 bg-muted/20">
                  <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Contrato
                  </th>
                  <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Referência do Ciclo
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
                    Origem
                  </th>
                  <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Ação
                  </th>
                </tr>
              </thead>
              <tbody>
                {group.parcelas.map((parcela) => (
                  <tr
                    key={parcela.id}
                    className="border-b border-border/40 transition-colors last:border-0 hover:bg-white/3"
                  >
                    <td className="px-4 py-3">
                      {parcela.contrato_codigo ? (
                        <CopySnippet label="Contrato" value={parcela.contrato_codigo} mono inline />
                      ) : (
                        <span className="text-muted-foreground">-</span>
                      )}
                    </td>
                    <td className="px-4 py-3 font-medium">
                      {formatMonthYear(parcela.referencia_mes)}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {parcela.data_vencimento ? formatDate(parcela.data_vencimento) : "-"}
                    </td>
                    <td className="px-4 py-3 font-semibold tabular-nums">
                      {formatCurrency(parcela.valor)}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={parcela.status} />
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant="outline">
                        {parcela.origem === "arquivo_retorno" ? "Arquivo retorno" : "Parcela"}
                      </Badge>
                    </td>
                    <td className="px-4 py-3">
                      {parcela.pode_dar_baixa && parcela.parcela_id ? (
                        <Button
                          size="sm"
                          variant="success"
                          onClick={() =>
                            setDarBaixaState({
                              item: parcela,
                              comprovante: null,
                              valorPago: parcela.valor,
                              observacao: "",
                            })
                          }
                        >
                          <UploadIcon className="mr-1.5 size-3.5" />
                          Dar Baixa
                        </Button>
                      ) : (
                        <span className="text-xs text-muted-foreground">
                          Sem parcela vinculada
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ),
    [listing],
  );

  return (
    <div className="space-y-6">
      <section className="rounded-[1.75rem] border border-border/60 bg-card/70 p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-1">
            <h1 className="text-3xl font-semibold">Inadimplentes</h1>
            <p className="text-sm text-muted-foreground">
              {listing === "quitados"
                ? "Histórico das parcelas inadimplentes que já receberam baixa manual."
                : "Fila operacional construída a partir do arquivo retorno e das parcelas vencidas em aberto - registre a baixa com comprovante."}
            </p>
            <Tabs
              value={listing}
              onValueChange={(value) => setListing(value as ListingTab)}
              className="w-full"
            >
              <TabsList variant="line" className="w-fit">
                <TabsTrigger value="pendentes">Pendentes</TabsTrigger>
                <TabsTrigger value="quitados">Quitados</TabsTrigger>
              </TabsList>
            </Tabs>
          </div>
          <ExportButton
            disabled={isExporting}
            label={isExporting ? "Exportando..." : "Exportar"}
            enableScopeSelection
            onExport={(formatValue) =>
              formatValue === "pdf" || formatValue === "xlsx"
                ? void handleExport("month", formatValue)
                : undefined
            }
            onExportScoped={(scope, formatValue) => void handleExport(scope, formatValue)}
          />
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {listing === "quitados" ? (
          <>
            <StatsCard
              title="Total Quitados"
              value={String(kpis?.total_quitados ?? "-")}
              delta="inadimplências com baixa manual"
              icon={ClipboardCheckIcon}
              tone="positive"
            />
            <StatsCard
              title="Valor Total Quitado"
              value={kpis?.valor_total_quitado ? formatCurrency(kpis.valor_total_quitado) : "-"}
              delta="somatório do recorte atual"
              icon={WalletCardsIcon}
              tone="neutral"
            />
            <StatsCard
              title="Quitados Este Mês"
              value={String(kpis?.quitados_este_mes ?? "-")}
              delta="baixas registradas no mês corrente"
              icon={CheckCircleIcon}
              tone="positive"
            />
            <StatsCard
              title="Valor Quitado Este Mês"
              value={
                kpis?.valor_quitado_este_mes
                  ? formatCurrency(kpis.valor_quitado_este_mes)
                  : "-"
              }
              delta="inadimplência já regularizada"
              icon={HandCoinsIcon}
              tone="neutral"
            />
          </>
        ) : (
          <>
            <StatsCard
              title="Total Inadimplentes"
              value={String(kpis?.total_inadimplentes ?? "-")}
              delta={`${kpis?.total_pendentes_com_parcela ?? 0} com parcela registrada`}
              icon={ClipboardListIcon}
              tone="warning"
            />
            <StatsCard
              title="Parcelas Inadimplentes"
              value={String(kpis?.nao_descontado ?? "-")}
              delta="retornaram não descontadas"
              icon={TrendingDownIcon}
              tone="warning"
            />
            <StatsCard
              title="Parcelas Quitadas"
              value={String(kpis?.total_quitados ?? "-")}
              delta={`Baixas este mês: ${kpis?.baixas_realizadas_mes ?? 0}`}
              icon={CheckCircleIcon}
              tone="positive"
            />
            <StatsCard
              title="Valor Total Pendente"
              value={
                kpis?.valor_total_pendente ? formatCurrency(kpis.valor_total_pendente) : "-"
              }
              delta="saldo inadimplente em aberto"
              icon={HandCoinsIcon}
              tone="neutral"
            />
          </>
        )}
      </section>

      <section className="rounded-[1.75rem] border border-border/60 bg-card/50 p-4">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-center">
          <div className="flex-1">
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Buscar por nome, CPF, matrícula ou contrato..."
              className="rounded-2xl border-border/60 bg-card/60"
            />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {listing === "pendentes" ? (
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="w-[180px] rounded-2xl border-border/60 bg-card/60">
                  <SelectValue placeholder="Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="todos">Todos</SelectItem>
                  <SelectItem value="em_aberto">Em aberto</SelectItem>
                  <SelectItem value="nao_descontado">Não descontado</SelectItem>
                </SelectContent>
              </Select>
            ) : null}
            <div className="min-w-[180px]">
              <CalendarCompetencia
                value={competencia}
                onChange={(dateValue) => setCompetencia(dateValue)}
              />
            </div>
            <Sheet
              open={filtersOpen}
              onOpenChange={(open) => {
                if (open) {
                  setDraftFilters({ agente, dataInicio, dataFim });
                }
                setFiltersOpen(open);
              }}
            >
              <SheetTrigger asChild>
                <Button variant="outline" className="rounded-2xl">
                  <SlidersHorizontalIcon className="size-4" />
                  Filtros avançados
                  {activeAdvancedFiltersCount ? (
                    <Badge className="ml-1 rounded-full bg-primary/15 px-2 py-0 text-primary">
                      {activeAdvancedFiltersCount}
                    </Badge>
                  ) : null}
                </Button>
              </SheetTrigger>
              <SheetContent className="w-full border-l border-border/60 sm:max-w-xl">
                <SheetHeader>
                  <SheetTitle>Filtros avançados</SheetTitle>
                  <SheetDescription>
                    {listing === "quitados"
                      ? "Refine o histórico de baixas por agente responsável e intervalo de datas."
                      : "Refine a fila por agente responsável e intervalo de vencimento."}
                  </SheetDescription>
                </SheetHeader>

                <div className="space-y-5 overflow-y-auto px-4 pb-4">
                  <div className="space-y-2">
                    <Label>Agente</Label>
                    <SearchableSelect
                      options={agentOptions}
                      value={draftFilters.agente}
                      onChange={(value) =>
                        setDraftFilters((current) => ({
                          ...current,
                          agente: value,
                        }))
                      }
                      placeholder="Todos os agentes"
                      searchPlaceholder="Buscar agente"
                      clearLabel="Todos os agentes"
                      className="rounded-2xl border-border/60 bg-background/60"
                    />
                  </div>
                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="space-y-2">
                      <Label>{listing === "quitados" ? "Baixado de" : "Vencimento de"}</Label>
                      <DatePicker
                        value={draftFilters.dataInicio}
                        onChange={(value) =>
                          setDraftFilters((current) => ({
                            ...current,
                            dataInicio: value,
                          }))
                        }
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>{listing === "quitados" ? "Baixado até" : "Vencimento até"}</Label>
                      <DatePicker
                        value={draftFilters.dataFim}
                        onChange={(value) =>
                          setDraftFilters((current) => ({
                            ...current,
                            dataFim: value,
                          }))
                        }
                      />
                    </div>
                  </div>
                </div>

                <SheetFooter>
                  <Button
                    variant="outline"
                    onClick={() => {
                      setDraftFilters({
                        agente: "",
                        dataInicio: undefined,
                        dataFim: undefined,
                      });
                      setAgente("");
                      setDataInicio(undefined);
                      setDataFim(undefined);
                      setFiltersOpen(false);
                    }}
                  >
                    Limpar
                  </Button>
                  <Button
                    onClick={() => {
                      setAgente(draftFilters.agente);
                      setDataInicio(draftFilters.dataInicio);
                      setDataFim(draftFilters.dataFim);
                      setFiltersOpen(false);
                    }}
                  >
                    Aplicar
                  </Button>
                </SheetFooter>
              </SheetContent>
            </Sheet>
            <Button variant="outline" onClick={resetFilters}>
              Limpar
            </Button>
          </div>
        </div>
      </section>

      {query.isLoading && !query.data ? (
        <div className="overflow-hidden rounded-[1.75rem] border border-border/60 bg-card/70">
          <div className="space-y-0 divide-y divide-border/40">
            {Array.from({ length: 6 }).map((_, index) => (
              <div key={index} className="flex items-center gap-4 px-5 py-4">
                <Skeleton className="size-4 shrink-0" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-4 w-48" />
                </div>
                <Skeleton className="h-5 w-28" />
                <Skeleton className="h-5 w-20" />
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-6 w-16" />
                <Skeleton className="h-5 w-20" />
                <Skeleton className="h-8 w-24" />
              </div>
            ))}
          </div>
        </div>
      ) : (
        <DataTable
          data={groups}
          columns={columns}
          renderExpanded={renderExpanded}
          currentPage={page}
          totalPages={Math.max(1, Math.ceil(totalCount / 50))}
          onPageChange={setPage}
          emptyMessage={
            listing === "quitados"
              ? "Nenhuma baixa manual encontrada para os filtros aplicados."
              : "Nenhuma parcela pendente de meses anteriores."
          }
        />
      )}

      <Dialog
        open={!!darBaixaState}
        onOpenChange={(open) => {
          if (!open) {
            setDarBaixaState(null);
          }
        }}
      >
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Registrar inadimplência</DialogTitle>
            <DialogDescription>
              {darBaixaState ? (
                <>
                  <strong>{darBaixaState.item.nome}</strong> -{" "}
                  {formatMonthYear(darBaixaState.item.referencia_mes)} -{" "}
                  {formatCurrency(darBaixaState.item.valor)}
                </>
              ) : null}
            </DialogDescription>
          </DialogHeader>

          {darBaixaState ? (
            <div className="space-y-4">
              <div className="space-y-2">
                <Label>Comprovante de pagamento *</Label>
                <FileUploadDropzone
                  accept={comprovanteAccept}
                  maxSize={10 * 1024 * 1024}
                  onUpload={(file) =>
                    setDarBaixaState((current) =>
                      current ? { ...current, comprovante: file ?? null } : current,
                    )
                  }
                  isProcessing={false}
                />
                {darBaixaState.comprovante ? (
                  <div className="flex items-center gap-2 rounded-xl bg-emerald-500/10 px-3 py-2 text-sm text-emerald-300">
                    <CheckCircleIcon className="size-4 shrink-0" />
                    {darBaixaState.comprovante.name}
                  </div>
                ) : null}
              </div>

              <div className="space-y-2">
                <Label>Valor pago (R$) *</Label>
                <Input
                  value={darBaixaState.valorPago}
                  onChange={(event) =>
                    setDarBaixaState((current) =>
                      current ? { ...current, valorPago: event.target.value } : current,
                    )
                  }
                  placeholder="0.00"
                  type="number"
                  step="0.01"
                  min="0"
                  className="rounded-2xl border-border/60 bg-card/60"
                />
              </div>

              <div className="space-y-2">
                <Label>Observação</Label>
                <Textarea
                  value={darBaixaState.observacao}
                  onChange={(event) =>
                    setDarBaixaState((current) =>
                      current ? { ...current, observacao: event.target.value } : current,
                    )
                  }
                  placeholder="Informações adicionais sobre o pagamento..."
                  className="min-h-24"
                />
              </div>
            </div>
          ) : null}

          <DialogFooter>
            <Button variant="outline" onClick={() => setDarBaixaState(null)}>
              Cancelar
            </Button>
            <Button
              variant="success"
              disabled={
                darBaixaMutation.isPending ||
                !darBaixaState?.comprovante ||
                !darBaixaState.valorPago
              }
              onClick={() => {
                if (!darBaixaState?.comprovante || !darBaixaState.valorPago) {
                  return;
                }
                if (!darBaixaState.item.parcela_id) {
                  toast.error("Esta linha não possui parcela vinculada para baixa manual.");
                  return;
                }
                darBaixaMutation.mutate({
                  parcelaId: darBaixaState.item.parcela_id,
                  comprovante: darBaixaState.comprovante,
                  valorPago: darBaixaState.valorPago,
                  observacao: darBaixaState.observacao,
                });
              }}
            >
              {darBaixaMutation.isPending ? (
                <>
                  <Spinner className="mr-2 size-4" />
                  Registrando...
                </>
              ) : (
                "Confirmar Baixa"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={!!inativarAssociadoState}
        onOpenChange={(open) => {
          if (!open) {
            setInativarAssociadoState(null);
          }
        }}
      >
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Inativar associado e baixar vencidas</DialogTitle>
            <DialogDescription>
              {inativarAssociadoState ? (
                <>
                  <strong>{inativarAssociadoState.group.nome}</strong> com{" "}
                  {inativarAssociadoState.group.total_parcelas} item(ns) na fila. As
                  parcelas vencidas com vínculo no sistema serão baixadas com o mesmo
                  comprovante.
                </>
              ) : null}
            </DialogDescription>
          </DialogHeader>

          {inativarAssociadoState ? (
            <div className="space-y-4">
              <div className="rounded-2xl border border-border/60 bg-card/60 px-4 py-3 text-sm">
                <p className="font-medium text-foreground">
                  Total listado: {formatCurrency(inativarAssociadoState.group.valor_total.toFixed(2))}
                </p>
                <p className="mt-1 text-muted-foreground">
                  Somente parcelas vencidas com `parcela_id` serão baixadas automaticamente.
                </p>
              </div>

              <div className="space-y-2">
                <Label>Comprovante de pagamento *</Label>
                <FileUploadDropzone
                  accept={comprovanteAccept}
                  maxSize={10 * 1024 * 1024}
                  onUpload={(file) =>
                    setInativarAssociadoState((current) =>
                      current ? { ...current, comprovante: file ?? null } : current,
                    )
                  }
                  isProcessing={false}
                />
                {inativarAssociadoState.comprovante ? (
                  <div className="flex items-center gap-2 rounded-xl bg-emerald-500/10 px-3 py-2 text-sm text-emerald-300">
                    <CheckCircleIcon className="size-4 shrink-0" />
                    {inativarAssociadoState.comprovante.name}
                  </div>
                ) : null}
              </div>

              <div className="space-y-2">
                <Label>Observação</Label>
                <Textarea
                  value={inativarAssociadoState.observacao}
                  onChange={(event) =>
                    setInativarAssociadoState((current) =>
                      current ? { ...current, observacao: event.target.value } : current,
                    )
                  }
                  placeholder="Motivo da inativação e contexto do pagamento..."
                  className="min-h-24"
                />
              </div>
            </div>
          ) : null}

          <DialogFooter>
            <Button variant="outline" onClick={() => setInativarAssociadoState(null)}>
              Cancelar
            </Button>
            <Button
              variant="destructive"
              disabled={
                inativarAssociadoMutation.isPending ||
                !inativarAssociadoState?.comprovante ||
                !inativarAssociadoState.group.possuiParcelaBaixavel
              }
              onClick={() => {
                if (!inativarAssociadoState?.comprovante) {
                  return;
                }
                inativarAssociadoMutation.mutate({
                  associadoId: inativarAssociadoState.group.associado_id,
                  comprovante: inativarAssociadoState.comprovante,
                  observacao: inativarAssociadoState.observacao,
                });
              }}
            >
              {inativarAssociadoMutation.isPending ? (
                <>
                  <Spinner className="mr-2 size-4" />
                  Inativando...
                </>
              ) : (
                "Confirmar inativação"
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
