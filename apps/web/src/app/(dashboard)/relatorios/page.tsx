"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ActivityIcon,
  ChevronDownIcon,
  DownloadIcon,
  FileSpreadsheetIcon,
  RefreshCcwIcon,
  WalletIcon,
} from "lucide-react";
import { toast } from "sonner";

import type { RelatorioGeradoItem, RelatorioResumo, SimpleUser } from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import { formatCurrency, formatDateTime } from "@/lib/formatters";
import { usePermissions } from "@/hooks/use-permissions";
import SearchableSelect from "@/components/custom/searchable-select";
import DataTable, { type DataTableColumn } from "@/components/shared/data-table";
import EmptyState from "@/components/shared/empty-state";
import { ListRouteSkeleton, MetricCardSkeleton } from "@/components/shared/page-skeletons";
import StatsCard from "@/components/shared/stats-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import DatePicker from "@/components/custom/date-picker";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";

type ReportFormat = "csv" | "pdf" | "xlsx";
type AssociadoPagamentoReportType =
  | "associados_ativos_com_1_parcela_paga"
  | "associados_ativos_com_3_parcelas_pagas";

const ASSOCIADO_PAGAMENTO_EXPORT_OPTIONS = [
  {
    tipo: "associados_ativos_com_1_parcela_paga" as const,
    title: "Ativos com 1 parcela paga",
    description:
      "Associados ativos com pelo menos uma parcela paga no período, com filtro por agente e faixa de mensalidade.",
  },
  {
    tipo: "associados_ativos_com_3_parcelas_pagas" as const,
    title: "Ativos com 3 parcelas pagas",
    description:
      "Associados ativos com no mínimo três parcelas pagas no período, com filtro por agente e faixa de mensalidade.",
  },
] as const;

const MENSALIDADE_FAIXAS = [
  { value: "ate_100", label: "Até R$ 100" },
  { value: "100_200", label: "R$ 100 a R$ 199,99" },
  { value: "200_300", label: "R$ 200 a R$ 299,99" },
  { value: "300_500", label: "R$ 300 a R$ 499,99" },
  { value: "acima_500", label: "Acima de R$ 500" },
] as const;

