"use client";

import * as React from "react";
import { format } from "date-fns";
import { ptBR } from "date-fns/locale";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircleIcon,
  CheckCircleIcon,
  ChevronRightIcon,
  ClipboardListIcon,
  ExternalLinkIcon,
  HandCoinsIcon,
  TrendingDownIcon,
  UploadIcon,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { apiFetch } from "@/lib/api/client";
import { formatCurrency, formatDate } from "@/lib/formatters";
import CalendarCompetencia from "@/components/custom/calendar-competencia";
import FileUploadDropzone from "@/components/custom/file-upload-dropzone";
import StatusBadge from "@/components/custom/status-badge";
import CopySnippet from "@/components/shared/copy-snippet";
import DataTable, { type DataTableColumn } from "@/components/shared/data-table";
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
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";

type BaixaManualItem = {
  id: number;
  associado_id: number;
  nome: string;
  cpf_cnpj: string;
  matricula: string;
  agente_nome: string;
  contrato_id: number;
  contrato_codigo: string;
  referencia_mes: string;
  valor: string;
  status: string;
  data_vencimento: string;
  observacao: string;
};

type BaixaManualKpis = {
  total_pendentes: number;
  em_aberto: number;
  nao_descontado: number;
  valor_total_pendente: string;
  baixas_realizadas_mes: number;
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
};

