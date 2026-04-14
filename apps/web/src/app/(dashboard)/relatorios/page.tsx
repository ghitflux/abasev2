"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ActivityIcon,
  DownloadIcon,
  FileCogIcon,
  FileSpreadsheetIcon,
  RefreshCcwIcon,
  WalletIcon,
} from "lucide-react";
import { toast } from "sonner";

import type { RelatorioGeradoItem, RelatorioResumo } from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import { formatCurrency, formatDateTime } from "@/lib/formatters";
import { usePermissions } from "@/hooks/use-permissions";
import DataTable, { type DataTableColumn } from "@/components/shared/data-table";
import EmptyState from "@/components/shared/empty-state";
import ReportExportDialog, {
  type ReportExportFilters,
} from "@/components/shared/report-export-dialog";
import { ListRouteSkeleton, MetricCardSkeleton } from "@/components/shared/page-skeletons";
import StatsCard from "@/components/shared/stats-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const EXPORT_OPTIONS = [
  {
    tipo: "associados" as const,
    title: "Associados",
    description: "Base cadastral com status, orgao e agente responsavel.",
  },
  {
    tipo: "tesouraria" as const,
    title: "Tesouraria",
    description: "Contratos, mensalidades, repasses e status financeiro.",
  },
  {
    tipo: "refinanciamentos" as const,
    title: "Refinanciamentos",
    description: "Historico completo de solicitacoes, aprovacoes e efetivacoes.",
  },
  {
    tipo: "importacao" as const,
    title: "Importacao",
    description: "Historico do arquivo retorno com processamento e inconsistencias.",
  },
];

type ReportType = (typeof EXPORT_OPTIONS)[number]["tipo"];
type ReportFormat = "csv" | "json" | "pdf" | "xlsx";

const REPORT_LABELS: Record<ReportType, string> = {
  associados: "Associados",
  tesouraria: "Tesouraria",
  refinanciamentos: "Refinanciamentos",
  importacao: "Importacao",
};

function inferReportTypeLabel(name: string) {
  const normalized = name.toLowerCase();
  return (
    EXPORT_OPTIONS.find((option) => normalized.startsWith(`${option.tipo}_`))?.title ?? "Exportacao"
  );
}

function downloadRelatorio(item: RelatorioGeradoItem) {
  const link = document.createElement("a");
  link.href = `/api/backend/relatorios/${item.id}/download`;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  document.body.appendChild(link);
  link.click();
  link.remove();
}