function inferReportTypeLabel(name: string) {
  const normalized = name.toLowerCase();
  return (
    ASSOCIADO_PAGAMENTO_EXPORT_OPTIONS.find((option) =>
      normalized.startsWith(`${option.tipo}_`),
    )?.title ?? "Exportacao"
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

type AgentFilterUser = SimpleUser & {
  email?: string;
  primary_role?: string | null;
};

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

  const agentesQuery = useQuery({
    queryKey: ["relatorios-agentes"],
    queryFn: () => apiFetch<AgentFilterUser[]>("tesouraria/contratos/agentes"),
    enabled: hasRole("ADMIN"),
    staleTime: 5 * 60 * 1000,
  });

  const exportMutation = useMutation({
    mutationFn: (payload: {
      tipo: AssociadoPagamentoReportType;
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
  const agentOptions = React.useMemo(
    () =>
      (agentesQuery.data ?? []).map((item) => ({
        value: String(item.id),
        label: item.full_name || item.email || `Usuário ${item.id}`,
      })),
    [agentesQuery.data],
  );

  const handleAssociadoPagamentoExport = React.useCallback(
    (
      tipo: AssociadoPagamentoReportType,
      filters: {
        dataInicio?: string;
        dataFim?: string;
        agenteId?: string;
        faixasMensalidade?: string[];
      },
      formato: ReportFormat,
    ) => {
      exportMutation.mutate({
        tipo,
        formato,
        filtros: {
          data_inicio: filters.dataInicio || undefined,
          data_fim: filters.dataFim || undefined,
          agente_id: filters.agenteId || undefined,
          faixa_mensalidade: filters.faixasMensalidade?.length
            ? filters.faixasMensalidade
            : undefined,
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
        {ASSOCIADO_PAGAMENTO_EXPORT_OPTIONS.map((option) => (
          <Card
            key={option.tipo}
            data-testid={`relatorio-card-${option.tipo}`}
            className="rounded-[1.75rem] border-border/60 bg-card/70 shadow-xl shadow-black/20"
          >
            <CardHeader>
              <CardTitle>{option.title}</CardTitle>
              <CardDescription>{option.description}</CardDescription>
            </CardHeader>
            <CardContent>
              <AssociadoPagamentoReportDialog
                disabled={exportMutation.isPending}
                title={option.title}
                description={option.description}
                agentOptions={agentOptions}
                onExport={(filters, formato) =>
                  handleAssociadoPagamentoExport(option.tipo, filters, formato)
                }
              />
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

function formatIsoDate(value?: Date) {
  if (!value) return "";
  return value.toISOString().slice(0, 10);
}

function AssociadoPagamentoReportDialog({
  disabled,
  title,
  description,
  agentOptions,
  onExport,
}: {
  disabled?: boolean;
  title: string;
  description: string;
  agentOptions: Array<{ value: string; label: string }>;
  onExport: (
    filters: {
      dataInicio?: string;
      dataFim?: string;
      agenteId?: string;
      faixasMensalidade?: string[];
    },
    formato: "csv" | "pdf" | "xlsx",
  ) => void;
}) {
  const [open, setOpen] = React.useState(false);
  const [dataInicio, setDataInicio] = React.useState<Date>();
  const [dataFim, setDataFim] = React.useState<Date>();
  const [agenteId, setAgenteId] = React.useState("");
  const [faixasMensalidade, setFaixasMensalidade] = React.useState<string[]>([]);
  const [faixasOpen, setFaixasOpen] = React.useState(false);

  const handleExport = (formato: ReportFormat) => {
    onExport(
      {
        dataInicio: formatIsoDate(dataInicio) || undefined,
        dataFim: formatIsoDate(dataFim) || undefined,
        agenteId: agenteId || undefined,
        faixasMensalidade,
      },
      formato,
    );
    setOpen(false);
  };

  const selectedFaixaLabels = MENSALIDADE_FAIXAS.filter((option) =>
    faixasMensalidade.includes(option.value),
  );

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" className="rounded-2xl" disabled={disabled}>
          <DownloadIcon className="size-4" />
          Exportar CSV / PDF / XLS
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-2 md:grid-cols-2">
          <div className="space-y-2">
            <Label>Data inicial</Label>
            <DatePicker value={dataInicio} onChange={setDataInicio} />
          </div>
          <div className="space-y-2">
            <Label>Data final</Label>
            <DatePicker value={dataFim} onChange={setDataFim} />
          </div>
          <div className="space-y-2">
            <Label htmlFor={`${title}-agente`}>Agente</Label>
            <SearchableSelect
              options={agentOptions}
              value={agenteId}
              onChange={setAgenteId}
              placeholder="Todos os agentes"
              clearValue=""
              clearLabel="Todos os agentes"
              searchPlaceholder="Buscar agente..."
              className="h-11 rounded-xl border-border/60 bg-background/60"
            />
          </div>
          <div className="space-y-2">
            <Label>Faixas de mensalidade</Label>
            <Popover open={faixasOpen} onOpenChange={setFaixasOpen}>
              <PopoverTrigger asChild>
                <Button
                  variant="outline"
                  className="h-11 w-full justify-between rounded-xl border-border/60 bg-card/60"
                >
                  <span className="truncate text-left">
                    {selectedFaixaLabels.length
                      ? selectedFaixaLabels.map((option) => option.label).join(", ")
                      : "Todas as faixas"}
                  </span>
                  <ChevronDownIcon className="size-4 shrink-0 text-muted-foreground" />
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-[var(--radix-popover-trigger-width)] rounded-2xl border-border/60 p-3">
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium">Selecione uma ou mais faixas</p>
                    {faixasMensalidade.length ? (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => setFaixasMensalidade([])}
                      >
                        Limpar
                      </Button>
                    ) : null}
                  </div>
                  <div className="space-y-2">
                    {MENSALIDADE_FAIXAS.map((option) => {
                      const checked = faixasMensalidade.includes(option.value);
                      return (
                        <label
                          key={option.value}
                          className="flex cursor-pointer items-center gap-3 rounded-xl border border-border/40 px-3 py-2 hover:bg-accent/40"
                        >
                          <Checkbox
                            checked={checked}
                            onCheckedChange={(nextChecked) => {
                              setFaixasMensalidade((current) =>
                                nextChecked
                                  ? [...current, option.value]
                                  : current.filter((item) => item !== option.value),
                              );
                            }}
                          />
                          <span className="text-sm">{option.label}</span>
                        </label>
                      );
                    })}
                  </div>
                </div>
              </PopoverContent>
            </Popover>
            {selectedFaixaLabels.length ? (
              <div className="flex flex-wrap gap-2">
                {selectedFaixaLabels.map((option) => (
                  <Badge
                    key={option.value}
                    className="rounded-full bg-primary/15 px-3 py-1 text-primary"
                  >
                    {option.label}
                  </Badge>
                ))}
              </div>
            ) : null}
          </div>
        </div>
        <DialogFooter className="gap-2 sm:justify-end">
          <Button variant="outline" onClick={() => handleExport("csv")} disabled={disabled}>
            CSV
          </Button>
          <Button variant="outline" onClick={() => handleExport("pdf")} disabled={disabled}>
            PDF
          </Button>
          <Button onClick={() => handleExport("xlsx")} disabled={disabled}>
            XLS
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
