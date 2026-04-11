"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLinkIcon, RefreshCcwIcon } from "lucide-react";
import { toast } from "sonner";

import AssociadoDetailsDialog from "@/components/associados/associado-details-dialog";
import CalendarCompetencia from "@/components/custom/calendar-competencia";
import FileUploadDropzone from "@/components/custom/file-upload-dropzone";
import StatusBadge from "@/components/custom/status-badge";
import ReportExportDialog from "@/components/shared/report-export-dialog";
import DataTable, {
  type DataTableColumn,
} from "@/components/shared/data-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import DryRunModal from "@/components/importacao/dry-run-modal";
import {
  useV1ImportacaoArquivoRetornoDescontadosList,
  useV1ImportacaoArquivoRetornoEncerramentosList,
  useV1ImportacaoArquivoRetornoFinanceiroRetrieve,
  useV1ImportacaoArquivoRetornoNaoDescontadosList,
  useV1ImportacaoArquivoRetornoNovosCiclosList,
  useV1ImportacaoArquivoRetornoPendenciasManuaisList,
  useV1ImportacaoArquivoRetornoUltimaRetrieve,
} from "@/gen";
import type {
  ArquivoRetornoDetail,
  ArquivoRetornoItem,
  ArquivoRetornoList,
  PaginatedArquivoRetornoListList,
} from "@/gen/models";
import { apiFetch } from "@/lib/api/client";
import { formatMonthValue, parseMonthValue } from "@/lib/date-value";
import { formatCurrency, formatDateTime } from "@/lib/formatters";
import {
  getArquivoFinanceiroResumo,
  type ArquivoRetornoFinanceiroItem,
  type ArquivoRetornoWithFinanceiro,
} from "@/lib/importacao-financeiro";
import { maskCPFCNPJ } from "@/lib/masks";
import { exportRows, type TableExportColumn } from "@/lib/table-export";
import { cn } from "@/lib/utils";

const TXT_ACCEPT = { "text/plain": [".txt"] };
const ITEM_PAGE_SIZE = 5;
const HISTORY_PAGE_SIZE = 5;
const DETAIL_PAGE_SIZE_OPTIONS = [
  { label: "10", value: 10 },
  { label: "20", value: 20 },
  { label: "50", value: 50 },
];

type DryRunPreviewState = {
  arquivoId: number;
  arquivoNome: string;
  competenciaDisplay: string;
  dryRunData: NonNullable<ArquivoRetornoDetail["dry_run_resultado"]>;
};

type LatestMetricDialogConfig = {
  key: "linhas" | "mensalidades" | "valores_30_50";
  title: string;
  description: string;
  rows: ArquivoRetornoFinanceiroItem[];
  emptyMessage: string;
};

function totalPages(count?: number, pageSize = 5) {
  return Math.max(1, Math.ceil((count ?? 0) / pageSize));
}

function statusIsPending(status?: string) {
  return status === "pendente" || status === "processando";
}

type ItemSectionProps = {
  title: string;
  description: string;
  data: ArquivoRetornoItem[];
  emptyMessage: string;
  isLoading?: boolean;
};

function ItemSection({
  title,
  description,
  data,
  emptyMessage,
  isLoading = false,
}: ItemSectionProps) {
  const columns: DataTableColumn<ArquivoRetornoItem>[] = [
    {
      id: "nome",
      header: "Servidor",
      cell: (row) => (
        <div>
          <p className="font-medium text-foreground">{row.nome_servidor}</p>
          <p className="text-xs text-muted-foreground">
            {row.matricula_servidor}
          </p>
        </div>
      ),
    },
    {
      id: "cpf_cnpj",
      header: "CPF",
      cell: (row) => maskCPFCNPJ(row.cpf_cnpj),
    },
    {
      id: "orgao_pagto_nome",
      header: "Órgão",
      cell: (row) => row.orgao_pagto_nome || "-",
    },
    {
      id: "valor_descontado",
      header: "Valor",
      cell: (row) => formatCurrency(row.valor_descontado),
    },
    {
      id: "status_codigo",
      header: "ETIPI",
      cell: (row) => (
        <Badge variant="outline">{row.status_codigo || "-"}</Badge>
      ),
    },
    {
      id: "status_desconto",
      header: "Sistema",
      cell: (row) => (
        <StatusBadge
          status={
            row.status_desconto ?? row.resultado_processamento ?? "pendente"
          }
        />
      ),
    },
  ];

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-semibold text-foreground">{title}</h3>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
      {isLoading ? (
        <div className="space-y-3 rounded-[1.75rem] border border-border/60 bg-card/70 p-5 shadow-xl shadow-black/20">
          <Skeleton className="h-10 w-full rounded-xl" />
          <Skeleton className="h-14 w-full rounded-xl" />
          <Skeleton className="h-14 w-full rounded-xl" />
          <Skeleton className="h-14 w-full rounded-xl" />
        </div>
      ) : (
        <DataTable columns={columns} data={data} emptyMessage={emptyMessage} />
      )}
    </div>
  );
}

