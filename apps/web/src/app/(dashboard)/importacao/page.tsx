"use client";

import * as React from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { RefreshCcwIcon } from "lucide-react";
import { toast } from "sonner";

import FileUploadDropzone from "@/components/custom/file-upload-dropzone";
import StatusBadge from "@/components/custom/status-badge";
import DataTable, { type DataTableColumn } from "@/components/shared/data-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import DryRunModal from "@/components/importacao/dry-run-modal";
import {
  useV1ImportacaoArquivoRetornoDescontadosList,
  useV1ImportacaoArquivoRetornoEncerramentosList,
  useV1ImportacaoArquivoRetornoList,
  useV1ImportacaoArquivoRetornoNaoDescontadosList,
  useV1ImportacaoArquivoRetornoNovosCiclosList,
  useV1ImportacaoArquivoRetornoPendenciasManuaisList,
  useV1ImportacaoArquivoRetornoUltimaRetrieve,
} from "@/gen";
import type { ArquivoRetornoDetail, ArquivoRetornoItem, ArquivoRetornoList } from "@/gen/models";
import { apiFetch } from "@/lib/api/client";
import { formatCurrency, formatDateTime } from "@/lib/formatters";
import {
  getArquivoFinanceiroResumo,
  type ArquivoRetornoWithFinanceiro,
} from "@/lib/importacao-financeiro";
import { maskCPFCNPJ } from "@/lib/masks";