export default function RelatoriosPage() {
  const queryClient = useQueryClient();
  const { hasRole, status } = usePermissions();

  const resumoQuery = useQuery({
    queryKey: ["relatorios-resumo"],
    queryFn: () => apiFetch<RelatorioResumo>("relatorios/resumo"),
    enabled: hasRole("ADMIN"),
  });

  const historicoQuery = useQuery({
    queryKey: ["relatorios-historico"],
    queryFn: () => apiFetch<RelatorioGeradoItem[]>("relatorios"),
    enabled: hasRole("ADMIN"),
  });

  const exportMutation = useMutation({
    mutationFn: (payload: {
      tipo: ReportType;
      formato: ReportFormat;
      filtros?: Record<string, unknown>;
    }) =>
      apiFetch<RelatorioGeradoItem>("relatorios/exportar", {
        method: "POST",
        body: payload,
      }),
    onSuccess: (item) => {
      toast.success("Relatorio gerado com sucesso.");
      void queryClient.invalidateQueries({ queryKey: ["relatorios-historico"] });
      downloadRelatorio(item);
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Falha ao gerar relatorio.");
    },
  });

  const columns = React.useMemo<DataTableColumn<RelatorioGeradoItem>[]>(
    () => [
      {
        id: "nome",
        header: "Arquivo",
        cell: (row) => (
          <div>
            <p className="font-medium text-foreground">{row.nome}</p>
            <p className="text-xs text-muted-foreground">
              {inferReportTypeLabel(row.nome)} persistido em disco
            </p>
          </div>
        ),
      },
      {
        id: "formato",
        header: "Formato",
        cell: (row) => <Badge variant="outline">{row.formato.toUpperCase()}</Badge>,
      },
      {
        id: "created_at",
        header: "Gerado em",
        cell: (row) => formatDateTime(row.created_at),
      },
      {
        id: "acoes",
        header: "Acoes",
        cell: (row) => (
          <Button variant="outline" size="sm" onClick={() => downloadRelatorio(row)}>
            <DownloadIcon className="size-4" />
            Baixar
          </Button>
        ),
      },
    ],
    [],
  );

  const resumo = resumoQuery.data;
  const historico = historicoQuery.data ?? [];

  const handleStructuredExport = React.useCallback(
    (tipo: ReportType) =>
      async (
        filters: ReportExportFilters,
        formato: "pdf" | "xlsx",
      ) => {
        exportMutation.mutate({
          tipo,
          formato,
          filtros: {
            columns: filters.columns,
          },
        });
      },
    [exportMutation],
  );

  if (status !== "authenticated") {
    return <ListRouteSkeleton metricCards={4} />;
  }

  if (!hasRole("ADMIN")) {
    return (
      <EmptyState
        title="Acesso restrito"
        description="O modulo de relatorios administrativos fica disponivel apenas para perfil ADMIN."
      />
    );
  }

  return (
    <div className="space-y-8">
      <section className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div className="space-y-2">
          <h1 className="text-3xl font-semibold text-foreground">Relatorios operacionais</h1>
          <p className="max-w-3xl text-sm text-muted-foreground">
            Resumo executivo do sistema e exportacoes persistidas para auditoria, sem rota fantasma
            e sem placeholder.
          </p>
        </div>
        {resumo?.ultima_importacao ? (
          <div className="rounded-[1.5rem] border border-border/60 bg-card/60 px-4 py-3 text-sm text-muted-foreground">
            Ultima importacao: <span className="font-medium text-foreground">{resumo.ultima_importacao.arquivo_nome}</span>
          </div>
        ) : null}
      </section>

      {resumoQuery.isLoading && !resumo ? (
        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <MetricCardSkeleton key={index} />
          ))}
        </section>
      ) : resumo ? (
        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <StatsCard
            title="Associados ativos"
            value={String(resumo.associados_ativos)}
            delta={`${resumo.associados_em_analise} em analise`}
            tone="positive"
            icon={ActivityIcon}
          />
          <StatsCard
            title="Contratos ativos"
            value={String(resumo.contratos_ativos)}
            delta={`${resumo.contratos_em_analise} em analise`}
            tone="neutral"
            icon={WalletIcon}
          />
          <StatsCard
            title="Refinanciamentos"
            value={String(resumo.refinanciamentos_efetivados)}
            delta={`${resumo.refinanciamentos_pendentes} pendentes`}
            tone="positive"
            icon={RefreshCcwIcon}
          />
          <StatsCard
            title="Baixas no mes"
            value={formatCurrency(resumo.valor_baixado_mes)}
            delta={`${resumo.baixas_mes} parcelas descontadas`}
            tone="warning"
            icon={FileSpreadsheetIcon}
          />
        </section>
      ) : (
        <EmptyState
          title="Resumo indisponivel"
          description="Nao foi possivel carregar os indicadores executivos de relatorios."
        />
      )}

      <section className="grid gap-4 xl:grid-cols-2">
        {EXPORT_OPTIONS.map((option) => (
          <Card
            key={option.tipo}
            data-testid={`relatorio-card-${option.tipo}`}
            className="rounded-[1.75rem] border-border/60 bg-card/70 shadow-xl shadow-black/20"
          >
            <CardHeader>
              <CardTitle>{option.title}</CardTitle>
              <CardDescription>{option.description}</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-3">
            <ReportExportDialog
              hideScope
              disabled={exportMutation.isPending}
              label="Exportar PDF / XLS"
              reportType={option.tipo}
              onExport={handleStructuredExport(option.tipo)}
            />
            <Button
              aria-label={`Exportar ${REPORT_LABELS[option.tipo]} em CSV`}
              onClick={() => exportMutation.mutate({ tipo: option.tipo, formato: "csv" })}
              disabled={exportMutation.isPending}
              variant="outline"
            >
              <FileSpreadsheetIcon className="size-4" />
              Exportar CSV
            </Button>
            <Button
              aria-label={`Exportar ${REPORT_LABELS[option.tipo]} em JSON`}
              variant="outline"
              onClick={() => exportMutation.mutate({ tipo: option.tipo, formato: "json" })}
              disabled={exportMutation.isPending}
              >
                <FileCogIcon className="size-4" />
                Exportar JSON
              </Button>
            </CardContent>
          </Card>
        ))}
      </section>

      <section className="space-y-4">
        <div>
          <h2 className="text-2xl font-semibold text-foreground">Historico de exportacoes</h2>
          <p className="text-sm text-muted-foreground">
            Cada geracao fica registrada e pode ser baixada novamente a qualquer momento.
          </p>
        </div>
        <DataTable
          columns={columns}
          data={historico}
          emptyMessage="Nenhum relatorio foi gerado ainda."
          loading={historicoQuery.isLoading}
          skeletonRows={6}
        />
      </section>
    </div>
  );
}
