"use client";

import * as React from "react";
import { format } from "date-fns";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2Icon,
  Clock3Icon,
  HandCoinsIcon,
  SlidersHorizontalIcon,
  Trash2Icon,
  XCircleIcon,
} from "lucide-react";
import { toast } from "sonner";

import type {
  ComprovanteResumo,
  PaginatedResponse,
  RefinanciamentoItem,
  RefinanciamentoResumo,
  SimpleUser,
} from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import { buildBackendFileUrl } from "@/lib/backend-files";
import { formatCurrency, formatDateTime, formatMonthYear } from "@/lib/formatters";
import {
  describeReportScope,
  exportRouteReport,
  fetchAllPaginatedRows,
  filterRowsByReportScope,
} from "@/lib/reports";
import DatePicker from "@/components/custom/date-picker";
import StatusBadge from "@/components/custom/status-badge";
import AssociadoDetailsDialog from "@/components/associados/associado-details-dialog";
import CopySnippet from "@/components/shared/copy-snippet";
import DataTable, { type DataTableColumn } from "@/components/shared/data-table";
import ReportExportDialog, {
  type ReportExportFilters,
} from "@/components/shared/report-export-dialog";
import StatsCard from "@/components/shared/stats-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
import { usePermissions } from "@/hooks/use-permissions";

type AgentFilterUser = SimpleUser & {
  email?: string;
  primary_role?: string | null;
};

const PENDING_STATUS = ["aprovado_para_renovacao"];
const EFETIVADO_STATUS = ["efetivado"];
const CANCELADO_STATUS = ["bloqueado", "revertido", "desativado"];

function toIsoDate(value?: Date) {
  return value ? format(value, "yyyy-MM-dd") : undefined;
}

function CompactUploadButton({
  id,
  label,
  existingUrl,
  existingReference,
  existingReferenceType,
  existingName,
  draftFile,
  onSelect,
  onClear,
  disabled = false,
}: {
  id: string;
  label: string;
  existingUrl?: string;
  existingReference?: string;
  existingReferenceType?: string;
  existingName?: string;
  draftFile?: File;
  onSelect?: (file: File) => void;
  onClear?: () => void;
  disabled?: boolean;
}) {
  const hasReferenceOnly = Boolean(existingReference && !existingUrl);
  const isLegacyReference = existingReferenceType === "legado_sem_arquivo";
  return (
    <div className="flex min-w-[14rem] items-center gap-2 rounded-xl border border-border/60 bg-background/40 p-2.5">
      <div className="min-w-0 flex-1">
        <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-muted-foreground">
          {label}
        </p>
        <p className="truncate text-xs text-foreground">
          {draftFile?.name ||
            existingName ||
            (hasReferenceOnly
              ? isLegacyReference
                ? "Arquivo legado vinculado"
                : "Arquivo vinculado por referência"
              : "Sem anexo")}
        </p>
      </div>
      {existingUrl ? (
        <Button asChild size="sm" variant="outline">
          <a href={buildBackendFileUrl(existingUrl)} target="_blank" rel="noreferrer">
            Ver
          </a>
        </Button>
      ) : hasReferenceOnly ? (
        isLegacyReference ? (
          <Badge className="rounded-full bg-amber-500/15 text-amber-200">Legado</Badge>
        ) : (
          <Badge className="rounded-full bg-sky-500/15 text-sky-200">Referência</Badge>
        )
      ) : null}
      {onSelect ? (
        <label className="cursor-pointer">
          <input
            type="file"
            accept=".pdf,.png,.jpg,.jpeg"
            className="hidden"
            disabled={disabled}
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) {
                onSelect(file);
              }
              event.currentTarget.value = "";
            }}
            id={id}
          />
          <Button asChild size="sm" variant={draftFile || existingName ? "outline" : "secondary"}>
            <span>{draftFile || existingName || existingReference ? "Trocar" : "Anexar"}</span>
          </Button>
        </label>
      ) : null}
      {draftFile && onClear ? (
        <Button size="icon-sm" variant="ghost" onClick={onClear}>
          <Trash2Icon className="size-4" />
        </Button>
      ) : null}
    </div>
  );
}

