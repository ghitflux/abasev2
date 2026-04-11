"use client";

import * as React from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { format } from "date-fns";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CalendarCheck2Icon,
  HandCoinsIcon,
  PencilLineIcon,
  PlusIcon,
  ReceiptTextIcon,
  RotateCcwIcon,
  SlidersHorizontalIcon,
  Trash2Icon,
  WalletCardsIcon,
} from "lucide-react";
import { toast } from "sonner";

import type {
  DevolucaoAssociadoItem,
  DevolucaoContratoItem,
  DevolucaoKpis,
  PaginatedResponse,
} from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import { buildBackendFileUrl } from "@/lib/backend-files";
import { usePermissions } from "@/hooks/use-permissions";
import { formatCurrency, formatDate, formatMonthYear } from "@/lib/formatters";
import {
  describeReportScope,
  exportRouteReport,
  fetchAllPaginatedRows,
  filterRowsByReportScope,
} from "@/lib/reports";
import CalendarCompetencia from "@/components/custom/calendar-competencia";
import StatusBadge from "@/components/custom/status-badge";
import DevolucaoFormDialog, {
  type DevolucaoFormState,
} from "@/components/tesouraria/devolucao-form-dialog";
import DuplicidadesFinanceirasPanel from "@/components/tesouraria/duplicidades-financeiras-panel";
import DataTable, {
  type DataTableColumn,
} from "@/components/shared/data-table";
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
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";

type ListingTab = "duplicidades" | "historico";
type RegisterResponse = PaginatedResponse<DevolucaoContratoItem> & {
  kpis: DevolucaoKpis;
};
type HistoryResponse = PaginatedResponse<DevolucaoAssociadoItem> & {
  kpis: DevolucaoKpis;
};

function useDevolucaoContratosQuery({
  page,
  search,
  competencia,
  estado,
  fluxo,
  enabled = true,
}: {
  page: number;
  search: string;
  competencia?: Date;
  estado: string;
  fluxo?: string;
  enabled?: boolean;
}) {
  return useQuery({
    queryKey: [
      "tesouraria-devolucoes",
      "contratos",
      page,
      search,
      competencia?.toISOString(),
      estado,
      fluxo,
    ],
    enabled,
    queryFn: () =>
      apiFetch<RegisterResponse>("tesouraria/devolucoes/contratos", {
        query: {
          page,
          page_size: 20,
          search: search || undefined,
          competencia: competencia ? format(competencia, "yyyy-MM") : undefined,
          estado: estado !== "todos" ? estado : undefined,
          fluxo,
        },
      }),
  });
}

function buildCreateState(
  row: DevolucaoContratoItem | null,
  defaultTipo?: DevolucaoFormState["tipo"],
): DevolucaoFormState {
  return {
    mode: "create",
    devolucaoId: null,
    row,
    tipo:
      row?.tipo_sugerido === "desistencia_pos_liquidacao"
        ? "desistencia_pos_liquidacao"
        : (defaultTipo ?? "pagamento_indevido"),
    dataDevolucao: new Date(),
    quantidadeParcelas: 1,
    valor: null,
    motivo: "",
    competenciaReferencia: undefined,
    comprovantePrincipal: null,
    comprovantesExtras: [],
    existingComprovantePrincipal: null,
    existingAnexosExtras: [],
    removerAnexosIds: [],
  };
}

function buildEditState(row: DevolucaoAssociadoItem): DevolucaoFormState {
  const primaryAttachment = row.anexos[0] ?? row.comprovante ?? null;
  const extraAttachments = row.anexos.slice(1);

  return {
    mode: "edit",
    devolucaoId: row.devolucao_id,
    row: {
      id: row.contrato_id,
      contrato_id: row.contrato_id,
      associado_id: row.associado_id,
      nome: row.nome,
      cpf_cnpj: row.cpf_cnpj,
      matricula: row.matricula,
      agente_nome: row.agente_nome,
      contrato_codigo: row.contrato_codigo,
      status_contrato: row.status_contrato,
      data_contrato: row.data_devolucao,
      mes_averbacao: row.competencia_referencia,
      tipo_sugerido:
        row.tipo === "desistencia_pos_liquidacao" ? row.tipo : undefined,
    },
    tipo: row.tipo as DevolucaoFormState["tipo"],
    dataDevolucao: row.data_devolucao
      ? new Date(`${row.data_devolucao}T12:00:00`)
      : undefined,
    quantidadeParcelas: row.quantidade_parcelas,
    valor: Math.round(Number.parseFloat(row.valor) * 100),
    motivo: row.motivo,
    competenciaReferencia: row.competencia_referencia
      ? new Date(`${row.competencia_referencia}T12:00:00`)
      : undefined,
    comprovantePrincipal: null,
    comprovantesExtras: [],
    existingComprovantePrincipal: primaryAttachment,
    existingAnexosExtras: extraAttachments,
    removerAnexosIds: [],
  };
}