function normalizeText(value?: string | null) {
  return (value ?? "")
    .toString()
    .normalize("NFD")
    .replaceAll(/\p{Diacritic}/gu, "")
    .toLowerCase()
    .trim();
}

function normalizeCategoria(value?: string | null) {
  return normalizeText(value)
    .replaceAll("/", "_")
    .replaceAll("-", "_")
    .replaceAll(" ", "_");
}

function isMensalidadesCategoria(value?: string | null) {
  const normalized = normalizeCategoria(value);
  return normalized === "mensalidades" || normalized === "mensalidade";
}

function isValores3050Categoria(value?: string | null) {
  const normalized = normalizeCategoria(value);
  return normalized === "valores_30_50" || normalized === "valores3050";
}

function matchesFinanceiroRowSearch(
  row: ArquivoRetornoFinanceiroItem,
  search: string,
) {
  const searchValue = normalizeText(search);
  if (!searchValue) {
    return true;
  }

  const comparable = [
    row.associado_nome,
    row.cpf_cnpj,
    row.matricula,
    row.agente_responsavel,
    row.categoria,
    row.situacao_label,
  ]
    .map(normalizeText)
    .join(" ");
  return comparable.includes(searchValue);
}

function financeiroExportColumns(): TableExportColumn<ArquivoRetornoFinanceiroItem>[] {
  return [
    { header: "Associado", value: (row) => row.associado_nome || "" },
    { header: "CPF", value: (row) => maskCPFCNPJ(row.cpf_cnpj) },
    { header: "Matrícula", value: (row) => row.matricula || "" },
    {
      header: "Agente responsável",
      value: (row) => row.agente_responsavel || "",
    },
    { header: "Categoria", value: (row) => row.categoria || "" },
    { header: "Esperado", value: (row) => formatCurrency(row.esperado) },
    { header: "Recebido", value: (row) => formatCurrency(row.recebido) },
    { header: "Situação", value: (row) => row.situacao_label || "" },
  ];
}

function buildFinanceiroColumns({
  onOpenAssociadoDetails,
}: {
  onOpenAssociadoDetails?: (associadoId: number) => void;
} = {}): DataTableColumn<ArquivoRetornoFinanceiroItem>[] {
  const columns: DataTableColumn<ArquivoRetornoFinanceiroItem>[] = [
    {
      id: "associado_nome",
      header: "Servidor",
      cell: (row) => (
        <div>
          <p className="font-medium text-foreground">{row.associado_nome}</p>
          <p className="text-xs text-muted-foreground">
            {row.matricula || "-"}
          </p>
        </div>
      ),
    },
    {
      id: "cpf_cnpj",
      header: "CPF",
      cell: (row) => maskCPFCNPJ(row.cpf_cnpj),
    },
    {
      id: "categoria",
      header: "Categoria",
      cell: (row) => row.categoria || "-",
    },
    {
      id: "esperado",
      header: "Esperado",
      cell: (row) => formatCurrency(row.esperado),
    },
    {
      id: "recebido",
      header: "Recebido",
      cell: (row) => formatCurrency(row.recebido),
    },
    {
      id: "situacao_label",
      header: "Situação",
      cell: (row) => (
        <StatusBadge status={row.ok ? "concluido" : "pendencia_manual"} />
      ),
    },
  ];

  if (onOpenAssociadoDetails) {
    columns.push({
      id: "acoes",
      header: "",
      cell: (row) =>
        row.associado_id ? (
          <Button
            size="sm"
            variant="outline"
            onClick={() => onOpenAssociadoDetails(row.associado_id as number)}
          >
            <ExternalLinkIcon className="mr-1.5 size-3.5" />
            Ver associado
          </Button>
        ) : (
          <span className="text-xs text-muted-foreground">
            Sem associado vinculado
          </span>
        ),
    });
  }

  return columns;
}

