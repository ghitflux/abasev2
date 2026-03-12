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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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
import { maskCPFCNPJ } from "@/lib/masks";

const TXT_ACCEPT = { "text/plain": [".txt"] };
const ITEM_PAGE_SIZE = 5;

function extractResumoValue(arquivo: { resumo?: Record<string, unknown> } | undefined, key: string) {
  const value = arquivo?.resumo?.[key];
  if (typeof value === "number") return value;
  if (typeof value === "string") return Number.parseInt(value, 10) || 0;
  return 0;
}

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
};

function ItemSection({ title, description, data, emptyMessage }: ItemSectionProps) {
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
      <DataTable columns={columns} data={data} emptyMessage={emptyMessage} />
    </div>
  );
}

export default function ImportacaoPage() {
  const queryClient = useQueryClient();
  const [historyPage, setHistoryPage] = React.useState(1);
  const [activeTab, setActiveTab] = React.useState("descontados");
  const [isPolling, setIsPolling] = React.useState(false);

  const historyQuery = useV1ImportacaoArquivoRetornoList(
    { page: historyPage, page_size: 5 },
    { query: { refetchInterval: isPolling ? 3000 : false } },
  );
  const latestQuery = useV1ImportacaoArquivoRetornoUltimaRetrieve({
    query: { retry: false, refetchInterval: isPolling ? 3000 : false },
  });

  const latestImport = latestQuery.data ?? historyQuery.data?.results?.[0];
  const latestId = latestImport?.id ?? 0;

  React.useEffect(() => {
    setIsPolling(statusIsPending(latestImport?.status));
  }, [latestImport?.status]);

  function invalidateImportacao() {
    void queryClient.invalidateQueries({
      predicate: (query) =>
        JSON.stringify(query.queryKey).includes("/api/v1/importacao/arquivo-retorno/"),
    });
  }

  const uploadMutation = useMutation<ArquivoRetornoDetail, Error, File>({
    mutationFn: async (file) => {
      const formData = new FormData();
      formData.append("arquivo", file);
      return apiFetch<ArquivoRetornoDetail>("importacao/arquivo-retorno/upload", {
        method: "POST",
        formData,
      });
    },
    onSuccess: (data) => {
      toast.success("Arquivo enviado com sucesso.");
      setIsPolling(statusIsPending(data.status));
      invalidateImportacao();
    },
    onError: (error) => {
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

  const descontadosQuery = useV1ImportacaoArquivoRetornoDescontadosList(
    latestId,
    { page_size: ITEM_PAGE_SIZE },
    { query: { enabled: !!latestId } },
  );
  const naoDescontadosQuery = useV1ImportacaoArquivoRetornoNaoDescontadosList(
    latestId,
    { page_size: ITEM_PAGE_SIZE },
    { query: { enabled: !!latestId } },
  );
  const pendenciasQuery = useV1ImportacaoArquivoRetornoPendenciasManuaisList(
    latestId,
    { page_size: ITEM_PAGE_SIZE },
    { query: { enabled: !!latestId } },
  );
  const encerramentosQuery = useV1ImportacaoArquivoRetornoEncerramentosList(
    latestId,
    { page_size: ITEM_PAGE_SIZE },
    { query: { enabled: !!latestId } },
  );
  const novosCiclosQuery = useV1ImportacaoArquivoRetornoNovosCiclosList(
    latestId,
    { page_size: ITEM_PAGE_SIZE },
    { query: { enabled: !!latestId } },
  );

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
      id: "nao_encontrados",
      header: "Não encontrados",
      accessor: "nao_encontrados",
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
              onUpload={(file) => uploadMutation.mutate(file)}
            />
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
            {latestImport ? (
              <>
                <div className="flex flex-wrap items-center gap-3">
                  <StatusBadge status={latestImport.status ?? "pendente"} />
                  <Badge variant="outline">{latestImport.sistema_origem}</Badge>
                  <Badge variant="outline">Competência detectada: {latestImport.competencia_display}</Badge>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="rounded-2xl border border-border/60 bg-background/40 p-4">
                    <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">Efetivados</p>
                    <p className="mt-2 text-3xl font-semibold">{extractResumoValue(latestImport, "efetivados")}</p>
                  </div>
                  <div className="rounded-2xl border border-border/60 bg-background/40 p-4">
                    <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">Não descontados</p>
                    <p className="mt-2 text-3xl font-semibold">{extractResumoValue(latestImport, "nao_descontados")}</p>
                  </div>
                  <div className="rounded-2xl border border-border/60 bg-background/40 p-4">
                    <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">Pendências manuais</p>
                    <p className="mt-2 text-3xl font-semibold">{extractResumoValue(latestImport, "pendencias_manuais")}</p>
                  </div>
                  <div className="rounded-2xl border border-border/60 bg-background/40 p-4">
                    <p className="text-xs uppercase tracking-[0.24em] text-muted-foreground">Não encontrados</p>
                    <p className="mt-2 text-3xl font-semibold">{extractResumoValue(latestImport, "nao_encontrado")}</p>
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
        <Card className="border-border/60 bg-card/80">
          <CardHeader>
            <CardDescription>Associados Descontados</CardDescription>
            <CardTitle className="text-3xl">{extractResumoValue(latestImport, "baixa_efetuada")}</CardTitle>
          </CardHeader>
        </Card>
        <Card className="border-border/60 bg-card/80">
          <CardHeader>
            <CardDescription>Previsão de Encerramento</CardDescription>
            <CardTitle className="text-3xl">{extractResumoValue(latestImport, "encerramentos")}</CardTitle>
          </CardHeader>
        </Card>
        <Card className="border-border/60 bg-card/80">
          <CardHeader>
            <CardDescription>Novos Ciclos Abertos</CardDescription>
            <CardTitle className="text-3xl">{extractResumoValue(latestImport, "novos_ciclos")}</CardTitle>
          </CardHeader>
        </Card>
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
                emptyMessage="Nenhum desconto efetivado nesta importação."
              />
            </TabsContent>
            <TabsContent value="nao-descontados" className="pt-4">
              <ItemSection
                title="Não descontados"
                description="Itens rejeitados pelo ETIPI com marcação de não descontado."
                data={naoDescontadosQuery.data?.results ?? []}
                emptyMessage="Nenhum não descontado nesta importação."
              />
            </TabsContent>
            <TabsContent value="pendencias" className="pt-4">
              <ItemSection
                title="Pendências manuais"
                description="Itens que exigem revisão manual antes de qualquer baixa."
                data={pendenciasQuery.data?.results ?? []}
                emptyMessage="Nenhuma pendência manual nesta importação."
              />
            </TabsContent>
            <TabsContent value="encerramentos" className="pt-4">
              <ItemSection
                title="Encerramentos previstos"
                description="Itens que fecharam o ciclo atual do associado."
                data={encerramentosQuery.data?.results ?? []}
                emptyMessage="Nenhum encerramento previsto nesta importação."
              />
            </TabsContent>
            <TabsContent value="novos-ciclos" className="pt-4">
              <ItemSection
                title="Novos ciclos abertos"
                description="Associados que tiveram ciclo renovado automaticamente."
                data={novosCiclosQuery.data?.results ?? []}
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
          <DataTable
            columns={historyColumns}
            data={historyQuery.data?.results ?? []}
            currentPage={historyPage}
            totalPages={totalPages(historyQuery.data?.count, 5)}
            onPageChange={setHistoryPage}
            emptyMessage="Nenhuma importação registrada."
          />
        </CardContent>
      </Card>
    </div>
  );
}