type DarBaixaState = {
  item: BaixaManualItem;
  comprovante: File | null;
  valorPago: string;
  observacao: string;
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

function groupByAssociado(items: BaixaManualItem[]): AssociadoGroup[] {
  const map = new Map<number, AssociadoGroup>();
  for (const item of items) {
    const existing = map.get(item.associado_id);
    if (existing) {
      existing.parcelas.push(item);
      existing.total_parcelas += 1;
      existing.valor_total += parseFloat(item.valor) || 0;
    } else {
      map.set(item.associado_id, {
        id: item.associado_id,
        associado_id: item.associado_id,
        nome: item.nome,
        cpf_cnpj: item.cpf_cnpj,
        matricula: item.matricula,
        agente_nome: item.agente_nome,
        parcelas: [item],
        total_parcelas: 1,
        valor_total: parseFloat(item.valor) || 0,
      });
    }
  }
  return Array.from(map.values());
}

export default function BaixaManualPage() {
  const queryClient = useQueryClient();
  const router = useRouter();
  const [page, setPage] = React.useState(1);
  const [search, setSearch] = React.useState("");
  const [statusFilter, setStatusFilter] = React.useState("todos");
  const [competencia, setCompetencia] = React.useState<Date | undefined>();
  const [darBaixaState, setDarBaixaState] = React.useState<DarBaixaState | null>(null);
  const [navigatingId, setNavigatingId] = React.useState<number | null>(null);

  const competenciaParam = competencia ? format(competencia, "yyyy-MM") : undefined;

  const query = useQuery({
    queryKey: ["tesouraria-baixa-manual", page, search, statusFilter, competenciaParam],
    queryFn: () =>
      apiFetch<BaixaManualResponse>("tesouraria/baixa-manual", {
        query: {
          page,
          page_size: 50,
          search: search || undefined,
          status: statusFilter !== "todos" ? statusFilter : undefined,
          competencia: competenciaParam,
        },
      }),
  });

  const darBaixaMutation = useMutation({
    mutationFn: async ({
      id,
      comprovante,
      valorPago,
      observacao,
    }: {
      id: number;
      comprovante: File;
      valorPago: string;
      observacao: string;
    }) => {
      const fd = new FormData();
      fd.append("comprovante", comprovante);
      fd.append("valor_pago", valorPago);
      if (observacao) fd.append("observacao", observacao);
      return apiFetch(`tesouraria/baixa-manual/${id}/dar-baixa`, {
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

  function handleVerDetalhes(associadoId: number) {
    setNavigatingId(associadoId);
    router.push(`/associados/${associadoId}`);
  }

  const kpis = query.data?.kpis;
  const rows = query.data?.results ?? [];
  const totalCount = query.data?.count ?? 0;
  const groups = React.useMemo(() => groupByAssociado(rows), [rows]);

  const columns = React.useMemo<DataTableColumn<AssociadoGroup>[]>(
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
          <span className="text-sm text-muted-foreground">{row.agente_nome || "—"}</span>
        ),
      },
      {
        id: "parcelas",
        header: "Parcelas",
        cell: (row) => (
          <Badge variant="secondary" className="font-mono text-xs">
            {row.total_parcelas} parcela{row.total_parcelas !== 1 ? "s" : ""}
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
          <Button
            size="sm"
            variant="outline"
            className="shrink-0"
            disabled={navigatingId === row.associado_id}
            onClick={(e) => {
              e.stopPropagation();
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
        ),
      },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [navigatingId],
  );

  const renderExpanded = React.useCallback(
    (group: AssociadoGroup) => (
      <div className="space-y-3">
        <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
          Parcelas Pendentes — {group.nome}
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
                  Vencimento
                </th>
                <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Valor
                </th>
                <th className="px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                  Status
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
                    <CopySnippet label="Contrato" value={parcela.contrato_codigo} mono inline />
                  </td>
                  <td className="px-4 py-3 font-medium">
                    {formatMonthYear(parcela.referencia_mes)}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {formatDate(parcela.data_vencimento)}
                  </td>
                  <td className="px-4 py-3 font-semibold tabular-nums">
                    {formatCurrency(parcela.valor)}
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={parcela.status} />
                  </td>
                  <td className="px-4 py-3">
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
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    ),
    [],
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <section className="rounded-[1.75rem] border border-border/60 bg-card/70 p-6">
        <div className="space-y-1">
          <h1 className="text-3xl font-semibold">Inadimplentes</h1>
          <p className="text-sm text-muted-foreground">
            Parcelas de meses anteriores pendentes ou não descontadas — registre a baixa com comprovante.
          </p>
        </div>
      </section>

      {/* KPI cards */}
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatsCard
          title="Total Pendentes"
          value={String(kpis?.total_pendentes ?? "—")}
          delta="em aberto + não descontadas"
          icon={ClipboardListIcon}
          tone="warning"
        />
        <StatsCard
          title="Em Aberto"
          value={String(kpis?.em_aberto ?? "—")}
          delta="parcelas em aberto"
          icon={AlertCircleIcon}
          tone="warning"
        />
        <StatsCard
          title="Não Descontadas"
          value={String(kpis?.nao_descontado ?? "—")}
          delta="retornaram rejeitadas"
          icon={TrendingDownIcon}
          tone="warning"
        />
        <StatsCard
          title="Valor Total Pendente"
          value={kpis ? formatCurrency(kpis.valor_total_pendente) : "—"}
          delta={`Baixas este mês: ${kpis?.baixas_realizadas_mes ?? 0}`}
          icon={HandCoinsIcon}
          tone="neutral"
        />
      </section>

      {/* Filters */}
      <section className="grid gap-3 rounded-[1.75rem] border border-border/60 bg-card/50 p-4 sm:grid-cols-2 lg:grid-cols-[1fr_180px_180px_auto]">
        <Input
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(1);
          }}
          placeholder="Buscar por associado, CPF, matrícula ou contrato"
          className="rounded-2xl border-border/60 bg-card/60"
        />
        <Select
          value={statusFilter}
          onValueChange={(v) => {
            setStatusFilter(v);
            setPage(1);
          }}
        >
          <SelectTrigger className="rounded-2xl border-border/60 bg-card/60">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="todos">Todos</SelectItem>
            <SelectItem value="em_aberto">Em aberto</SelectItem>
            <SelectItem value="nao_descontado">Não descontado</SelectItem>
          </SelectContent>
        </Select>
        <CalendarCompetencia
          value={competencia}
          onChange={(d) => {
            setCompetencia(d);
            setPage(1);
          }}
        />
        <Button
          variant="outline"
          onClick={() => {
            setCompetencia(undefined);
            setStatusFilter("todos");
            setSearch("");
            setPage(1);
          }}
        >
          Limpar
        </Button>
      </section>

      {/* Table */}
      {query.isLoading ? (
        <div className="overflow-hidden rounded-[1.75rem] border border-border/60 bg-card/70">
          <div className="space-y-0 divide-y divide-border/40">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="flex items-center gap-4 px-5 py-4">
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
          emptyMessage="Nenhuma parcela pendente de meses anteriores."
        />
      )}

      {/* Dar Baixa Dialog */}
      <Dialog
        open={!!darBaixaState}
        onOpenChange={(open) => {
          if (!open) setDarBaixaState(null);
        }}
      >
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Registrar inadimplência</DialogTitle>
            <DialogDescription>
              {darBaixaState ? (
                <>
                  <strong>{darBaixaState.item.nome}</strong> —{" "}
                  {formatMonthYear(darBaixaState.item.referencia_mes)} —{" "}
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
                    setDarBaixaState((prev) =>
                      prev ? { ...prev, comprovante: file ?? null } : prev,
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
                  onChange={(e) =>
                    setDarBaixaState((prev) =>
                      prev ? { ...prev, valorPago: e.target.value } : prev,
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
                  onChange={(e) =>
                    setDarBaixaState((prev) =>
                      prev ? { ...prev, observacao: e.target.value } : prev,
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
                !darBaixaState?.valorPago
              }
              onClick={() => {
                if (!darBaixaState?.comprovante || !darBaixaState.valorPago) return;
                darBaixaMutation.mutate({
                  id: darBaixaState.item.id,
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
    </div>
  );
}