function ImportMetricCard({
  title,
  value,
  hint,
  onClick,
}: {
  title: string;
  value: React.ReactNode;
  hint?: string;
  onClick?: () => void;
}) {
  const content = (
    <Card className="border-border/60 bg-card/80 transition-colors hover:bg-card">
      <CardHeader>
        <CardDescription>{title}</CardDescription>
        <CardTitle className="text-3xl">{value}</CardTitle>
        {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
      </CardHeader>
    </Card>
  );

  if (!onClick) {
    return content;
  }

  return (
    <button type="button" className="text-left" onClick={onClick}>
      {content}
    </button>
  );
}

function MetricCardSkeleton() {
  return (
    <Card className="border-border/60 bg-card/80">
      <CardHeader>
        <Skeleton className="h-4 w-28" />
        <Skeleton className="h-10 w-16" />
      </CardHeader>
    </Card>
  );
}

function HistoryTableSkeleton() {
  return (
    <div className="space-y-3 rounded-[1.75rem] border border-border/60 bg-card/70 p-5 shadow-xl shadow-black/20">
      <Skeleton className="h-10 w-full rounded-xl" />
      <Skeleton className="h-14 w-full rounded-xl" />
      <Skeleton className="h-14 w-full rounded-xl" />
      <Skeleton className="h-14 w-full rounded-xl" />
      <div className="flex justify-between gap-3 pt-2">
        <Skeleton className="h-4 w-24" />
        <div className="flex gap-2">
          <Skeleton className="size-8 rounded-md" />
          <Skeleton className="size-8 rounded-md" />
          <Skeleton className="size-8 rounded-md" />
          <Skeleton className="size-8 rounded-md" />
        </div>
      </div>
    </div>
  );
}

export default function ImportacaoPage() {
  const queryClient = useQueryClient();
  const latestResultSectionRef = React.useRef<HTMLDivElement | null>(null);
  const [historyPage, setHistoryPage] = React.useState(1);
  const [activeTab, setActiveTab] = React.useState("descontados");
  const [isPolling, setIsPolling] = React.useState(false);
  const [uploadFile, setUploadFile] = React.useState<File | null>(null);
  const [uploadProgress, setUploadProgress] = React.useState(0);
  const [dryRunPreview, setDryRunPreview] =
    React.useState<DryRunPreviewState | null>(null);
  const [historyCompetencia, setHistoryCompetencia] = React.useState("");
  const [historyStatus, setHistoryStatus] = React.useState("todos");
  const [latestMetricDialogConfig, setLatestMetricDialogConfig] =
    React.useState<LatestMetricDialogConfig | null>(null);
  const [latestMetricSearch, setLatestMetricSearch] = React.useState("");
  const [selectedAssociadoId, setSelectedAssociadoId] = React.useState<
    number | null
  >(null);

  const historyQuery = useQuery({
    queryKey: [
      "importacao-arquivo-retorno-history",
      historyPage,
      historyCompetencia,
      historyStatus,
    ],
    queryFn: () =>
      apiFetch<PaginatedArquivoRetornoListList>("importacao/arquivo-retorno", {
        query: {
          page: historyPage,
          page_size: HISTORY_PAGE_SIZE,
          competencia: historyCompetencia || undefined,
          status: historyStatus !== "todos" ? historyStatus : undefined,
        },
      }),
    staleTime: 30 * 1000,
    placeholderData: (previousData) => previousData,
  });
  const latestQuery = useV1ImportacaoArquivoRetornoUltimaRetrieve({
    query: {
      retry: false,
      refetchInterval: isPolling ? 3000 : false,
      staleTime: 15 * 1000,
      placeholderData: (previousData) => previousData,
    },
  });

  const latestImport = latestQuery.data ?? historyQuery.data?.results?.[0];
  const latestImportWithFinanceiro = latestImport as
    | ArquivoRetornoWithFinanceiro
    | undefined;
  const latestId = latestImport?.id ?? 0;
  const latestFinanceiroQuery = useV1ImportacaoArquivoRetornoFinanceiroRetrieve(
    latestId,
    {
      query: {
        enabled: !!latestId && latestImport?.status === "concluido",
        staleTime: 5 * 60 * 1000,
        placeholderData: (previousData) => previousData,
      },
    },
  );
  const latestFinanceiro =
    latestFinanceiroQuery.data?.resumo ??
    getArquivoFinanceiroResumo(latestImportWithFinanceiro);
  const latestFinanceiroRows = latestFinanceiroQuery.data?.rows ?? [];

  const latestMetricRows = React.useMemo(
    () => ({
      linhas: latestFinanceiroRows,
      mensalidades: latestFinanceiroRows.filter((row) =>
        isMensalidadesCategoria(row.categoria),
      ),
      valores_30_50: latestFinanceiroRows.filter((row) =>
        isValores3050Categoria(row.categoria),
      ),
    }),
    [latestFinanceiroRows],
  );
  const filteredLatestMetricRows = React.useMemo(
    () =>
      (latestMetricDialogConfig?.rows ?? []).filter((row) =>
        matchesFinanceiroRowSearch(row, latestMetricSearch),
      ),
    [latestMetricDialogConfig?.rows, latestMetricSearch],
  );
  const latestFinanceiroColumns = React.useMemo(
    () =>
      buildFinanceiroColumns({
        onOpenAssociadoDetails: (associadoId) =>
          setSelectedAssociadoId(associadoId),
      }),
    [],
  );

  const openLatestMetricDialog = React.useCallback(
    (key: keyof typeof latestMetricRows) => {
      const configMap: Record<
        keyof typeof latestMetricRows,
        Omit<LatestMetricDialogConfig, "rows">
      > = {
        linhas: {
          key: "linhas",
          title: "Linhas conciliadas da última importação",
          description:
            "Listagem financeira consolidada do último arquivo retorno processado.",
          emptyMessage:
            "Nenhuma linha conciliada disponível para a última importação.",
        },
        mensalidades: {
          key: "mensalidades",
          title: "Mensalidades da última importação",
          description:
            "Associados classificados como mensalidades no detalhamento financeiro do último arquivo.",
          emptyMessage:
            "Nenhuma mensalidade encontrada para a última importação.",
        },
        valores_30_50: {
          key: "valores_30_50",
          title: "Valores 30/50 da última importação",
          description:
            "Associados classificados na faixa de 30/50 reais no último arquivo retorno.",
          emptyMessage:
            "Nenhum associado classificado em 30/50 encontrado na última importação.",
        },
      };

      setLatestMetricDialogConfig({
        ...configMap[key],
        rows: latestMetricRows[key],
      });
      setLatestMetricSearch("");
    },
    [latestMetricRows],
  );

  React.useEffect(() => {
    setIsPolling(statusIsPending(latestImport?.status));
    if (!statusIsPending(latestImport?.status)) {
      void queryClient.invalidateQueries({
        queryKey: ["tesouraria-duplicidades-sidebar"],
      });
    }
  }, [latestImport?.status, queryClient]);

  React.useEffect(() => {
    setHistoryPage(1);
  }, [historyCompetencia, historyStatus]);

  React.useEffect(() => {
    if (!latestMetricDialogConfig) {
      setLatestMetricSearch("");
    }
  }, [latestMetricDialogConfig]);

  const focusLatestResultSection = React.useCallback(() => {
    latestResultSectionRef.current?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  }, []);

  const openLatestResultTab = React.useCallback(
    (nextTab: string) => {
      setActiveTab(nextTab);
      window.requestAnimationFrame(() => {
        focusLatestResultSection();
      });
    },
    [focusLatestResultSection],
  );

  function invalidateImportacao() {
    void queryClient.invalidateQueries({
      predicate: (query) =>
        JSON.stringify(query.queryKey).includes(
          "/api/v1/importacao/arquivo-retorno/",
        ),
    });
    void queryClient.invalidateQueries({
      queryKey: ["importacao-duplicidades-financeiras"],
    });
    void queryClient.invalidateQueries({
      queryKey: ["tesouraria-duplicidades-sidebar"],
    });
  }

  const uploadMutation = useMutation<ArquivoRetornoDetail, Error, File>({
    mutationFn: async (file) => {
      setUploadFile(file);
      setUploadProgress(0);
      const formData = new FormData();
      formData.append("arquivo", file);
      return apiFetch<ArquivoRetornoDetail>(
        "importacao/arquivo-retorno/upload",
        {
          method: "POST",
          formData,
          onUploadProgress: (progress) => {
            setUploadProgress(progress.percent);
          },
        },
      );
    },
    onSuccess: (data) => {
      toast.success("Arquivo enviado com sucesso.");
      setUploadFile(null);
      setUploadProgress(100);
      if (data.status === "aguardando_confirmacao" && data.dry_run_resultado) {
        setIsPolling(false);
        setDryRunPreview({
          arquivoId: data.id,
          arquivoNome: data.arquivo_nome,
          competenciaDisplay: data.competencia_display,
          dryRunData: data.dry_run_resultado,
        });
      } else {
        setDryRunPreview(null);
        setIsPolling(statusIsPending(data.status));
      }
      invalidateImportacao();
    },
    onError: (error) => {
      setUploadFile(null);
      setUploadProgress(0);
      toast.error(
        error instanceof Error ? error.message : "Falha no upload do arquivo.",
      );
    },
  });

  const reprocessarMutation = useMutation<ArquivoRetornoDetail, Error, number>({
    mutationFn: async (id) =>
      apiFetch<ArquivoRetornoDetail>(
        `importacao/arquivo-retorno/${id}/reprocessar`,
        {
          method: "POST",
        },
      ),
    onSuccess: () => {
      toast.success("Reprocessamento solicitado.");
      setIsPolling(true);
      invalidateImportacao();
    },
    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : "Falha ao reprocessar o arquivo.",
      );
    },
  });

  const confirmarMutation = useMutation<ArquivoRetornoDetail, Error, number>({
    mutationFn: async (id) =>
      apiFetch<ArquivoRetornoDetail>(
        `importacao/arquivo-retorno/${id}/confirmar`,
        {
          method: "POST",
        },
      ),
    onSuccess: (data) => {
      setDryRunPreview(null);
      setIsPolling(statusIsPending(data.status));
      toast.success("Importação confirmada. Processando...");
      invalidateImportacao();
    },
    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : "Falha ao confirmar a importação.",
      );
    },
  });

  const cancelarMutation = useMutation<void, Error, number>({
    mutationFn: async (id) =>
      apiFetch<void>(`importacao/arquivo-retorno/${id}/cancelar`, {
        method: "POST",
      }),
    onSuccess: () => {
      setDryRunPreview(null);
      setUploadFile(null);
      setUploadProgress(0);
      toast.success("Importação cancelada.");
      invalidateImportacao();
    },
    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : "Falha ao cancelar a importação.",
      );
    },
  });
  const isDryRunBusy =
    confirmarMutation.isPending || cancelarMutation.isPending;

  const descontadosQuery = useV1ImportacaoArquivoRetornoDescontadosList(
    latestId,
    { page_size: ITEM_PAGE_SIZE },
    {
      query: {
        enabled: !!latestId && activeTab === "descontados",
        staleTime: 30 * 1000,
        placeholderData: (previousData) => previousData,
      },
    },
  );
  const naoDescontadosQuery = useV1ImportacaoArquivoRetornoNaoDescontadosList(
    latestId,
    { page_size: ITEM_PAGE_SIZE },
    {
      query: {
        enabled: !!latestId && activeTab === "nao-descontados",
        staleTime: 30 * 1000,
        placeholderData: (previousData) => previousData,
      },
    },
  );
  const pendenciasQuery = useV1ImportacaoArquivoRetornoPendenciasManuaisList(
    latestId,
    { page_size: ITEM_PAGE_SIZE },
    {
      query: {
        enabled: !!latestId && activeTab === "pendencias",
        staleTime: 30 * 1000,
        placeholderData: (previousData) => previousData,
      },
    },
  );
  const encerramentosQuery = useV1ImportacaoArquivoRetornoEncerramentosList(
    latestId,
    { page_size: ITEM_PAGE_SIZE },
    {
      query: {
        enabled: !!latestId && activeTab === "encerramentos",
        staleTime: 30 * 1000,
        placeholderData: (previousData) => previousData,
      },
    },
  );
  const novosCiclosQuery = useV1ImportacaoArquivoRetornoNovosCiclosList(
    latestId,
    { page_size: ITEM_PAGE_SIZE },
    {
      query: {
        enabled: !!latestId && activeTab === "novos-ciclos",
        staleTime: 30 * 1000,
        placeholderData: (previousData) => previousData,
      },
    },
  );
  const processados = latestImport?.processados ?? 0;
  const totalRegistros = latestImport?.total_registros ?? 0;
  const processamentoPercentual = totalRegistros
    ? Math.round((processados / totalRegistros) * 100)
    : isPolling
      ? 10
      : 0;
  const activeItemsQuery =
    activeTab === "descontados"
      ? descontadosQuery
      : activeTab === "nao-descontados"
        ? naoDescontadosQuery
        : activeTab === "pendencias"
          ? pendenciasQuery
          : activeTab === "encerramentos"
            ? encerramentosQuery
            : novosCiclosQuery;
  const isInitialLatestLoading = latestQuery.isLoading && !latestImport;
  const isInitialHistoryLoading = historyQuery.isLoading && !historyQuery.data;
  const isInitialItemsLoading =
    activeItemsQuery.isLoading && !activeItemsQuery.data;
  const isLatestFinanceiroLoading =
    latestImport?.status === "concluido" &&
    latestFinanceiroQuery.isLoading &&
    !latestFinanceiro;
  const historyColumns: DataTableColumn<ArquivoRetornoList>[] = [
    {
      id: "created_at",
      header: "Data/Hora",
      cell: (row) => formatDateTime(row.processado_em ?? row.created_at),
    },
    {
      id: "arquivo_nome",
      header: "Arquivo",
      cell: (row) => (
        <div>
          <p className="font-medium text-foreground">{row.arquivo_nome}</p>
          <p className="text-xs text-muted-foreground">{row.sistema_origem}</p>
        </div>
      ),
    },
    {
      id: "competencia_display",
      header: "Referência",
      cell: (row) => row.competencia_display,
    },
    {
      id: "total_registros",
      header: "Total",
      accessor: "total_registros",
    },
    {
      id: "processados",
      header: "Processados",
      accessor: "processados",
    },
    {
      id: "associados_importados",
      header: "Associados importados",
      cell: (row) => row.associados_importados ?? row.nao_encontrados ?? 0,
    },
    {
      id: "erros",
      header: "Erros",
      accessor: "erros",
    },
    {
      id: "status",
      header: "Status",
      cell: (row) => <StatusBadge status={row.status ?? "pendente"} />,
    },
  ];

  return (
    <div className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <Card className="border-border/60 bg-card/80">
          <CardHeader>
            <CardTitle className="text-2xl">
              Importar Relatório de Retorno
            </CardTitle>
            <CardDescription>
              Formato esperado: relatório ETIPI/iNETConsig em <code>.txt</code>.
              A competência e o sistema de origem são extraídos automaticamente
              do arquivo.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <FileUploadDropzone
              accept={TXT_ACCEPT}
              maxSize={20 * 1024 * 1024}
              isProcessing={uploadMutation.isPending || isPolling}
              emptyTitle="Importar relatório ETIPI/iNETConsig"
              emptyDescription="Formato esperado: .txt com limite de 20 MB"
              file={uploadFile}
              onUpload={(file) => uploadMutation.mutate(file)}
            />
            {uploadMutation.isPending ? (
              <div className="rounded-2xl border border-primary/20 bg-primary/5 p-4">
                <div className="flex items-center justify-between gap-3 text-sm">
                  <span className="font-medium text-foreground">
                    Enviando {uploadFile?.name ?? "arquivo retorno"}
                  </span>
                  <span className="text-muted-foreground">
                    {uploadProgress}%
                  </span>
                </div>
                <Progress
                  value={Math.max(uploadProgress, 4)}
                  className="mt-3 h-2.5"
                />
              </div>
            ) : null}
            {isPolling ? (
              <div className="rounded-2xl border border-border/60 bg-background/40 p-4">
                <div className="flex items-center justify-between gap-3 text-sm">
                  <span className="font-medium text-foreground">
                    Processando arquivo retorno
                  </span>
                  <span className="text-muted-foreground">
                    {processados}/{Math.max(totalRegistros, processados)}
                  </span>
                </div>
                <Progress
                  value={Math.max(processamentoPercentual, 8)}
                  className="mt-3 h-2.5"
                />
              </div>
            ) : null}
            <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
              <Badge
                variant="outline"
                className="border-primary/30 text-primary"
              >
                Competência detectada no cabeçalho
              </Badge>
              <Badge variant="outline">Sem seleção manual de órgão</Badge>
              <Badge variant="outline">
                Upload multipart + processamento assíncrono
              </Badge>
            </div>
          </CardContent>
        </Card>

        <Card className="border-border/60 bg-card/80">
          <CardHeader>
            <CardTitle>Última importação</CardTitle>
            <CardDescription>
              {latestImport
                ? `Arquivo ${latestImport.arquivo_nome} em ${latestImport.competencia_display}.`
                : "Nenhum arquivo retorno processado até agora."}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {isInitialLatestLoading ? (
              <div className="space-y-4">
                <div className="flex flex-wrap gap-3">
                  <Skeleton className="h-7 w-24 rounded-full" />
                  <Skeleton className="h-7 w-28 rounded-full" />
                  <Skeleton className="h-7 w-40 rounded-full" />
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Skeleton className="h-24 w-full rounded-2xl" />
                  <Skeleton className="h-24 w-full rounded-2xl" />
                  <Skeleton className="h-24 w-full rounded-2xl" />
                  <Skeleton className="h-24 w-full rounded-2xl" />
                </div>
              </div>
            ) : latestImport ? (
              <>
                <div className="flex flex-wrap items-center gap-3">
                  <StatusBadge status={latestImport.status ?? "pendente"} />
                  <Badge variant="outline">{latestImport.sistema_origem}</Badge>
                  <Badge variant="outline">
                    Competência detectada: {latestImport.competencia_display}
                  </Badge>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <button
                    type="button"
                    className="rounded-2xl border border-border/60 bg-background/40 p-4 text-left transition-colors hover:bg-background/55"
                    onClick={() => openLatestResultTab("descontados")}
                  >
                    <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
                      Quitados
                    </p>
                    <p className="mt-2 text-3xl font-semibold">
                      {isLatestFinanceiroLoading
                        ? "..."
                        : `${latestFinanceiro?.ok ?? 0}/${latestFinanceiro?.total ?? latestImport?.total_registros ?? 0}`}
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Registros concluídos no resumo financeiro do arquivo.
                    </p>
                  </button>
                  <button
                    type="button"
                    className="rounded-2xl border border-border/60 bg-background/40 p-4 text-left transition-colors hover:bg-background/55"
                    onClick={() => openLatestResultTab("nao-descontados")}
                  >
                    <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
                      Faltando
                    </p>
                    <p className="mt-2 text-3xl font-semibold">
                      {isLatestFinanceiroLoading
                        ? "..."
                        : (latestFinanceiro?.faltando ?? 0)}
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {formatCurrency(latestFinanceiro?.pendente)} ainda
                      pendentes.
                    </p>
                  </button>
                  <button
                    type="button"
                    className="rounded-2xl border border-border/60 bg-background/40 p-4 text-left transition-colors hover:bg-background/55"
                    onClick={() => openLatestMetricDialog("linhas")}
                  >
                    <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
                      Recebido
                    </p>
                    <p className="mt-2 text-3xl font-semibold">
                      {isLatestFinanceiroLoading
                        ? "..."
                        : formatCurrency(latestFinanceiro?.recebido)}
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      de {formatCurrency(latestFinanceiro?.esperado)} esperados.
                    </p>
                  </button>
                  <button
                    type="button"
                    className="rounded-2xl border border-border/60 bg-background/40 p-4 text-left transition-colors hover:bg-background/55"
                    onClick={() => openLatestMetricDialog("linhas")}
                  >
                    <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
                      Percentual recebido
                    </p>
                    <p className="mt-2 text-3xl font-semibold">
                      {isLatestFinanceiroLoading
                        ? "..."
                        : `${(latestFinanceiro?.percentual ?? 0).toFixed(1)}%`}
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Proporção financeira consolidada a partir de
                      `PagamentoMensalidade`.
                    </p>
                  </button>
                </div>
                <div className="flex items-center gap-3">
                  <Button
                    variant="outline"
                    onClick={() => reprocessarMutation.mutate(latestImport.id)}
                    disabled={
                      reprocessarMutation.isPending ||
                      statusIsPending(latestImport.status)
                    }
                  >
                    <RefreshCcwIcon className="mr-2 size-4" />
                    Reprocessar arquivo
                  </Button>
                  {isPolling ? (
                    <span className="text-sm text-muted-foreground">
                      Processando arquivo retorno...
                    </span>
                  ) : null}
                </div>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">
                O sistema mostrará aqui a competência detectada, os contadores
                do processamento e os cards de encerramento quando o primeiro
                arquivo for importado.
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {isInitialLatestLoading ? (
          <>
            <MetricCardSkeleton />
            <MetricCardSkeleton />
            <MetricCardSkeleton />
          </>
        ) : (
          <>
            <ImportMetricCard
              title="Mensalidades Recebidas"
              value={formatCurrency(latestFinanceiro?.mensalidades?.recebido)}
              hint="Clique para abrir a listagem financeira da última importação."
              onClick={() => openLatestMetricDialog("mensalidades")}
            />
            <ImportMetricCard
              title="Valores 30/50 Recebidos"
              value={formatCurrency(latestFinanceiro?.valores_30_50?.recebido)}
              hint="Clique para abrir os associados de 30/50 da última importação."
              onClick={() => openLatestMetricDialog("valores_30_50")}
            />
            <ImportMetricCard
              title="Linhas do Arquivo"
              value={
                latestFinanceiro?.total ?? latestImport?.total_registros ?? 0
              }
              hint="Clique para abrir o consolidado da última importação."
              onClick={() => openLatestMetricDialog("linhas")}
            />
          </>
        )}
      </div>

      <Card
        ref={latestResultSectionRef}
        className="border-border/60 bg-card/80"
      >
        <CardHeader>
          <CardTitle>Resultado da última importação</CardTitle>
          <CardDescription>
            Linhas úteis do arquivo retorno com status bruto ETIPI e status
            normalizado do sistema.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList variant="line">
              <TabsTrigger value="descontados">Descontados</TabsTrigger>
              <TabsTrigger value="nao-descontados">Não descontados</TabsTrigger>
              <TabsTrigger value="pendencias">Pendências</TabsTrigger>
              <TabsTrigger value="encerramentos">Encerramentos</TabsTrigger>
              <TabsTrigger value="novos-ciclos">Novos ciclos</TabsTrigger>
            </TabsList>
            <TabsContent value="descontados" className="pt-4">
              <ItemSection
                title="Baixas automáticas"
                description="Linhas conciliadas e baixadas automaticamente."
                data={descontadosQuery.data?.results ?? []}
                isLoading={activeTab === "descontados" && isInitialItemsLoading}
                emptyMessage="Nenhum desconto efetivado nesta importação."
              />
            </TabsContent>
            <TabsContent value="nao-descontados" className="pt-4">
              <ItemSection
                title="Não descontados"
                description="Itens rejeitados pelo ETIPI com marcação de não descontado."
                data={naoDescontadosQuery.data?.results ?? []}
                isLoading={
                  activeTab === "nao-descontados" && isInitialItemsLoading
                }
                emptyMessage="Nenhum não descontado nesta importação."
              />
            </TabsContent>
            <TabsContent value="pendencias" className="pt-4">
              <ItemSection
                title="Pendências manuais"
                description="Itens que exigem revisão manual antes de qualquer baixa."
                data={pendenciasQuery.data?.results ?? []}
                isLoading={activeTab === "pendencias" && isInitialItemsLoading}
                emptyMessage="Nenhuma pendência manual nesta importação."
              />
            </TabsContent>
            <TabsContent value="encerramentos" className="pt-4">
              <ItemSection
                title="Encerramentos previstos"
                description="Itens que fecharam o ciclo atual do associado."
                data={encerramentosQuery.data?.results ?? []}
                isLoading={
                  activeTab === "encerramentos" && isInitialItemsLoading
                }
                emptyMessage="Nenhum encerramento previsto nesta importação."
              />
            </TabsContent>
            <TabsContent value="novos-ciclos" className="pt-4">
              <ItemSection
                title="Novos ciclos abertos"
                description="Associados que tiveram ciclo renovado automaticamente."
                data={novosCiclosQuery.data?.results ?? []}
                isLoading={
                  activeTab === "novos-ciclos" && isInitialItemsLoading
                }
                emptyMessage="Nenhum novo ciclo aberto nesta importação."
              />
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      <Card className="border-border/60 bg-card/80">
        <CardHeader>
          <CardTitle>Histórico de importações</CardTitle>
          <CardDescription>
            Últimos uploads com referência extraída, contadores do processamento
            e status do arquivo.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <CalendarCompetencia
              value={parseMonthValue(historyCompetencia)}
              onChange={(value) =>
                setHistoryCompetencia(formatMonthValue(value))
              }
            />
            <Select value={historyStatus} onValueChange={setHistoryStatus}>
              <SelectTrigger className="min-w-44 rounded-2xl bg-card/60">
                <SelectValue placeholder="Todos os status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="todos">Todos os status</SelectItem>
                <SelectItem value="concluido">Concluído</SelectItem>
                <SelectItem value="processando">Processando</SelectItem>
                <SelectItem value="pendente">Pendente</SelectItem>
                <SelectItem value="erro">Erro</SelectItem>
              </SelectContent>
            </Select>
            <Button
              variant="outline"
              className="rounded-2xl"
              onClick={() => {
                setHistoryCompetencia("");
                setHistoryStatus("todos");
              }}
            >
              Limpar filtros
            </Button>
          </div>
          {isInitialHistoryLoading ? (
            <HistoryTableSkeleton />
          ) : (
            <DataTable
              columns={historyColumns}
              data={historyQuery.data?.results ?? []}
              currentPage={historyPage}
              totalPages={totalPages(historyQuery.data?.count, 5)}
              onPageChange={setHistoryPage}
              emptyMessage="Nenhuma importação registrada."
            />
          )}
        </CardContent>
      </Card>

      {dryRunPreview ? (
        <DryRunModal
          open
          onOpenChange={(open) => {
            if (open || isDryRunBusy) {
              return;
            }
            cancelarMutation.mutate(dryRunPreview.arquivoId);
          }}
          arquivoNome={dryRunPreview.arquivoNome}
          competenciaDisplay={dryRunPreview.competenciaDisplay}
          dryRunData={dryRunPreview.dryRunData}
          onConfirm={() => confirmarMutation.mutate(dryRunPreview.arquivoId)}
          onCancel={() => cancelarMutation.mutate(dryRunPreview.arquivoId)}
          isConfirming={confirmarMutation.isPending}
          isCanceling={cancelarMutation.isPending}
        />
      ) : null}

      <Dialog
        open={Boolean(latestMetricDialogConfig)}
        onOpenChange={(open) => {
          if (!open) {
            setLatestMetricDialogConfig(null);
          }
        }}
      >
        <DialogContent className="grid max-h-[calc(100vh-2rem)] max-w-[92vw] grid-rows-[auto_auto_minmax(0,1fr)] overflow-hidden border-border/60 bg-background/95 sm:max-w-[80rem]">
          <DialogHeader>
            <DialogTitle>
              {latestMetricDialogConfig?.title ??
                "Detalhamento da última importação"}
            </DialogTitle>
            <DialogDescription>
              {latestMetricDialogConfig?.description ??
                "Listagem financeira consolidada do último arquivo retorno."}
            </DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <Input
              value={latestMetricSearch}
              onChange={(event) => setLatestMetricSearch(event.target.value)}
              placeholder="Buscar por associado, CPF, matrícula ou agente..."
              className="rounded-2xl border-border/60 bg-card/60 lg:max-w-lg"
            />
            <ReportExportDialog
              hideScope
              label="Exportar"
              onExport={(_, fmt) =>
                exportRows(
                  fmt,
                  latestMetricDialogConfig?.title ??
                    "Detalhamento da última importação",
                  "ultima-importacao-detalhamento",
                  financeiroExportColumns(),
                  filteredLatestMetricRows,
                )
              }
            />
          </div>
          <div className="min-h-0 overflow-x-auto overflow-y-auto">
            <DataTable
              columns={latestFinanceiroColumns}
              data={filteredLatestMetricRows}
              pageSize={10}
              pageSizeOptions={DETAIL_PAGE_SIZE_OPTIONS}
              className={cn(
                "rounded-[1.35rem] border border-border/60 bg-background/55 shadow-none",
              )}
              tableClassName="min-w-[72rem]"
              emptyMessage={
                latestMetricDialogConfig?.emptyMessage ??
                "Nenhum registro encontrado para o indicador selecionado."
              }
            />
          </div>
        </DialogContent>
      </Dialog>

      <AssociadoDetailsDialog
        associadoId={selectedAssociadoId}
        open={selectedAssociadoId !== null}
        onOpenChange={(open) => {
          if (!open) {
            setSelectedAssociadoId(null);
          }
        }}
      />
    </div>
  );
}