function useDevolucaoHistoricoQuery({
  page,
  search,
  competencia,
  tipo,
  status,
  fluxo,
}: {
  page: number;
  search: string;
  competencia?: Date;
  tipo: string;
  status: string;
  fluxo?: string;
}) {
  return useQuery({
    queryKey: [
      "tesouraria-devolucoes",
      "historico",
      page,
      search,
      competencia?.toISOString(),
      tipo,
      status,
      fluxo,
    ],
    queryFn: () =>
      apiFetch<HistoryResponse>("tesouraria/devolucoes", {
        query: {
          page,
          page_size: 20,
          search: search || undefined,
          competencia: competencia ? format(competencia, "yyyy-MM") : undefined,
          tipo: tipo !== "todos" ? tipo : undefined,
          status: status !== "todos" ? status : undefined,
          fluxo,
        },
      }),
  });
}

export default function DevolucoesAssociadoPage() {
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const { hasRole, hasAnyRole } = usePermissions();
  const isAdmin = hasRole("ADMIN");
  const canEdit = hasAnyRole(["ADMIN", "COORDENADOR", "TESOUREIRO"]);
  const initialTab = React.useMemo<ListingTab>(() => {
    const requestedTab = searchParams.get("tab");
    if (requestedTab === "duplicidades") return "duplicidades";
    if (requestedTab === "historico") return "historico";
    return "historico";
  }, [searchParams]);

  const [tab, setTab] = React.useState<ListingTab>(initialTab);
  const [page, setPage] = React.useState(1);
  const [search, setSearch] = React.useState("");
  const [competencia, setCompetencia] = React.useState<Date | undefined>();
  const [estado, setEstado] = React.useState("todos");
  const [tipo, setTipo] = React.useState("todos");
  const [status, setStatus] = React.useState("todos");
  const [filtersOpen, setFiltersOpen] = React.useState(false);
  const [draftCompetencia, setDraftCompetencia] = React.useState<
    Date | undefined
  >();
  const [draftEstado, setDraftEstado] = React.useState("todos");
  const [draftTipo, setDraftTipo] = React.useState("todos");
  const [draftStatus, setDraftStatus] = React.useState("todos");
  const [isExporting, setIsExporting] = React.useState(false);
  const [registerState, setRegisterState] =
    React.useState<DevolucaoFormState | null>(null);
  const [registerAllowsContractSelection, setRegisterAllowsContractSelection] =
    React.useState(false);
  const [registerContractSearch, setRegisterContractSearch] =
    React.useState("");
  const [reverterTarget, setReverterTarget] =
    React.useState<DevolucaoAssociadoItem | null>(null);
  const [motivoReversao, setMotivoReversao] = React.useState("");
  const [deleteTarget, setDeleteTarget] =
    React.useState<DevolucaoAssociadoItem | null>(null);
  const [motivoExclusao, setMotivoExclusao] = React.useState("");

  React.useEffect(() => {
    setTab(initialTab);
  }, [initialTab]);

  React.useEffect(() => {
    setPage(1);
  }, [tab, search, competencia, estado, tipo, status]);

  const historicoQuery = useDevolucaoHistoricoQuery({
    page,
    search,
    competencia,
    tipo,
    status,
    fluxo: undefined,
  });
  const manualContractsQuery = useDevolucaoContratosQuery({
    page: 1,
    search: registerContractSearch,
    competencia,
    estado,
    fluxo: undefined,
    enabled: Boolean(registerState && registerAllowsContractSelection),
  });

  const query = historicoQuery;
  const totalCount = query.data?.count ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalCount / 20));

  const handleExport = React.useCallback(
    async (exportFilters: ReportExportFilters, formatValue: "pdf" | "xlsx") => {
      const { scope, referenceDate } = exportFilters;

      setIsExporting(true);
      try {
        if (tab === "historico") {
          const sourceQuery = {
            search: search || undefined,
            competencia: competencia
              ? format(competencia, "yyyy-MM")
              : undefined,
            tipo: tipo !== "todos" ? tipo : undefined,
            status: status !== "todos" ? status : undefined,
          };
          const fetchedRows =
            await fetchAllPaginatedRows<DevolucaoAssociadoItem>({
              sourcePath: "tesouraria/devolucoes",
              sourceQuery,
            });
          const rows = filterRowsByReportScope({
            rows: fetchedRows,
            scope,
            referenceDate,
            getCandidates: (row) => [
              row.data_devolucao,
              row.competencia_referencia,
            ],
          }).map((row) => ({
            nome: row.nome,
            cpf_cnpj: row.cpf_cnpj,
            matricula: row.matricula,
            agente_nome: row.agente_nome,
            contrato_codigo: row.contrato_codigo,
            tipo: row.tipo,
            status_devolucao: row.status_devolucao,
            data_devolucao: row.data_devolucao,
            quantidade_parcelas: row.quantidade_parcelas,
            valor: row.valor,
            competencia_referencia: row.competencia_referencia ?? "",
            motivo: row.motivo,
          }));

          await exportRouteReport({
            route: "/tesouraria/devolucoes",
            format: formatValue,
            rows,
            filters: {
              ...sourceQuery,
              aba: tab,
              ...describeReportScope(scope, referenceDate),
            },
          });
          return;
        }

        const sourceQuery = {
          search: search || undefined,
          competencia: competencia ? format(competencia, "yyyy-MM") : undefined,
          estado: estado !== "todos" ? estado : undefined,
          fluxo: undefined,
        };
        const fetchedRows = await fetchAllPaginatedRows<DevolucaoContratoItem>({
          sourcePath: "tesouraria/devolucoes/contratos",
          sourceQuery,
        });
        const rows = filterRowsByReportScope({
          rows: fetchedRows,
          scope,
          referenceDate,
          getCandidates: (row) => [row.data_contrato, row.mes_averbacao],
        }).map((row) => ({
          nome: row.nome,
          cpf_cnpj: row.cpf_cnpj,
          matricula: row.matricula,
          agente_nome: row.agente_nome,
          contrato_codigo: row.contrato_codigo,
          status_contrato: row.status_contrato,
          data_contrato: row.data_contrato,
          mes_averbacao: row.mes_averbacao ?? "",
          tipo_sugerido: row.tipo_sugerido ?? "",
        }));

        await exportRouteReport({
          route: "/tesouraria/devolucoes",
          format: formatValue,
          rows,
          filters: {
            ...sourceQuery,
            aba: tab,
            ...describeReportScope(scope, referenceDate),
          },
        });
      } catch (error) {
        toast.error(
          error instanceof Error
            ? error.message
            : "Falha ao exportar devoluções.",
        );
      } finally {
        setIsExporting(false);
      }
    },
    [competencia, estado, search, status, tab, tipo],
  );

  const registrarMutation = useMutation({
    mutationFn: async (payload: DevolucaoFormState) => {
      if (!payload.row) {
        throw new Error(
          "Selecione um contrato elegível antes de registrar a devolução.",
        );
      }
      const formData = new FormData();
      formData.append("tipo", payload.tipo);
      formData.append(
        "data_devolucao",
        format(payload.dataDevolucao as Date, "yyyy-MM-dd"),
      );
      formData.append(
        "quantidade_parcelas",
        String(payload.quantidadeParcelas),
      );
      formData.append("valor", ((payload.valor ?? 0) / 100).toFixed(2));
      formData.append("motivo", payload.motivo);
      if (payload.comprovantePrincipal) {
        formData.append("comprovantes", payload.comprovantePrincipal);
      }
      payload.comprovantesExtras.forEach((arquivo) => {
        formData.append("comprovantes", arquivo);
      });
      if (payload.competenciaReferencia) {
        formData.append(
          "competencia_referencia",
          format(payload.competenciaReferencia, "yyyy-MM-01"),
        );
      }
      return apiFetch<DevolucaoAssociadoItem>(
        `tesouraria/devolucoes/contratos/${payload.row.contrato_id}/registrar/`,
        {
          method: "POST",
          formData,
        },
      );
    },
    onSuccess: () => {
      toast.success("Devolução registrada com sucesso.");
      setRegisterState(null);
      setRegisterAllowsContractSelection(false);
      setRegisterContractSearch("");
      setTab("historico");
      void queryClient.invalidateQueries({
        queryKey: ["tesouraria-devolucoes"],
      });
      void queryClient.invalidateQueries({ queryKey: ["associados"] });
      void queryClient.invalidateQueries({ queryKey: ["contratos"] });
    },
    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : "Não foi possível registrar a devolução.",
      );
    },
  });

  const editarMutation = useMutation({
    mutationFn: async (payload: DevolucaoFormState) => {
      if (!payload.row || !payload.devolucaoId) {
        throw new Error(
          "A devolução precisa permanecer vinculada a um contrato.",
        );
      }
      const formData = new FormData();
      formData.append("tipo", payload.tipo);
      formData.append(
        "data_devolucao",
        format(payload.dataDevolucao as Date, "yyyy-MM-dd"),
      );
      formData.append(
        "quantidade_parcelas",
        String(payload.quantidadeParcelas),
      );
      formData.append("valor", ((payload.valor ?? 0) / 100).toFixed(2));
      formData.append("motivo", payload.motivo);
      if (payload.competenciaReferencia) {
        formData.append(
          "competencia_referencia",
          format(payload.competenciaReferencia, "yyyy-MM-01"),
        );
      }
      if (payload.comprovantePrincipal) {
        formData.append("comprovante", payload.comprovantePrincipal);
      }
      payload.comprovantesExtras.forEach((arquivo) => {
        formData.append("novos_comprovantes", arquivo);
      });
      payload.removerAnexosIds.forEach((anexoId) => {
        formData.append("remover_anexos_ids", String(anexoId));
      });

      return apiFetch<DevolucaoAssociadoItem>(
        `tesouraria/devolucoes/${payload.devolucaoId}/`,
        {
          method: "PATCH",
          formData,
        },
      );
    },
    onSuccess: () => {
      toast.success("Devolução atualizada com sucesso.");
      setRegisterState(null);
      setRegisterAllowsContractSelection(false);
      setRegisterContractSearch("");
      void queryClient.invalidateQueries({
        queryKey: ["tesouraria-devolucoes"],
      });
      void queryClient.invalidateQueries({ queryKey: ["associados"] });
      void queryClient.invalidateQueries({ queryKey: ["contratos"] });
    },
    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : "Não foi possível atualizar a devolução.",
      );
    },
  });

  const reverterMutation = useMutation({
    mutationFn: async ({ id, motivo }: { id: number; motivo: string }) =>
      apiFetch<DevolucaoAssociadoItem>(
        `tesouraria/devolucoes/${id}/reverter/`,
        {
          method: "POST",
          body: { motivo_reversao: motivo },
        },
      ),
    onSuccess: () => {
      toast.success("Devolução revertida com sucesso.");
      setReverterTarget(null);
      setMotivoReversao("");
      void queryClient.invalidateQueries({
        queryKey: ["tesouraria-devolucoes"],
      });
      void queryClient.invalidateQueries({ queryKey: ["associados"] });
      void queryClient.invalidateQueries({ queryKey: ["contratos"] });
    },
    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : "Não foi possível reverter a devolução.",
      );
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async ({ id, motivo }: { id: number; motivo: string }) =>
      apiFetch<{ message: string }>(`tesouraria/devolucoes/${id}/excluir/`, {
        method: "POST",
        body: { motivo_exclusao: motivo },
      }),
    onSuccess: () => {
      toast.success("Registro de devolução excluído com sucesso.");
      setDeleteTarget(null);
      setMotivoExclusao("");
      void queryClient.invalidateQueries({
        queryKey: ["tesouraria-devolucoes"],
      });
      void queryClient.invalidateQueries({ queryKey: ["associados"] });
      void queryClient.invalidateQueries({ queryKey: ["contratos"] });
    },
    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : "Não foi possível excluir a devolução.",
      );
    },
  });


  const historyColumns = React.useMemo<
    DataTableColumn<DevolucaoAssociadoItem>[]
  >(
    () => [
      {
        id: "associado",
        header: "Associado",
        cell: (row) => (
          <div>
            <p className="font-medium">{row.nome}</p>
            <p className="text-xs text-muted-foreground">
              {row.cpf_cnpj} · {row.matricula || "Sem matrícula"}
            </p>
          </div>
        ),
      },
      {
        id: "tipo",
        header: "Tipo / Competência",
        cell: (row) => (
          <div className="space-y-1">
            <StatusBadge status={row.status_devolucao} />
            <p className="text-sm capitalize text-foreground">
              {row.tipo.replaceAll("_", " ")}
            </p>
            <p className="text-xs text-muted-foreground">
              {row.competencia_referencia
                ? `Competência ${formatMonthYear(row.competencia_referencia)}`
                : "Sem competência vinculada"}
            </p>
          </div>
        ),
      },
      {
        id: "valor",
        header: "Valor / Parcelas",
        cell: (row) => (
          <div>
            <p className="font-semibold">{formatCurrency(row.valor)}</p>
            <p className="text-xs text-muted-foreground">
              {row.quantidade_parcelas} parcela(s) ·{" "}
              {formatDate(row.data_devolucao)}
            </p>
          </div>
        ),
      },
      {
        id: "comprovante",
        header: "Anexos",
        cell: (row) =>
          row.anexos.length ? (
            <div className="space-y-1">
              {row.anexos.slice(0, 2).map((anexo) => (
                <a
                  key={`${row.id}-${anexo.arquivo_referencia}-${anexo.nome}`}
                  href={buildBackendFileUrl(anexo.url)}
                  target="_blank"
                  rel="noreferrer"
                  className="block text-sm text-primary underline-offset-4 hover:underline"
                >
                  {anexo.nome}
                </a>
              ))}
              {row.anexos.length > 2 ? (
                <p className="text-xs text-muted-foreground">
                  + {row.anexos.length - 2} anexo(s)
                </p>
              ) : null}
            </div>
          ) : (
            <span className="text-sm text-muted-foreground">Sem anexo</span>
          ),
      },
      {
        id: "acoes",
        header: "Ações",
        cellClassName: "w-[220px]",
        cell: (row) => (
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="outline">
              <Link href={`/associados/${row.associado_id}`}>Ver cadastro</Link>
            </Button>
            {canEdit && row.status_devolucao === "registrada" ? (
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  setRegisterAllowsContractSelection(false);
                  setRegisterContractSearch("");
                  setRegisterState(buildEditState(row));
                }}
              >
                <PencilLineIcon className="mr-1.5 size-3.5" />
                Editar
              </Button>
            ) : null}
            {isAdmin && row.pode_reverter ? (
              <Button
                size="sm"
                variant="outline"
                onClick={() => setReverterTarget(row)}
              >
                <RotateCcwIcon className="mr-1.5 size-3.5" />
                Reverter
              </Button>
            ) : null}
            {isAdmin ? (
              <Button
                size="sm"
                variant="destructive"
                onClick={() => {
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
    [canEdit, isAdmin],
  );

  const historyRows = (historicoQuery.data?.results ??
    []) as DevolucaoAssociadoItem[];
  const kpis = query.data?.kpis;
  const isDuplicidadeTab = tab === "duplicidades";
  const activeFiltersCount =
    Number(Boolean(competencia)) +
    Number(tipo !== "todos") +
    Number(status !== "todos");

  return (
    <div className="space-y-6">
      <section className="rounded-[1.75rem] border border-border/60 bg-card/70 p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-1">
            <h1 className="text-3xl font-semibold">Devoluções</h1>
            <p className="text-sm text-muted-foreground">
              Registre devoluções por pagamento ou desconto indevido e acompanhe
              o histórico operacional e o histórico formal de devoluções sem
              alterar parcelas, ciclos ou a baixa financeira do contrato.
            </p>
          </div>
          <ReportExportDialog
            disabled={isExporting || isDuplicidadeTab}
            label={isExporting ? "Exportando..." : "Exportar"}
            onExport={handleExport}
          />
        </div>
      </section>

      {!isDuplicidadeTab ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <StatsCard
            title="Registros"
            value={String(kpis?.total_registros ?? 0)}
            delta="Histórico de devolução no recorte"
            icon={ReceiptTextIcon}
            tone="neutral"
          />
          <StatsCard
            title="Associados impactados"
            value={String(kpis?.associados_impactados ?? 0)}
            delta="Associados distintos no recorte"
            icon={WalletCardsIcon}
            tone="neutral"
          />
          <StatsCard
            title="Valor total"
            value={formatCurrency(kpis?.valor_total ?? "0")}
            delta={`${kpis?.registradas ?? 0} devolução(ões) ativa(s)`}
            icon={HandCoinsIcon}
            tone="positive"
          />
          <StatsCard
            title="Revertidas"
            value={String(kpis?.revertidas ?? 0)}
            delta="Registros revertidos por administração"
            icon={CalendarCheck2Icon}
            tone="warning"
          />
        </div>
      ) : null}

      <Tabs
        value={tab}
        onValueChange={(value) => setTab(value as ListingTab)}
        className="space-y-6"
      >
        <TabsList variant="line" className="justify-start">
          <TabsTrigger value="duplicidades">Histórico geral</TabsTrigger>
          <TabsTrigger value="historico">Histórico de devolução</TabsTrigger>
        </TabsList>

        {!isDuplicidadeTab ? (
          <div className="grid gap-4 rounded-[1.75rem] border border-border/60 bg-card/70 p-6 lg:grid-cols-[minmax(0,1fr)_auto]">
            <div className="space-y-2">
              <Label htmlFor="devolucao-search">Buscar</Label>
              <Input
                id="devolucao-search"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Nome, CPF, matrícula, contrato ou agente"
                className="h-11 rounded-xl border-border/60 bg-background/50"
              />
            </div>
            <div className="flex items-end justify-end">
              <div className="flex flex-wrap items-end justify-end gap-3">
                {tab === "historico" ? (
                  <Button
                    className="h-11 rounded-xl"
                    onClick={() => {
                      setRegisterAllowsContractSelection(true);
                      setRegisterContractSearch("");
                      setRegisterState(buildCreateState(null, "pagamento_indevido"));
                    }}
                  >
                    <PlusIcon className="size-4" />
                    Lançar devolução manual
                  </Button>
                ) : null}
                <Sheet
                  open={filtersOpen}
                  onOpenChange={(open) => {
                    if (open) {
                      setDraftCompetencia(competencia);
                      setDraftEstado(estado);
                      setDraftTipo(tipo);
                      setDraftStatus(status);
                    }
                    setFiltersOpen(open);
                  }}
                >
                  <SheetTrigger asChild>
                    <Button variant="outline" className="h-11 rounded-xl">
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
                        Ajuste competência e filtros específicos para registrar
                        ou revisar devoluções.
                      </SheetDescription>
                    </SheetHeader>

                    <div className="space-y-5 overflow-y-auto px-4 pb-4">
                      <div className="space-y-2">
                        <Label>Competência</Label>
                        <CalendarCompetencia
                          value={draftCompetencia}
                          onChange={setDraftCompetencia}
                        />
                      </div>

                      <div className="space-y-2">
                        <Label>Tipo</Label>
                        <Select
                          value={draftTipo}
                          onValueChange={setDraftTipo}
                        >
                          <SelectTrigger className="h-11 rounded-xl border-border/60 bg-background/50">
                            <SelectValue placeholder="Todos" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="todos">Todos</SelectItem>
                            <SelectItem value="pagamento_indevido">
                              Pagamento indevido
                            </SelectItem>
                            <SelectItem value="desconto_indevido">
                              Desconto indevido
                            </SelectItem>
                            <SelectItem value="desistencia_pos_liquidacao">
                              Desistência pós-liquidação
                            </SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-2">
                        <Label>Status</Label>
                        <Select
                          value={draftStatus}
                          onValueChange={setDraftStatus}
                        >
                          <SelectTrigger className="h-11 rounded-xl border-border/60 bg-background/50">
                            <SelectValue placeholder="Todos" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="todos">Todos</SelectItem>
                            <SelectItem value="registrada">
                              Registrada
                            </SelectItem>
                            <SelectItem value="revertida">
                              Revertida
                            </SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </div>

                    <SheetFooter>
                      <Button
                        variant="outline"
                        onClick={() => {
                          setDraftCompetencia(undefined);
                          setDraftEstado("todos");
                          setDraftTipo("todos");
                          setDraftStatus("todos");
                          setCompetencia(undefined);
                          setEstado("todos");
                          setTipo("todos");
                          setStatus("todos");
                          setFiltersOpen(false);
                        }}
                      >
                        Limpar
                      </Button>
                      <Button
                        onClick={() => {
                          setCompetencia(draftCompetencia);
                          setEstado(draftEstado);
                          setTipo(draftTipo);
                          setStatus(draftStatus);
                          setFiltersOpen(false);
                        }}
                      >
                        Aplicar
                      </Button>
                    </SheetFooter>
                  </SheetContent>
                </Sheet>
              </div>
            </div>
          </div>
        ) : null}

        <TabsContent value="duplicidades" className="mt-0">
          <DuplicidadesFinanceirasPanel emptyMessage="Nenhum evento operacional pendente ou histórico encontrado para a tesouraria." />
        </TabsContent>

        <TabsContent value="historico" className="mt-0">
          <DataTable
            columns={historyColumns}
            data={historyRows}
            loading={historicoQuery.isLoading}
            currentPage={page}
            totalPages={totalPages}
            onPageChange={setPage}
            pageSize={20}
            emptyMessage="Nenhuma devolução registrada no histórico de devolução."
          />
        </TabsContent>
      </Tabs>

      <DevolucaoFormDialog
        open={!!registerState}
        value={registerState}
        setValue={setRegisterState}
        onClose={() => {
          setRegisterState(null);
          setRegisterAllowsContractSelection(false);
          setRegisterContractSearch("");
        }}
        onSubmit={() => {
          if (!registerState) {
            return;
          }
          if (registerState.mode === "edit") {
            editarMutation.mutate(registerState);
            return;
          }
          registrarMutation.mutate(registerState);
        }}
        isSubmitting={registrarMutation.isPending || editarMutation.isPending}
        allowContractSelection={registerAllowsContractSelection}
        contractSearch={registerContractSearch}
        onContractSearchChange={setRegisterContractSearch}
        contractOptions={manualContractsQuery.data?.results ?? []}
        contractSearchLoading={manualContractsQuery.isFetching}
      />

      <Dialog
        open={!!reverterTarget}
        onOpenChange={(open) => !open && setReverterTarget(null)}
      >
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Reverter devolução</DialogTitle>
            <DialogDescription>
              A reversão mantém o histórico e marca o registro como revertido.
            </DialogDescription>
          </DialogHeader>
          {reverterTarget ? (
            <div className="space-y-4">
              <div className="rounded-2xl border border-border/60 bg-background/40 p-4">
                <p className="font-medium">{reverterTarget.nome}</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  {reverterTarget.contrato_codigo} ·{" "}
                  {formatCurrency(reverterTarget.valor)}
                </p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="motivo-reversao">Motivo da reversão</Label>
                <Textarea
                  id="motivo-reversao"
                  value={motivoReversao}
                  onChange={(event) => setMotivoReversao(event.target.value)}
                  className="min-h-[120px] rounded-2xl border-border/60 bg-background/50"
                  placeholder="Descreva o motivo da reversão."
                />
              </div>
            </div>
          ) : null}
          <DialogFooter>
            <Button
              variant="ghost"
              onClick={() => {
                setReverterTarget(null);
                setMotivoReversao("");
              }}
            >
              Cancelar
            </Button>
            <Button
              variant="outline"
              disabled={
                !motivoReversao.trim() ||
                reverterMutation.isPending ||
                !reverterTarget
              }
              onClick={() =>
                reverterTarget &&
                reverterMutation.mutate({
                  id: reverterTarget.devolucao_id,
                  motivo: motivoReversao,
                })
              }
            >
              Reverter
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
            <DialogTitle>Excluir devolução</DialogTitle>
            <DialogDescription>
              {deleteTarget ? (
                <>
                  O registro de devolução de{" "}
                  <strong>{deleteTarget.nome}</strong> será removido do
                  histórico ativo da tesouraria.
                </>
              ) : null}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 rounded-2xl border border-border/60 bg-card/60 p-4">
            {deleteTarget ? (
              <>
                <div className="space-y-1 text-sm">
                  <p className="font-medium">
                    {formatCurrency(deleteTarget.valor)} ·{" "}
                    {deleteTarget.tipo.replaceAll("_", " ")}
                  </p>
                  <p className="text-muted-foreground">
                    {deleteTarget.quantidade_parcelas} parcela(s) ·{" "}
                    {formatDate(deleteTarget.data_devolucao)}
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
                !deleteTarget ||
                !motivoExclusao.trim()
              }
              onClick={() => {
                if (!deleteTarget || !motivoExclusao.trim()) {
                  return;
                }
                deleteMutation.mutate({
                  id: deleteTarget.id,
                  motivo: motivoExclusao.trim(),
                });
              }}
            >
              Excluir devolução
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
