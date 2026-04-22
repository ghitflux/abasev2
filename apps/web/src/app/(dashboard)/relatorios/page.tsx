"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ChevronDownIcon,
  DownloadIcon,
  LoaderCircleIcon,
} from "lucide-react";
import { endOfMonth, format, startOfMonth, subMonths } from "date-fns";
import { toast } from "sonner";

import type { RelatorioGeradoItem, SimpleUser } from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import { MENSALIDADE_FAIXAS } from "@/lib/associado-filter-presets";
import { formatDateTime } from "@/lib/formatters";
import { usePermissions } from "@/hooks/use-permissions";
import SearchableSelect from "@/components/custom/searchable-select";
import DataTable, { type DataTableColumn } from "@/components/shared/data-table";
import EmptyState from "@/components/shared/empty-state";
import { ListRouteSkeleton } from "@/components/shared/page-skeletons";
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
  | "associados_ativos_com_3_parcelas_pagas"
  | "associados_inativos_com_1_parcela_paga"
  | "associados_inativos_com_3_parcelas_pagas";

const ASSOCIADO_PAGAMENTO_EXPORT_OPTIONS = [
  {
    tipo: "associados_ativos_com_1_parcela_paga" as const,
    title: "Ativos com 1 parcela paga",
    description:
      "Associados que não estejam inativos e sem contrato cancelado, com pelo menos uma parcela paga no período filtrado.",
  },
  {
    tipo: "associados_ativos_com_3_parcelas_pagas" as const,
    title: "Ativos com 3 parcelas pagas",
    description:
      "Associados que não estejam inativos e sem contrato cancelado, com no mínimo três parcelas pagas no período filtrado.",
  },
  {
    tipo: "associados_inativos_com_1_parcela_paga" as const,
    title: "Inativos com 1 parcela paga",
    description:
      "Associados com status inativo ou com contrato cancelado, com pelo menos uma parcela paga no período filtrado.",
  },
  {
    tipo: "associados_inativos_com_3_parcelas_pagas" as const,
    title: "Inativos com 3 parcelas pagas",
    description:
      "Associados com status inativo ou com contrato cancelado, com no mínimo três parcelas pagas no período filtrado.",
  },
] as const;

function inferReportTypeLabel(name: string) {
  const normalized = name.toLowerCase();
  return (
    ASSOCIADO_PAGAMENTO_EXPORT_OPTIONS.find((option) =>
      normalized.startsWith(`${option.tipo}_`),
    )?.title ?? "Exportacao"
  );
}