function findComprovanteByTipo(
  comprovantes: ComprovanteResumo[],
  tipo: string,
): ComprovanteResumo | undefined {
  return comprovantes.find((item) => item.tipo === tipo);
}

function resolveRenewalAttachments(row: RefinanciamentoItem) {
  return {
    termoAgente: findComprovanteByTipo(row.comprovantes, "termo_antecipacao"),
    comprovanteAssociado: findComprovanteByTipo(
      row.comprovantes,
      "comprovante_pagamento_associado",
    ),
    comprovanteAgente: findComprovanteByTipo(
      row.comprovantes,
      "comprovante_pagamento_agente",
    ),
  };
}

export default function TesourariaRefinanciamentosPage() {
  const { hasAnyRole } = usePermissions();
  const canMutate = hasAnyRole(["ADMIN", "TESOUREIRO"]);
  const queryClient = useQueryClient();
  const [search, setSearch] = React.useState("");
  const [isExporting, setIsExporting] = React.useState(false);

  const agentesQuery = useQuery({
    queryKey: ["refinanciamentos-agentes"],
    queryFn: () => apiFetch<AgentFilterUser[]>("tesouraria/contratos/agentes"),
    staleTime: 5 * 60 * 1000,
  });

  const agentOptions = React.useMemo(
    () =>
      (agentesQuery.data ?? []).map((item) => ({
        value: String(item.id),
        label: [
          item.full_name || item.email || `Usuário ${item.id}`,
          item.primary_role || null,
        ]
          .filter(Boolean)
          .join(" · "),
      })),
    [agentesQuery.data],
  );
  const [filtersOpen, setFiltersOpen] = React.useState(false);
  const [dataInicio, setDataInicio] = React.useState<Date>();
  const [dataFim, setDataFim] = React.useState<Date>();
  const [draftDataInicio, setDraftDataInicio] = React.useState<Date>();
  const [draftDataFim, setDraftDataFim] = React.useState<Date>();
  const [pagePending, setPagePending] = React.useState(1);
  const [pageEfetivadas, setPageEfetivadas] = React.useState(1);
  const [pageCanceladas, setPageCanceladas] = React.useState(1);
  const [detailAssociadoId, setDetailAssociadoId] = React.useState<number | null>(null);

  React.useEffect(() => {
    setPagePending(1);
    setPageEfetivadas(1);
    setPageCanceladas(1);
  }, [search, dataInicio, dataFim]);

  const pendingQuery = useQuery({
    queryKey: [
      "tesouraria-refinanciamentos",
      "pendentes",
      pagePending,
      search,
      dataInicio?.toISOString(),
      dataFim?.toISOString(),
    ],
    queryFn: () =>
      apiFetch<PaginatedResponse<RefinanciamentoItem>>("tesouraria/refinanciamentos", {
        query: {
          page: pagePending,
          page_size: 15,
          search: search || undefined,
          data_inicio: toIsoDate(dataInicio),
          data_fim: toIsoDate(dataFim),
          status: PENDING_STATUS,
        },
      }),
  });

  const efetivadasQuery = useQuery({
    queryKey: [
      "tesouraria-refinanciamentos",
      "efetivadas",
      pageEfetivadas,
      search,
      dataInicio?.toISOString(),
      dataFim?.toISOString(),
    ],
    queryFn: () =>
      apiFetch<PaginatedResponse<RefinanciamentoItem>>("tesouraria/refinanciamentos", {
        query: {
          page: pageEfetivadas,
          page_size: 15,
          search: search || undefined,
          data_inicio: toIsoDate(dataInicio),
          data_fim: toIsoDate(dataFim),
          status: EFETIVADO_STATUS,
        },
      }),
  });

  const canceladasQuery = useQuery({
    queryKey: [
      "tesouraria-refinanciamentos",
      "canceladas",
      pageCanceladas,
      search,
      dataInicio?.toISOString(),
      dataFim?.toISOString(),
    ],
    queryFn: () =>
      apiFetch<PaginatedResponse<RefinanciamentoItem>>("tesouraria/refinanciamentos", {
        query: {
          page: pageCanceladas,
          page_size: 15,
          search: search || undefined,
          data_inicio: toIsoDate(dataInicio),
          data_fim: toIsoDate(dataFim),
          status: CANCELADO_STATUS,
        },
      }),
  });

  const resumoQuery = useQuery({
    queryKey: [
      "tesouraria-refinanciamentos-resumo",
      search,
      dataInicio?.toISOString(),
      dataFim?.toISOString(),
    ],
    queryFn: () =>
      apiFetch<RefinanciamentoResumo>("tesouraria/refinanciamentos/resumo", {
        query: {
          search: search || undefined,
          data_inicio: toIsoDate(dataInicio),
          data_fim: toIsoDate(dataFim),
        },
      }),
  });

  const substituirComprovanteMutation = useMutation({
    mutationFn: async ({
      refinanciamentoId,
      papel,
      arquivo,
    }: {
      refinanciamentoId: number;
      papel: "associado" | "agente";
      arquivo: File;
    }) => {
      const formData = new FormData();
      formData.set("papel", papel);
      formData.set("arquivo", arquivo);
      return apiFetch<RefinanciamentoItem>(
        `tesouraria/refinanciamentos/${refinanciamentoId}/substituir-comprovante`,
        {
          method: "POST",
          formData,
        },
      );
    },
    onSuccess: (_, variables) => {
      toast.success(
        variables.papel === "associado"
          ? "Comprovante do associado atualizado."
          : "Comprovante do agente atualizado.",
      );
      void queryClient.invalidateQueries({ queryKey: ["tesouraria-refinanciamentos"] });
      void queryClient.invalidateQueries({ queryKey: ["tesouraria-refinanciamentos-resumo"] });
      void queryClient.invalidateQueries({ queryKey: ["agente-refinanciados"] });
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : "Falha ao atualizar comprovante.",
      );
    },
  });

  const resumo = resumoQuery.data;
  const canceladasTotal =
    (resumo?.bloqueados ?? 0) + (resumo?.revertidos ?? 0) + (resumo?.desativados ?? 0);
  const activeFiltersCount = Number(Boolean(dataInicio)) + Number(Boolean(dataFim));

  const pendingColumns = React.useMemo<DataTableColumn<RefinanciamentoItem>[]>(
    () => [
      {
        id: "anexos",
        header: "Anexos",
        cellClassName: "min-w-[28rem]",
        cell: (row) => {
          const { termoAgente, comprovanteAssociado, comprovanteAgente } =
            resolveRenewalAttachments(row);
          const isProcessing =
            substituirComprovanteMutation.isPending &&
            substituirComprovanteMutation.variables?.refinanciamentoId === row.id;

          return (
            <div className="space-y-3">
              <div className="flex flex-wrap gap-2">
                <CompactUploadButton
                  id={`renovacao-${row.id}-termo-agente`}
                  label="Termo do agente"
                  existingUrl={
                    termoAgente?.arquivo_disponivel_localmente ? termoAgente.arquivo : undefined
                  }
                  existingReference={termoAgente?.arquivo_referencia}
                  existingReferenceType={termoAgente?.tipo_referencia}
                  existingName={termoAgente?.nome_original}
                  disabled
                />
                <CompactUploadButton
                  id={`renovacao-${row.id}-associado`}
                  label="Comp. associado"
                  existingUrl={
                    comprovanteAssociado?.arquivo_disponivel_localmente
                      ? comprovanteAssociado.arquivo
                      : undefined
                  }
                  existingReference={comprovanteAssociado?.arquivo_referencia}
                  existingReferenceType={comprovanteAssociado?.tipo_referencia}
                  existingName={comprovanteAssociado?.nome_original}
                  disabled={!canMutate || isProcessing}
                  onSelect={(file) =>
                    substituirComprovanteMutation.mutate({
                      refinanciamentoId: row.id,
                      papel: "associado",
                      arquivo: file,
                    })
                  }
                  onClear={() => undefined}
                />
                <CompactUploadButton
                  id={`renovacao-${row.id}-agente`}
                  label="Comp. agente"
                  existingUrl={
                    comprovanteAgente?.arquivo_disponivel_localmente
                      ? comprovanteAgente.arquivo
                      : undefined
                  }
                  existingReference={comprovanteAgente?.arquivo_referencia}
                  existingReferenceType={comprovanteAgente?.tipo_referencia}
                  existingName={comprovanteAgente?.nome_original}
                  disabled={!canMutate || isProcessing}
                  onSelect={(file) =>
                    substituirComprovanteMutation.mutate({
                      refinanciamentoId: row.id,
                      papel: "agente",
                      arquivo: file,
                    })
                  }
                  onClear={() => undefined}
                />
              </div>
              <p className="text-xs text-muted-foreground">
                O comprovante do associado efetiva automaticamente. O comprovante do agente
                continua opcional e pode ser anexado depois.
              </p>
            </div>
          );
        },
      },
      {
        id: "acao",
        header: "Ação",
        cell: () => (
          <div className="flex min-w-44 flex-col gap-2">
            <Badge variant="outline" className="w-fit rounded-full">
              Upload imediato
            </Badge>
            <p className="text-xs text-muted-foreground">
              O anexo do associado conclui a etapa operacional da tesouraria.
            </p>
          </div>
        ),
      },
      {
        id: "associado",
        header: "Associado",
        cell: (row) => (
          <div className="space-y-2">
            <CopySnippet
              label="Associado"
              value={row.associado_nome}
              inline
              className="max-w-[16rem]"
            />
            <Button
              size="sm"
              variant="outline"
              onClick={() => setDetailAssociadoId(row.associado_id)}
            >
              Ver detalhes do associado
            </Button>
          </div>
        ),
      },
      {
        id: "contrato",
        header: "Contrato",
        cell: (row) => (
          <div className="space-y-1">
            <CopySnippet label="Contrato" value={row.contrato_codigo} mono inline />
            <p className="text-xs text-muted-foreground">
              Parcelas pagas no ciclo: {row.mensalidades_pagas}/{row.mensalidades_total}
            </p>
          </div>
        ),
      },
      {
        id: "matricula_cpf",
        header: "Matrícula / CPF",
        cell: (row) => (
          <div className="space-y-1">
            <CopySnippet
              label="Matrícula"
              value={row.matricula_display || row.matricula}
              mono
              inline
            />
            <CopySnippet label="CPF" value={row.cpf_cnpj} mono inline />
          </div>
        ),
      },
      {
        id: "agente",
        header: "Agente",
        cell: (row) => (
          <p className="text-sm text-muted-foreground">{row.agente?.full_name || "—"}</p>
        ),
      },
      {
        id: "valores",
        header: "Valor / Repasse",
        cell: (row) => (
          <div className="space-y-1">
            <p className="font-semibold">{formatCurrency(row.valor_liberado_associado)}</p>
            <p className="text-xs text-emerald-400">
              Repasse do agente: {formatCurrency(row.repasse_agente)}
            </p>
          </div>
        ),
      },
      {
        id: "competencia",
        header: "Competência solicitada",
        cell: (row) => formatMonthYear(row.competencia_solicitada),
      },
      {
        id: "envio_tesouraria",
        header: "Envio para tesouraria",
        cell: (row) => formatDateTime(row.updated_at),
      },
      {
        id: "data_anexo_associado",
        header: "Anexo associado",
        cell: (row) => formatDateTime(row.data_anexo_associado),
      },
      {
        id: "data_anexo_agente",
        header: "Anexo agente",
        cell: (row) => formatDateTime(row.data_anexo_agente),
      },
      {
        id: "data_pagamento_associado",
        header: "Pagamento associado",
        cell: (row) => formatDateTime(row.data_pagamento_associado),
      },
      {
        id: "data_pagamento_agente",
        header: "Pagamento agente",
        cell: (row) => formatDateTime(row.data_pagamento_agente),
      },
      {
        id: "status",
        header: "Status",
        cell: (row) => (
          <div className="space-y-2">
            <StatusBadge status={row.status} />
            <p className="text-xs text-muted-foreground">
              {row.coordenador_note?.trim() || row.analista_note?.trim() || row.motivo_apto_renovacao}
            </p>
          </div>
        ),
      },
    ],
    [canMutate, substituirComprovanteMutation],
  );

  const historyColumns = React.useMemo<DataTableColumn<RefinanciamentoItem>[]>(
    () => [
      {
        id: "anexos",
        header: "Anexos",
        cellClassName: "min-w-[28rem]",
        cell: (row) => {
          const { termoAgente, comprovanteAssociado, comprovanteAgente } =
            resolveRenewalAttachments(row);

          return (
            <div className="flex flex-wrap gap-2">
              <CompactUploadButton
                id={`readonly-${row.id}-termo-agente`}
                label="Termo do agente"
                existingUrl={
                  termoAgente?.arquivo_disponivel_localmente ? termoAgente.arquivo : undefined
                }
                existingReference={termoAgente?.arquivo_referencia}
                existingReferenceType={termoAgente?.tipo_referencia}
                existingName={termoAgente?.nome_original}
                disabled
              />
              <CompactUploadButton
                id={`readonly-${row.id}-associado`}
                label="Comp. associado"
                existingUrl={
                  comprovanteAssociado?.arquivo_disponivel_localmente
                    ? comprovanteAssociado.arquivo
                    : undefined
                }
                existingReference={comprovanteAssociado?.arquivo_referencia}
                existingReferenceType={comprovanteAssociado?.tipo_referencia}
                existingName={comprovanteAssociado?.nome_original}
                disabled={!canMutate}
                onSelect={(file) =>
                  substituirComprovanteMutation.mutate({
                    refinanciamentoId: row.id,
                    papel: "associado",
                    arquivo: file,
                  })
                }
                onClear={() => undefined}
              />
              <CompactUploadButton
                id={`readonly-${row.id}-agente`}
                label="Comp. agente"
                existingUrl={
                  comprovanteAgente?.arquivo_disponivel_localmente
                    ? comprovanteAgente.arquivo
                    : undefined
                }
                existingReference={comprovanteAgente?.arquivo_referencia}
                existingReferenceType={comprovanteAgente?.tipo_referencia}
                existingName={comprovanteAgente?.nome_original}
                disabled={!canMutate}
                onSelect={(file) =>
                  substituirComprovanteMutation.mutate({
                    refinanciamentoId: row.id,
                    papel: "agente",
                    arquivo: file,
                  })
                }
                onClear={() => undefined}
              />
            </div>
          );
        },
      },
      {
        id: "associado",
        header: "Associado",
        cell: (row) => (
          <div className="space-y-1">
            <CopySnippet label="Associado" value={row.associado_nome} inline className="max-w-[16rem]" />
            <CopySnippet label="CPF" value={row.cpf_cnpj} mono inline />
            <Button
              size="sm"
              variant="outline"
              onClick={() => setDetailAssociadoId(row.associado_id)}
            >
              Ver detalhes do associado
            </Button>
          </div>
        ),
      },
      {
        id: "contrato",
        header: "Contrato",
        cell: (row) => (
          <div className="space-y-1">
            <CopySnippet label="Contrato" value={row.contrato_codigo} mono inline />
            <p className="text-xs text-muted-foreground">
              Competência solicitada {formatMonthYear(row.competencia_solicitada)}
            </p>
          </div>
        ),
      },
      {
        id: "agente",
        header: "Agente",
        cell: (row) => (
          <p className="text-sm text-muted-foreground">{row.agente?.full_name || "—"}</p>
        ),
      },
      {
        id: "valor_pago",
        header: "Valor / Repasse",
        cell: (row) => (
          <div className="space-y-1">
            <p className="font-semibold">{formatCurrency(row.valor_liberado_associado)}</p>
            <p className="text-xs text-emerald-400">
              Repasse do agente: {formatCurrency(row.repasse_agente)}
            </p>
          </div>
        ),
      },
      {
        id: "data_operacional",
        header: "Data operacional",
        cell: (row) =>
          formatDateTime(row.executado_em || row.data_ativacao_ciclo || row.updated_at),
      },
      {
        id: "data_anexo_associado",
        header: "Anexo associado",
        cell: (row) => formatDateTime(row.data_anexo_associado),
      },
      {
        id: "data_anexo_agente",
        header: "Anexo agente",
        cell: (row) => formatDateTime(row.data_anexo_agente),
      },
      {
        id: "data_pagamento_associado",
        header: "Pagamento associado",
        cell: (row) => formatDateTime(row.data_pagamento_associado),
      },
      {
        id: "data_pagamento_agente",
        header: "Pagamento agente",
        cell: (row) => formatDateTime(row.data_pagamento_agente),
      },
      {
        id: "status",
        header: "Status",
        cell: (row) => (
          <div className="space-y-2">
            <StatusBadge status={row.status} />
            {row.data_ativacao_ciclo ? (
              <p className="text-xs text-muted-foreground">
                Ativado em {formatDateTime(row.data_ativacao_ciclo)}
              </p>
            ) : null}
          </div>
        ),
      },
    ],
    [canMutate, substituirComprovanteMutation],
  );

  const handleExport = React.useCallback(
    async (exportFilters: ReportExportFilters, exportFormat: "pdf" | "xlsx") => {
      const {
        scope,
        referenceDate,
        agente: exportAgente,
        status: exportStatus,
        columns: selectedColumns,
      } = exportFilters;
      setIsExporting(true);
      try {
        const sourceQuery = {
          search: search || undefined,
          data_inicio: toIsoDate(dataInicio),
          data_fim: toIsoDate(dataFim),
          agente: exportAgente || undefined,
        };
        const fetchedRows = await fetchAllPaginatedRows<RefinanciamentoItem>({
          sourcePath: "tesouraria/refinanciamentos",
          sourceQuery,
        });
        const scopedRows = filterRowsByReportScope({
          rows: fetchedRows,
          scope,
          referenceDate,
          getCandidates: (row) => [
            row.data_solicitacao_renovacao,
            row.data_solicitacao,
            row.executado_em,
            row.data_ativacao_ciclo,
            row.updated_at,
          ],
        }).filter((row) => !exportStatus || row.status === exportStatus);

        const rows = scopedRows.map((row) => ({
          associado_nome: row.associado_nome,
          cpf_cnpj: row.cpf_cnpj,
          contrato_codigo: row.contrato_codigo,
          data_solicitacao: formatDateTime(
            row.data_solicitacao_renovacao || row.data_solicitacao,
          ),
          data_anexo_associado: formatDateTime(row.data_anexo_associado),
          data_anexo_agente: formatDateTime(row.data_anexo_agente),
          data_pagamento_associado: formatDateTime(row.data_pagamento_associado),
          data_pagamento_agente: formatDateTime(row.data_pagamento_agente),
          status: row.status,
          valor_refinanciamento: formatCurrency(row.valor_liberado_associado),
          repasse_agente: row.repasse_agente,
          pagamento_status: row.pagamento_status,
          executado_em: row.executado_em,
          data_ativacao_ciclo: row.data_ativacao_ciclo,
        }));

        await exportRouteReport({
          route: "/tesouraria/refinanciamentos",
          format: exportFormat,
          rows,
          filters: {
            ...sourceQuery,
            ...describeReportScope(scope, referenceDate),
            totais: {
              total_registros: scopedRows.length,
              total_valor_renovacao: scopedRows
                .reduce(
                  (sum, row) =>
                    sum + Number.parseFloat(String(row.valor_liberado_associado ?? "0")),
                  0,
                )
                .toFixed(2),
              total_repasse_agente: scopedRows
                .reduce(
                  (sum, row) =>
                    sum + Number.parseFloat(String(row.repasse_agente ?? "0")),
                  0,
                )
                .toFixed(2),
            },
            columns: selectedColumns,
          },
        });
      } catch (error) {
        toast.error(
          error instanceof Error ? error.message : "Falha ao exportar renovações da tesouraria.",
        );
      } finally {
        setIsExporting(false);
      }
    },
    [dataFim, dataInicio, search],
  );

  return (
    <div className="space-y-6">
      <section className="rounded-[1.75rem] border border-border/60 bg-card/70 p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-1">
            <p className="text-sm uppercase tracking-[0.28em] text-muted-foreground">
              Tesouraria
            </p>
            <h1 className="text-3xl font-semibold">Contratos para Renovação</h1>
            <p className="text-sm text-muted-foreground">
              Contratos aprovados pela coordenação, com fila operacional da tesouraria
              e histórico de efetivação.
            </p>
          </div>
          <ReportExportDialog
            disabled={isExporting}
            label="Exportar"
            showFilters
            agentOptions={agentOptions}
            statusOptions={[
              { value: "aprovado_para_renovacao", label: "Aguardando Pagamento" },
              { value: "efetivado", label: "Efetivado" },
              { value: "bloqueado", label: "Bloqueado" },
              { value: "revertido", label: "Revertido" },
              { value: "desativado", label: "Desativado" },
            ]}
            onExport={handleExport}
          />
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatsCard
          title="Pendentes para renovação"
          value={String(pendingQuery.data?.count ?? 0)}
          delta="Fila operacional aguardando anexos da tesouraria"
          icon={Clock3Icon}
          tone="neutral"
        />
        <StatsCard
          title="Efetivadas"
          value={String(resumo?.efetivados ?? efetivadasQuery.data?.count ?? 0)}
          delta="Contratos concluídos pela tesouraria"
          icon={CheckCircle2Icon}
          tone="positive"
        />
        <StatsCard
          title="Canceladas"
          value={String(canceladasTotal)}
          delta="Bloqueadas, revertidas ou desativadas"
          icon={XCircleIcon}
          tone="warning"
        />
        <StatsCard
          title="Repasse total"
          value={formatCurrency(resumo?.repasse_total ?? "0")}
          delta="Soma do repasse no recorte atual"
          icon={HandCoinsIcon}
          tone="neutral"
        />
      </section>

      <section className="grid gap-4 rounded-[1.75rem] border border-border/60 bg-card/70 p-5 lg:grid-cols-[minmax(0,1fr)_auto]">
        <Input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Buscar por associado, CPF, matrícula ou contrato..."
          className="h-11 rounded-2xl border-border/60 bg-background/60"
        />
        <div className="flex justify-end">
          <Sheet
            open={filtersOpen}
            onOpenChange={(open) => {
              if (open) {
                setDraftDataInicio(dataInicio);
                setDraftDataFim(dataFim);
              }
              setFiltersOpen(open);
            }}
          >
            <SheetTrigger asChild>
              <Button variant="outline" className="h-11 rounded-2xl">
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
                  Refine o recorte da tesouraria por datas operacionais das renovações.
                </SheetDescription>
              </SheetHeader>

              <div className="space-y-5 overflow-y-auto px-4 pb-4">
                <div className="space-y-2">
                  <Label>Data inicial</Label>
                  <DatePicker value={draftDataInicio} onChange={setDraftDataInicio} />
                </div>
                <div className="space-y-2">
                  <Label>Data final</Label>
                  <DatePicker value={draftDataFim} onChange={setDraftDataFim} />
                </div>
              </div>

              <SheetFooter className="border-t border-border/60">
                <Button
                  variant="outline"
                  onClick={() => {
                    setDraftDataInicio(undefined);
                    setDraftDataFim(undefined);
                    setDataInicio(undefined);
                    setDataFim(undefined);
                    setFiltersOpen(false);
                  }}
                >
                  Limpar
                </Button>
                <Button
                  onClick={() => {
                    setDataInicio(draftDataInicio);
                    setDataFim(draftDataFim);
                    setFiltersOpen(false);
                  }}
                >
                  Aplicar
                </Button>
              </SheetFooter>
            </SheetContent>
          </Sheet>
        </div>
      </section>

      <RefinanciamentoSection
        eyebrow="Pendentes"
        title="Contratos aprovados para pagamento"
        total={pendingQuery.data?.count ?? 0}
        page={pagePending}
        rows={pendingQuery.data?.results ?? []}
        columns={pendingColumns}
        onPageChange={setPagePending}
        loading={pendingQuery.isLoading}
        emptyMessage="Nenhuma renovação aprovada para renovação no recorte atual."
      />

      <RefinanciamentoSection
        eyebrow="Efetivadas"
        title="Contratos concluídos"
        total={efetivadasQuery.data?.count ?? 0}
        page={pageEfetivadas}
        rows={efetivadasQuery.data?.results ?? []}
        columns={historyColumns}
        onPageChange={setPageEfetivadas}
        loading={efetivadasQuery.isLoading}
        emptyMessage="Nenhuma renovação efetivada no recorte."
      />

      <RefinanciamentoSection
        eyebrow="Canceladas"
        title="Contratos bloqueados ou revertidos"
        total={canceladasQuery.data?.count ?? 0}
        page={pageCanceladas}
        rows={canceladasQuery.data?.results ?? []}
        columns={historyColumns}
        onPageChange={setPageCanceladas}
        loading={canceladasQuery.isLoading}
        emptyMessage="Nenhuma renovação cancelada no recorte."
      />

      <AssociadoDetailsDialog
        associadoId={detailAssociadoId}
        open={detailAssociadoId != null}
        onOpenChange={(open) => {
          if (!open) {
            setDetailAssociadoId(null);
          }
        }}
      />
    </div>
  );
}

function RefinanciamentoSection({
  eyebrow,
  title,
  total,
  page,
  rows,
  columns,
  onPageChange,
  loading,
  emptyMessage,
}: {
  eyebrow: string;
  title: string;
  total: number;
  page: number;
  rows: RefinanciamentoItem[];
  columns: DataTableColumn<RefinanciamentoItem>[];
  onPageChange: (page: number) => void;
  loading: boolean;
  emptyMessage: string;
}) {
  const start = total ? (page - 1) * 15 + 1 : 0;
  const end = total ? start + rows.length - 1 : 0;

  return (
    <section className="space-y-4">
      <header className="flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.28em] text-muted-foreground">{eyebrow}</p>
          <h2 className="text-xl font-semibold">{title}</h2>
        </div>
        <p className="text-sm text-muted-foreground">
          Mostrando {total ? `${start}-${end} de ${total}` : "0"}
        </p>
      </header>
      <DataTable
        data={rows}
        columns={columns}
        currentPage={page}
        totalPages={Math.max(1, Math.ceil(total / 15))}
        onPageChange={onPageChange}
        emptyMessage={emptyMessage}
        loading={loading}
        skeletonRows={6}
      />
    </section>
  );
}