const TXT_ACCEPT = { "text/plain": [".txt"] };
const ITEM_PAGE_SIZE = 5;
type DryRunPreviewState = {
  arquivoId: number;
  arquivoNome: string;
  competenciaDisplay: string;
  dryRunData: NonNullable<ArquivoRetornoDetail["dry_run_resultado"]>;
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

function ItemSection({ title, description, data, emptyMessage, isLoading = false }: ItemSectionProps) {
  const columns: DataTableColumn<ArquivoRetornoItem>[] = [
    {
      id: "nome",
      header: "Servidor",
      cell: (row) => (
        <div>
          <p className="font-medium text-foreground">{row.nome_servidor}</p>
          <p className="text-xs text-muted-foreground">{row.matricula_servidor}</p>
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
      cell: (row) => <Badge variant="outline">{row.status_codigo || "-"}</Badge>,
    },
    {
      id: "status_desconto",
      header: "Sistema",
      cell: (row) => (
        <StatusBadge status={row.status_desconto ?? row.resultado_processamento ?? "pendente"} />
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
  const [historyPage, setHistoryPage] = React.useState(1);
  const [activeTab, setActiveTab] = React.useState("descontados");
  const [isPolling, setIsPolling] = React.useState(false);
  const [uploadFile, setUploadFile] = React.useState<File | null>(null);
  const [uploadProgress, setUploadProgress] = React.useState(0);
  const [dryRunPreview, setDryRunPreview] = React.useState<DryRunPreviewState | null>(null);

  const historyQuery = useV1ImportacaoArquivoRetornoList(
    { page: historyPage, page_size: 5 },
    {
      query: {
        refetchInterval: isPolling ? 3000 : false,
        staleTime: 30 * 1000,
        placeholderData: (previousData) => previousData,
      },
    },
  );
  const latestQuery = useV1ImportacaoArquivoRetornoUltimaRetrieve({
    query: {
      retry: false,
      refetchInterval: isPolling ? 3000 : false,
      staleTime: 15 * 1000,
      placeholderData: (previousData) => previousData,
    },
  });

  const latestImport = latestQuery.data ?? historyQuery.data?.results?.[0];
  const latestImportWithFinanceiro = latestImport as ArquivoRetornoWithFinanceiro | undefined;
  const latestFinanceiro = getArquivoFinanceiroResumo(latestImportWithFinanceiro);
  const latestId = latestImport?.id ?? 0;

  React.useEffect(() => {
    setIsPolling(statusIsPending(latestImport?.status));
    if (!statusIsPending(latestImport?.status)) {
      void queryClient.invalidateQueries({ queryKey: ["tesouraria-duplicidades-sidebar"] });
    }
  }, [latestImport?.status, queryClient]);

  function invalidateImportacao() {
    void queryClient.invalidateQueries({
      predicate: (query) =>
        JSON.stringify(query.queryKey).includes("/api/v1/importacao/arquivo-retorno/"),
    });
    void queryClient.invalidateQueries({ queryKey: ["importacao-duplicidades-financeiras"] });
    void queryClient.invalidateQueries({ queryKey: ["tesouraria-duplicidades-sidebar"] });
  }

  const uploadMutation = useMutation<ArquivoRetornoDetail, Error, File>({
    mutationFn: async (file) => {
      setUploadFile(file);
      setUploadProgress(0);
      const formData = new FormData();
      formData.append("arquivo", file);
      return apiFetch<ArquivoRetornoDetail>("importacao/arquivo-retorno/upload", {
        method: "POST",
        formData,
        onUploadProgress: (progress) => {
          setUploadProgress(progress.percent);
        },
      });
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
      toast.error(error instanceof Error ? error.message : "Falha no upload do arquivo.");
    },
  });

  const reprocessarMutation = useMutation<ArquivoRetornoDetail, Error, number>({
    mutationFn: async (id) =>
      apiFetch<ArquivoRetornoDetail>(`importacao/arquivo-retorno/${id}/reprocessar`, {
        method: "POST",
      }),
    onSuccess: () => {
      toast.success("Reprocessamento solicitado.");
      setIsPolling(true);
      invalidateImportacao();
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Falha ao reprocessar o arquivo.");
    },
  });

  const confirmarMutation = useMutation<ArquivoRetornoDetail, Error, number>({
    mutationFn: async (id) =>
      apiFetch<ArquivoRetornoDetail>(`importacao/arquivo-retorno/${id}/confirmar`, {
        method: "POST",
      }),
    onSuccess: (data) => {
      setDryRunPreview(null);
      setIsPolling(statusIsPending(data.status));
      toast.success("Importação confirmada. Processando...");
      invalidateImportacao();
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : "Falha ao confirmar a importação.",
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
        error instanceof Error ? error.message : "Falha ao cancelar a importação.",
      );
    },
  });
  const isDryRunBusy = confirmarMutation.isPending || cancelarMutation.isPending;

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
  const isInitialItemsLoading = activeItemsQuery.isLoading && !activeItemsQuery.data;
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
            <CardTitle className="text-2xl">Importar Relatório de Retorno</CardTitle>
            <CardDescription>
              Formato esperado: relatório ETIPI/iNETConsig em <code>.txt</code>. A competência e o
              sistema de origem são extraídos automaticamente do arquivo.
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
                  <span className="text-muted-foreground">{uploadProgress}%</span>
                </div>
                <Progress value={Math.max(uploadProgress, 4)} className="mt-3 h-2.5" />
              </div>
            ) : null}
            {isPolling ? (
              <div className="rounded-2xl border border-border/60 bg-background/40 p-4">
                <div className="flex items-center justify-between gap-3 text-sm">
                  <span className="font-medium text-foreground">Processando arquivo retorno</span>
                  <span className="text-muted-foreground">
                    {processados}/{Math.max(totalRegistros, processados)}
                  </span>
                </div>
                <Progress value={Math.max(processamentoPercentual, 8)} className="mt-3 h-2.5" />
              </div>
            ) : null}
            <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
              <Badge variant="outline" className="border-primary/30 text-primary">
                Competência detectada no cabeçalho
              </Badge>
              <Badge variant="outline">Sem seleção manual de órgão</Badge>
              <Badge variant="outline">Upload multipart + processamento assíncrono</Badge>
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
                  <Badge variant="outline">Competência detectada: {latestImport.competencia_display}</Badge>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="rounded-2xl border border-border/60 bg-background/40 p-4">
                    <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">Quitados</p>
                    <p className="mt-2 text-3xl font-semibold">
                      {latestFinanceiro?.ok ?? 0}/{latestFinanceiro?.total ?? latestImport?.total_registros ?? 0}
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Registros concluídos no resumo financeiro do arquivo.
                    </p>
                  </div>
                  <div className="rounded-2xl border border-border/60 bg-background/40 p-4">
                    <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">Faltando</p>
                    <p className="mt-2 text-3xl font-semibold">{latestFinanceiro?.faltando ?? 0}</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      {formatCurrency(latestFinanceiro?.pendente)} ainda pendentes.
                    </p>
                  </div>
                  <div className="rounded-2xl border border-border/60 bg-background/40 p-4">
                    <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">Recebido</p>
                    <p className="mt-2 text-3xl font-semibold">{formatCurrency(latestFinanceiro?.recebido)}</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      de {formatCurrency(latestFinanceiro?.esperado)} esperados.
                    </p>
                  </div>
                  <div className="rounded-2xl border border-border/60 bg-background/40 p-4">
                    <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">Percentual recebido</p>
                    <p className="mt-2 text-3xl font-semibold">
                      {(latestFinanceiro?.percentual ?? 0).toFixed(1)}%
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Proporção financeira consolidada a partir de `PagamentoMensalidade`.
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <Button
                    variant="outline"
                    onClick={() => reprocessarMutation.mutate(latestImport.id)}
                    disabled={reprocessarMutation.isPending || statusIsPending(latestImport.status)}
                  >
                    <RefreshCcwIcon className="mr-2 size-4" />
                    Reprocessar arquivo
                  </Button>
                  {isPolling ? (
                    <span className="text-sm text-muted-foreground">Processando arquivo retorno...</span>
                  ) : null}
                </div>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">
                O sistema mostrará aqui a competência detectada, os contadores do processamento e os
                cards de encerramento quando o primeiro arquivo for importado.
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
            <Card className="border-border/60 bg-card/80">
              <CardHeader>
                <CardDescription>Mensalidades Recebidas</CardDescription>
                <CardTitle className="text-3xl">
                  {formatCurrency(latestFinanceiro?.mensalidades?.recebido)}
                </CardTitle>
              </CardHeader>
            </Card>
            <Card className="border-border/60 bg-card/80">
              <CardHeader>
                <CardDescription>Valores 30/50 Recebidos</CardDescription>
                <CardTitle className="text-3xl">
                  {formatCurrency(latestFinanceiro?.valores_30_50?.recebido)}
                </CardTitle>
              </CardHeader>
            </Card>
            <Card className="border-border/60 bg-card/80">
              <CardHeader>
                <CardDescription>Linhas do Arquivo</CardDescription>
                <CardTitle className="text-3xl">
                  {latestFinanceiro?.total ?? latestImport?.total_registros ?? 0}
                </CardTitle>
              </CardHeader>
            </Card>
          </>
        )}
      </div>

      <Card className="border-border/60 bg-card/80">
        <CardHeader>
          <CardTitle>Resultado da última importação</CardTitle>
          <CardDescription>
            Linhas úteis do arquivo retorno com status bruto ETIPI e status normalizado do sistema.
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
                isLoading={activeTab === "nao-descontados" && isInitialItemsLoading}
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
                isLoading={activeTab === "encerramentos" && isInitialItemsLoading}
                emptyMessage="Nenhum encerramento previsto nesta importação."
              />
            </TabsContent>
            <TabsContent value="novos-ciclos" className="pt-4">
              <ItemSection
                title="Novos ciclos abertos"
                description="Associados que tiveram ciclo renovado automaticamente."
                data={novosCiclosQuery.data?.results ?? []}
                isLoading={activeTab === "novos-ciclos" && isInitialItemsLoading}
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
            Últimos uploads com referência extraída, contadores do processamento e status do arquivo.
          </CardDescription>
        </CardHeader>
        <CardContent>
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

    </div>
  );
}