function resolveRelatorioDownloadUrl(item: RelatorioGeradoItem) {
  const downloadUrl = String(item.download_url || "").trim();
  if (downloadUrl) {
    return downloadUrl.replace(/^\/api\/v1\//, "/api/backend/");
  }
  return `/api/backend/relatorios/${item.id}/download/`;
}

function downloadRelatorio(item: RelatorioGeradoItem) {
  const link = document.createElement("a");
  link.href = resolveRelatorioDownloadUrl(item);
  link.download = item.nome;
  link.style.display = "none";
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
  const [activeExport, setActiveExport] = React.useState<{
    title: string;
    formato: ReportFormat;
  } | null>(null);

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
    onMutate: (variables) => {
      const reportTitle =
        ASSOCIADO_PAGAMENTO_EXPORT_OPTIONS.find((option) => option.tipo === variables.tipo)?.title ??
        "Relatorio";
      setActiveExport({
        title: reportTitle,
        formato: variables.formato,
      });
    },
    onSuccess: (item) => {
      toast.success("Relatório gerado. Download iniciado.");
      void queryClient.invalidateQueries({ queryKey: ["relatorios-historico"] });
      downloadRelatorio(item);
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Falha ao gerar relatorio.");
    },
    onSettled: () => {
      setActiveExport(null);
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
            Exportacoes administrativas com criterios fixos de contagem, filtros por agente e
            faixa de mensalidade e presets de periodo.
          </p>
        </div>
      </section>

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

      <Dialog open={Boolean(activeExport) && exportMutation.isPending}>
        <DialogContent
          showCloseButton={false}
          className="sm:max-w-md"
          onEscapeKeyDown={(event) => event.preventDefault()}
          onInteractOutside={(event) => event.preventDefault()}
          onPointerDownOutside={(event) => event.preventDefault()}
        >
          <DialogHeader>
            <DialogTitle>Gerando relatório</DialogTitle>
            <DialogDescription>
              {activeExport
                ? `${activeExport.title} em ${activeExport.formato.toUpperCase()}. O download será iniciado automaticamente ao concluir.`
                : "O arquivo está sendo preparado no servidor."}
            </DialogDescription>
          </DialogHeader>
          <div className="rounded-2xl border border-border/60 bg-card/60 p-5">
            <div className="flex items-start gap-4">
              <LoaderCircleIcon className="mt-0.5 size-8 animate-spin text-primary" />
              <div className="space-y-2">
                <p className="font-medium text-foreground">Processando exportação</p>
                <p className="text-sm text-muted-foreground">
                  Esse relatório pode levar alguns segundos para ser gerado. Assim que terminar, o
                  arquivo começa a baixar sem precisar recarregar a página.
                </p>
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function formatIsoDate(value?: Date) {
  if (!value) return "";
  return format(value, "yyyy-MM-dd");
}

type PeriodPreset = "customizado" | "mes_atual" | "mes_anterior" | "periodo_maximo";

const PERIOD_PRESET_OPTIONS: Array<{
  value: PeriodPreset;
  label: string;
  description: string;
}> = [
  {
    value: "mes_atual",
    label: "Mês atual",
    description: "Do primeiro ao último dia do mês atual.",
  },
  {
    value: "mes_anterior",
    label: "Mês anterior",
    description: "Do primeiro ao último dia do mês anterior.",
  },
  {
    value: "customizado",
    label: "Faixa de período",
    description: "Permite definir data inicial e final manualmente.",
  },
  {
    value: "periodo_maximo",
    label: "Período máximo",
    description: "Sem recorte de datas; considera todo o histórico pagável.",
  },
];

function resolvePeriodRange(preset: PeriodPreset, customStart?: Date, customEnd?: Date) {
  const today = new Date();
  if (preset === "mes_atual") {
    return { dataInicio: startOfMonth(today), dataFim: endOfMonth(today) };
  }
  if (preset === "mes_anterior") {
    const previousMonth = subMonths(today, 1);
    return {
      dataInicio: startOfMonth(previousMonth),
      dataFim: endOfMonth(previousMonth),
    };
  }
  if (preset === "periodo_maximo") {
    return { dataInicio: undefined, dataFim: undefined };
  }
  return { dataInicio: customStart, dataFim: customEnd };
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
  const [periodPreset, setPeriodPreset] = React.useState<PeriodPreset>("mes_atual");
  const [dataInicio, setDataInicio] = React.useState<Date>();
  const [dataFim, setDataFim] = React.useState<Date>();
  const [agenteId, setAgenteId] = React.useState("");
  const [faixasMensalidade, setFaixasMensalidade] = React.useState<string[]>([]);
  const [faixasOpen, setFaixasOpen] = React.useState(false);

  React.useEffect(() => {
    if (!open) {
      return;
    }
    setPeriodPreset("mes_atual");
    setDataInicio(undefined);
    setDataFim(undefined);
    setAgenteId("");
    setFaixasMensalidade([]);
  }, [open]);

  const handleExport = (formato: ReportFormat) => {
    const range = resolvePeriodRange(periodPreset, dataInicio, dataFim);
    onExport(
      {
        dataInicio: formatIsoDate(range.dataInicio) || undefined,
        dataFim: formatIsoDate(range.dataFim) || undefined,
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
  const customPeriodSelected = periodPreset === "customizado";

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
          <div className="space-y-2 md:col-span-2">
            <Label>Período</Label>
            <div className="grid gap-2 md:grid-cols-2">
              {PERIOD_PRESET_OPTIONS.map((option) => {
                const checked = periodPreset === option.value;
                return (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => setPeriodPreset(option.value)}
                    className={[
                      "rounded-2xl border px-4 py-3 text-left transition-colors",
                      checked
                        ? "border-primary/60 bg-primary/10"
                        : "border-border/60 bg-card/50 hover:border-primary/30",
                    ].join(" ")}
                  >
                    <div className="text-sm font-medium text-foreground">{option.label}</div>
                    <div className="text-xs text-muted-foreground">{option.description}</div>
                  </button>
                );
              })}
            </div>
          </div>
          <div className="space-y-2">
            <Label>Data inicial</Label>
            <DatePicker value={dataInicio} onChange={setDataInicio} disabled={!customPeriodSelected} />
          </div>
          <div className="space-y-2">
            <Label>Data final</Label>
            <DatePicker value={dataFim} onChange={setDataFim} disabled={!customPeriodSelected} />
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
          <div className="rounded-2xl border border-border/60 bg-muted/30 px-4 py-3 text-sm text-muted-foreground md:col-span-2">
            Criterios: ativo = associado sem status `inativo` e sem contrato `cancelado`;
            inativo = associado com status `inativo` ou contrato `cancelado`; parcelas com status
            `descontado` ou `liquidada`; período aplicado sobre `data_pagamento` com fallback para
            `referencia_mes`; agente do contrato com fallback para o agente do associado; faixa pela
            `valor_mensalidade` do contrato.
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
