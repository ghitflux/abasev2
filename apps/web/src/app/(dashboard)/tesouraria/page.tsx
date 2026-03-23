"use client";

import * as React from "react";
import { format } from "date-fns";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CalendarDaysIcon,
  EyeIcon,
  FileDownIcon,
  SlidersHorizontalIcon,
  PaperclipIcon,
  LockIcon,
  Trash2Icon,
  UploadIcon,
} from "lucide-react";
import { toast } from "sonner";

import type { PaginatedResponse, TesourariaContratoItem } from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import { buildBackendFileUrl } from "@/lib/backend-files";
import { formatCurrency, formatDateTime, formatLongMonthYear } from "@/lib/formatters";
import { maskCPFCNPJ } from "@/lib/masks";
import CalendarCompetencia from "@/components/custom/calendar-competencia";
import StatusBadge from "@/components/custom/status-badge";
import AssociadoDetailsDialog from "@/components/associados/associado-details-dialog";
import CopySnippet from "@/components/shared/copy-snippet";
import DataTable, { type DataTableColumn } from "@/components/shared/data-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";

const comprovanteAccept = {
  "application/pdf": [".pdf"],
  "image/png": [".png"],
  "image/jpeg": [".jpg", ".jpeg"],
};

const PAGE_SIZE = 5;

type DraftMap = Record<number, { associado?: File; agente?: File }>;
type TesourariaPagamentoFilter = "pendente" | "concluido" | "cancelado" | "processado";
type AdvancedFiltersDraft = {
  dataInicio: string;
  dataFim: string;
  agente: string;
  statusContrato: string;
  situacaoEsteira: string;
};

function countAdvancedFilters(filters: AdvancedFiltersDraft) {
  return [
    Boolean(filters.dataInicio),
    Boolean(filters.dataFim),
    Boolean(filters.agente),
    filters.statusContrato !== "todos",
    filters.situacaoEsteira !== "todos",
  ].filter(Boolean).length;
}

function useTesourariaQuery({
  page,
  competencia,
  search,
  pagamento,
  dataInicio,
  dataFim,
  agente,
  statusContrato,
  situacaoEsteira,
}: {
  page: number;
  competencia: Date;
  search: string;
  pagamento: TesourariaPagamentoFilter;
  dataInicio: string;
  dataFim: string;
  agente: string;
  statusContrato: string;
  situacaoEsteira: string;
}) {
  return useQuery({
    queryKey: [
      "tesouraria-contratos",
      pagamento,
      page,
      competencia.toISOString(),
      search,
      dataInicio,
      dataFim,
      agente,
      statusContrato,
      situacaoEsteira,
    ],
    queryFn: () =>
      apiFetch<PaginatedResponse<TesourariaContratoItem>>("tesouraria/contratos", {
        query: {
          page,
          page_size: PAGE_SIZE,
          competencia: format(competencia, "yyyy-MM"),
          pagamento,
          search: search || undefined,
          data_inicio: dataInicio || undefined,
          data_fim: dataFim || undefined,
          agente: agente || undefined,
          status_contrato: statusContrato === "todos" ? undefined : statusContrato,
          situacao_esteira: situacaoEsteira === "todos" ? undefined : situacaoEsteira,
        },
      }),
  });
}

export default function TesourariaPage() {
  const queryClient = useQueryClient();
  const [competencia, setCompetencia] = React.useState(() => new Date());
  const [search, setSearch] = React.useState("");
  const [pagePending, setPagePending] = React.useState(1);
  const [pagePaid, setPagePaid] = React.useState(1);
  const [pageCanceled, setPageCanceled] = React.useState(1);
  const [showOnlyPending, setShowOnlyPending] = React.useState(false);
  const [dataInicio, setDataInicio] = React.useState("");
  const [dataFim, setDataFim] = React.useState("");
  const [agenteFiltro, setAgenteFiltro] = React.useState("");
  const [statusContrato, setStatusContrato] = React.useState("todos");
  const [situacaoEsteira, setSituacaoEsteira] = React.useState("todos");
  const [draftAdvancedFilters, setDraftAdvancedFilters] = React.useState<AdvancedFiltersDraft>({
    dataInicio: "",
    dataFim: "",
    agente: "",
    statusContrato: "todos",
    situacaoEsteira: "todos",
  });
  const [drafts, setDrafts] = React.useState<DraftMap>({});
  const [freezeTarget, setFreezeTarget] = React.useState<TesourariaContratoItem | null>(null);
  const [freezeReason, setFreezeReason] = React.useState("");
  const [bankTarget, setBankTarget] = React.useState<TesourariaContratoItem | null>(null);
  const [detailTarget, setDetailTarget] = React.useState<TesourariaContratoItem | null>(null);

  const pendingQuery = useTesourariaQuery({
    page: pagePending,
    competencia,
    search,
    pagamento: "pendente",
    dataInicio,
    dataFim,
    agente: agenteFiltro,
    statusContrato,
    situacaoEsteira,
  });
  const paidQuery = useTesourariaQuery({
    page: pagePaid,
    competencia,
    search,
    pagamento: "concluido",
    dataInicio,
    dataFim,
    agente: agenteFiltro,
    statusContrato,
    situacaoEsteira,
  });
  const canceledQuery = useTesourariaQuery({
    page: pageCanceled,
    competencia,
    search,
    pagamento: "cancelado",
    dataInicio,
    dataFim,
    agente: agenteFiltro,
    statusContrato,
    situacaoEsteira,
  });

  const efetivarMutation = useMutation({
    mutationFn: async ({
      contratoId,
      associado,
      agente,
    }: {
      contratoId: number;
      associado: File;
      agente: File;
    }) => {
      const formData = new FormData();
      formData.set("comprovante_associado", associado);
      formData.set("comprovante_agente", agente);
      return apiFetch<TesourariaContratoItem>(`tesouraria/contratos/${contratoId}/efetivar`, {
        method: "POST",
        formData,
      });
    },
    onSuccess: (_, variables) => {
      setDrafts((current) => {
        const next = { ...current };
        delete next[variables.contratoId];
        return next;
      });
      toast.success("Contrato efetivado com sucesso.");
      void queryClient.invalidateQueries({ queryKey: ["tesouraria-contratos"] });
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Não foi possível efetivar o contrato.");
    },
  });

  const congelarMutation = useMutation({
    mutationFn: async ({ contratoId, motivo }: { contratoId: number; motivo: string }) =>
      apiFetch<TesourariaContratoItem>(`tesouraria/contratos/${contratoId}/congelar`, {
        method: "POST",
        body: { motivo },
      }),
    onSuccess: () => {
      toast.success("Contrato congelado.");
      setFreezeTarget(null);
      setFreezeReason("");
      void queryClient.invalidateQueries({ queryKey: ["tesouraria-contratos"] });
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Falha ao congelar contrato.");
    },
  });

  const substituirComprovanteMutation = useMutation({
    mutationFn: async ({
      contratoId,
      papel,
      arquivo,
    }: {
      contratoId: number;
      papel: "associado" | "agente";
      arquivo: File;
    }) => {
      const formData = new FormData();
      formData.set("papel", papel);
      formData.set("arquivo", arquivo);
      return apiFetch<TesourariaContratoItem>(
        `tesouraria/contratos/${contratoId}/substituir-comprovante`,
        {
          method: "POST",
          formData,
        },
      );
    },
    onSuccess: () => {
      toast.success("Comprovante substituído.");
      void queryClient.invalidateQueries({ queryKey: ["tesouraria-contratos"] });
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : "Falha ao substituir o comprovante.",
      );
    },
  });

  const columns = React.useMemo<DataTableColumn<TesourariaContratoItem>[]>(
    () => [
      {
        id: "anexos",
        header: "Anexos",
        cell: (row) => {
          const associadoComprovante = row.comprovantes.find(
            (item) => item.papel === "associado",
          );
          const agenteComprovante = row.comprovantes.find((item) => item.papel === "agente");
          const draft = drafts[row.id] ?? {};
          const canEfetivar = row.status === "pendente" || row.status === "congelado";
          const isEfetivando =
            efetivarMutation.isPending && efetivarMutation.variables?.contratoId === row.id;
          const isSubstituindo =
            substituirComprovanteMutation.isPending &&
            substituirComprovanteMutation.variables?.contratoId === row.id;

          return (
            <div className="flex min-w-[13rem] flex-col gap-2">
              <div className="grid gap-2">
                <ComprovanteSlot
                  compact
                  label="Associado"
                  existingUrl={
                    associadoComprovante?.arquivo_disponivel_localmente
                      ? associadoComprovante.arquivo
                      : undefined
                  }
                  existingName={associadoComprovante?.nome_original}
                  draftFile={draft.associado}
                  disabled={isEfetivando || isSubstituindo}
                  isProcessing={isEfetivando || isSubstituindo}
                  onSelect={(file) => {
                    if (canEfetivar) {
                      setDrafts((current) => ({
                        ...current,
                        [row.id]: { ...current[row.id], associado: file },
                      }));
                      return;
                    }
                    substituirComprovanteMutation.mutate({
                      contratoId: row.id,
                      papel: "associado",
                      arquivo: file,
                    });
                  }}
                  onClear={() =>
                    setDrafts((current) => ({
                      ...current,
                      [row.id]: { ...current[row.id], associado: undefined },
                    }))
                  }
                />
                <ComprovanteSlot
                  compact
                  label="Agente"
                  existingUrl={
                    agenteComprovante?.arquivo_disponivel_localmente
                      ? agenteComprovante.arquivo
                      : undefined
                  }
                  existingName={agenteComprovante?.nome_original}
                  draftFile={draft.agente}
                  disabled={isEfetivando || isSubstituindo}
                  isProcessing={isEfetivando || isSubstituindo}
                  onSelect={(file) => {
                    if (canEfetivar) {
                      setDrafts((current) => ({
                        ...current,
                        [row.id]: { ...current[row.id], agente: file },
                      }));
                      return;
                    }
                    substituirComprovanteMutation.mutate({
                      contratoId: row.id,
                      papel: "agente",
                      arquivo: file,
                    });
                  }}
                  onClear={() =>
                    setDrafts((current) => ({
                      ...current,
                      [row.id]: { ...current[row.id], agente: undefined },
                    }))
                  }
                />
              </div>
              {canEfetivar && draft.associado && draft.agente ? (
                <Button
                  size="sm"
                  className="self-start"
                  onClick={() =>
                    efetivarMutation.mutate({
                      contratoId: row.id,
                      associado: draft.associado!,
                      agente: draft.agente!,
                    })
                  }
                  disabled={efetivarMutation.isPending}
                >
                  Efetivar agora
                </Button>
              ) : null}
            </div>
          );
        },
      },
      {
        id: "dados_bancarios",
        header: "Dados bancários",
        cell: (row) => (
          <Button size="sm" onClick={() => setBankTarget(row)}>
            <CalendarDaysIcon className="size-4" />
            Ver dados
          </Button>
        ),
      },
      {
        id: "pix",
        header: "Chave PIX",
        cell: (row) => row.chave_pix || "—",
      },
      {
        id: "acao",
        header: "Ação",
        cell: (row) => {
          const canFreeze = row.status === "pendente" || row.status === "congelado";

          return (
            <div className="flex min-w-52 flex-wrap gap-2">
              <Button size="sm" variant="outline" onClick={() => setDetailTarget(row)}>
                <EyeIcon className="size-4" />
                Ver detalhes
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="border-amber-500/40 text-amber-200"
                onClick={() => setFreezeTarget(row)}
                disabled={!canFreeze}
              >
                <LockIcon className="size-4" />
                Congelar
              </Button>
            </div>
          );
        },
      },
      {
        id: "nome",
        header: "Nome",
        cell: (row) => <p className="font-medium">{row.nome}</p>,
      },
      {
        id: "matricula_cpf",
        header: "Matrícula / CPF",
        cell: (row) => (
          <div className="space-y-1">
            <div>
              {row.matricula ? (
                <CopySnippet label="Matrícula" value={row.matricula} mono inline />
              ) : (
                <span className="text-muted-foreground">—</span>
              )}
            </div>
            <CopySnippet
              label="CPF"
              value={maskCPFCNPJ(row.cpf_cnpj)}
              mono
              inline
            />
          </div>
        ),
      },
      {
        id: "agente",
        header: "Agente",
        cell: (row) => (
          <div>
            <p className="font-medium">{row.agente_nome || "Sem agente"}</p>
            <p className="text-xs text-muted-foreground">
              Repasse: {row.percentual_repasse}%
            </p>
          </div>
        ),
      },
      {
        id: "valores",
        header: "Aux. / Comissão",
        cell: (row) => (
          <div className="space-y-1">
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="text-muted-foreground">Aux. liberado</span>
              <span className="font-medium">{formatCurrency(row.margem_disponivel)}</span>
            </div>
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="text-muted-foreground">Comissão</span>
              <span className="font-medium">{formatCurrency(row.comissao_agente)}</span>
            </div>
          </div>
        ),
      },
      {
        id: "data",
        header: "Data/Hora",
        cell: (row) => formatDateTime(row.data_assinatura),
      },
      {
        id: "status",
        header: "Status",
        cell: (row) => <StatusBadge status={row.status} />,
      },
    ],
    [drafts, efetivarMutation, substituirComprovanteMutation],
  );

  const handleRefresh = () => {
    setPagePending(1);
    setPagePaid(1);
    setPageCanceled(1);
    void queryClient.invalidateQueries({ queryKey: ["tesouraria-contratos"] });
  };

  const buildRangeLabel = (page: number, rowCount: number, total: number) => {
    if (!rowCount) return "0";
    const start = (page - 1) * PAGE_SIZE + 1;
    return `${start}-${start + rowCount - 1} de ${total}`;
  };

  const pendingRows = pendingQuery.data?.results ?? [];
  const paidRows = paidQuery.data?.results ?? [];
  const canceledRows = canceledQuery.data?.results ?? [];
  const activeAdvancedFiltersCount = countAdvancedFilters({
    dataInicio,
    dataFim,
    agente: agenteFiltro,
    statusContrato,
    situacaoEsteira,
  });

  return (
    <div className="space-y-6">
      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_auto]">
        <Card className="rounded-[1.75rem] border-border/60 bg-card/70">
          <CardContent className="flex flex-col gap-4 p-6 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="text-sm uppercase tracking-[0.28em] text-muted-foreground">
                Tesouraria
              </p>
              <h1 className="text-3xl font-semibold">Novos Contratos</h1>
              <p className="text-sm text-muted-foreground">
                Fluxo padrão de novos contratos na competência ativa: {formatLongMonthYear(competencia)}
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <CalendarCompetencia
                value={competencia}
                onChange={(value) => {
                  setCompetencia(value);
                  setPagePending(1);
                  setPagePaid(1);
                  setPageCanceled(1);
                }}
                className="w-full rounded-2xl bg-card/60 sm:w-56"
              />
              <Button variant="outline" onClick={() => window.print()}>
                <FileDownIcon className="size-4" />
                Baixar PDF
              </Button>
            </div>
          </CardContent>
        </Card>
        <Card className="rounded-[1.75rem] border-border/60 bg-card/70">
          <CardContent className="space-y-2 p-6">
            <p className="text-sm text-muted-foreground">Pendentes na competência</p>
            <button
              type="button"
              onClick={() => setShowOnlyPending((current) => !current)}
              className="text-left"
            >
              <Badge className="rounded-full bg-rose-500/15 px-3 py-1 text-rose-200">
                Pendentes: {pendingQuery.data?.count ?? 0}
              </Badge>
            </button>
            <p className="text-xs text-muted-foreground">
              Clique para {showOnlyPending ? "mostrar pagos/cancelados" : "filtrar apenas pendentes"}.
            </p>
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-3 rounded-[1.75rem] border border-border/60 bg-card/50 p-4 lg:grid-cols-[minmax(0,1fr)_auto_auto]">
        <Input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="Buscar por nome, CPF/CNPJ, matrícula ou código do contrato"
          className="rounded-2xl border-border/60 bg-card/60"
        />
        <Sheet
          onOpenChange={(open) => {
            if (open) {
              setDraftAdvancedFilters({
                dataInicio,
                dataFim,
                agente: agenteFiltro,
                statusContrato,
                situacaoEsteira,
              });
            }
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
                Filtre por período, agente, status do contrato e situação operacional.
              </SheetDescription>
            </SheetHeader>

            <div className="space-y-5 overflow-y-auto px-4 pb-4">
              <FilterField label="Agente">
                <Input
                  value={draftAdvancedFilters.agente}
                  onChange={(event) =>
                    setDraftAdvancedFilters((current) => ({
                      ...current,
                      agente: event.target.value,
                    }))
                  }
                  placeholder="Nome ou e-mail do agente"
                  className="rounded-2xl border-border/60 bg-card/60"
                />
              </FilterField>

              <div className="grid gap-4 md:grid-cols-2">
                <FilterField label="Data inicial">
                  <Input
                    type="date"
                    value={draftAdvancedFilters.dataInicio}
                    onChange={(event) =>
                      setDraftAdvancedFilters((current) => ({
                        ...current,
                        dataInicio: event.target.value,
                      }))
                    }
                    className="rounded-2xl border-border/60 bg-card/60"
                  />
                </FilterField>

                <FilterField label="Data final">
                  <Input
                    type="date"
                    value={draftAdvancedFilters.dataFim}
                    onChange={(event) =>
                      setDraftAdvancedFilters((current) => ({
                        ...current,
                        dataFim: event.target.value,
                      }))
                    }
                    className="rounded-2xl border-border/60 bg-card/60"
                  />
                </FilterField>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <FilterField label="Status do contrato">
                  <Select
                    value={draftAdvancedFilters.statusContrato}
                    onValueChange={(value) =>
                      setDraftAdvancedFilters((current) => ({
                        ...current,
                        statusContrato: value,
                      }))
                    }
                  >
                    <SelectTrigger className="rounded-2xl bg-card/60">
                      <SelectValue placeholder="Todos contratos" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="todos">Todos contratos</SelectItem>
                      <SelectItem value="em_analise">Em análise</SelectItem>
                      <SelectItem value="ativo">Ativos</SelectItem>
                      <SelectItem value="encerrado">Encerrados</SelectItem>
                      <SelectItem value="cancelado">Cancelados</SelectItem>
                    </SelectContent>
                  </Select>
                </FilterField>

                <FilterField label="Situação operacional">
                  <Select
                    value={draftAdvancedFilters.situacaoEsteira}
                    onValueChange={(value) =>
                      setDraftAdvancedFilters((current) => ({
                        ...current,
                        situacaoEsteira: value,
                      }))
                    }
                  >
                    <SelectTrigger className="rounded-2xl bg-card/60">
                      <SelectValue placeholder="Todas situações" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="todos">Todas situações</SelectItem>
                      <SelectItem value="aguardando">Aguardando</SelectItem>
                      <SelectItem value="em_andamento">Em andamento</SelectItem>
                      <SelectItem value="aprovado">Aprovados</SelectItem>
                      <SelectItem value="pendenciado">Pendenciados</SelectItem>
                      <SelectItem value="rejeitado">Rejeitados</SelectItem>
                    </SelectContent>
                  </Select>
                </FilterField>
              </div>
            </div>

            <SheetFooter className="border-t border-border/60">
              <Button
                variant="outline"
                type="button"
                onClick={() => {
                  setAgenteFiltro("");
                  setDataInicio("");
                  setDataFim("");
                  setStatusContrato("todos");
                  setSituacaoEsteira("todos");
                  setDraftAdvancedFilters({
                    dataInicio: "",
                    dataFim: "",
                    agente: "",
                    statusContrato: "todos",
                    situacaoEsteira: "todos",
                  });
                  handleRefresh();
                }}
              >
                Limpar avançados
              </Button>
              <SheetClose asChild>
                <Button
                  type="button"
                  onClick={() => {
                    setAgenteFiltro(draftAdvancedFilters.agente);
                    setDataInicio(draftAdvancedFilters.dataInicio);
                    setDataFim(draftAdvancedFilters.dataFim);
                    setStatusContrato(draftAdvancedFilters.statusContrato);
                    setSituacaoEsteira(draftAdvancedFilters.situacaoEsteira);
                    handleRefresh();
                  }}
                >
                  Aplicar
                </Button>
              </SheetClose>
            </SheetFooter>
          </SheetContent>
        </Sheet>
        <Button
          variant="outline"
          onClick={() => {
            setSearch("");
            setAgenteFiltro("");
            setDataInicio("");
            setDataFim("");
            setStatusContrato("todos");
            setSituacaoEsteira("todos");
            setDraftAdvancedFilters({
              dataInicio: "",
              dataFim: "",
              agente: "",
              statusContrato: "todos",
              situacaoEsteira: "todos",
            });
            handleRefresh();
          }}
        >
          Limpar
        </Button>
      </section>

      <section className="space-y-4">
        <header className="flex items-center justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.28em] text-muted-foreground">
              Pendentes
            </p>
            <h2 className="text-xl font-semibold">Aguardando efetivação PIX</h2>
          </div>
          <p className="text-sm text-muted-foreground">
            Mostrando {buildRangeLabel(pagePending, pendingRows.length, pendingQuery.data?.count ?? 0)}
          </p>
        </header>
        <DataTable
          data={pendingRows}
          columns={columns}
          currentPage={pagePending}
          totalPages={Math.max(1, Math.ceil((pendingQuery.data?.count ?? 0) / PAGE_SIZE))}
          onPageChange={setPagePending}
          emptyMessage="Nenhum contrato pendente para os filtros informados."
          loading={pendingQuery.isLoading}
          skeletonRows={PAGE_SIZE}
        />
      </section>

      {!showOnlyPending ? (
        <>
          <section className="space-y-4">
            <header className="flex items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.28em] text-emerald-300">
                  Pagos
                </p>
                <h2 className="text-xl font-semibold">Contratos efetivados</h2>
              </div>
              <p className="text-sm text-muted-foreground">
                Mostrando {buildRangeLabel(pagePaid, paidRows.length, paidQuery.data?.count ?? 0)}
              </p>
            </header>
            <DataTable
              data={paidRows}
              columns={columns}
              currentPage={pagePaid}
              totalPages={Math.max(1, Math.ceil((paidQuery.data?.count ?? 0) / PAGE_SIZE))}
              onPageChange={setPagePaid}
              emptyMessage="Nenhum contrato pago para os filtros informados."
              loading={paidQuery.isLoading}
              skeletonRows={PAGE_SIZE}
            />
          </section>

          <section className="space-y-4">
            <header className="flex items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.28em] text-rose-300">
                  Cancelados
                </p>
                <h2 className="text-xl font-semibold">Contratos cancelados</h2>
              </div>
              <p className="text-sm text-muted-foreground">
                Mostrando {buildRangeLabel(pageCanceled, canceledRows.length, canceledQuery.data?.count ?? 0)}
              </p>
            </header>
            <DataTable
              data={canceledRows}
              columns={columns}
              currentPage={pageCanceled}
              totalPages={Math.max(1, Math.ceil((canceledQuery.data?.count ?? 0) / PAGE_SIZE))}
              onPageChange={setPageCanceled}
              emptyMessage="Nenhum contrato cancelado para os filtros informados."
              loading={canceledQuery.isLoading}
              skeletonRows={PAGE_SIZE}
            />
          </section>
        </>
      ) : null}

      <Dialog open={!!freezeTarget} onOpenChange={(open) => !open && setFreezeTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Congelar contrato</DialogTitle>
            <DialogDescription>
              Registre o motivo para pausar temporariamente a efetivação.
            </DialogDescription>
          </DialogHeader>
          <Textarea
            value={freezeReason}
            onChange={(event) => setFreezeReason(event.target.value)}
            placeholder="Descreva o motivo do congelamento..."
            className="min-h-32"
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setFreezeTarget(null)}>
              Cancelar
            </Button>
            <Button
              onClick={() => {
                if (!freezeTarget || !freezeReason.trim()) {
                  toast.error("Informe um motivo para congelar o contrato.");
                  return;
                }
                congelarMutation.mutate({
                  contratoId: freezeTarget.id,
                  motivo: freezeReason,
                });
              }}
              disabled={congelarMutation.isPending}
            >
              Confirmar congelamento
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!bankTarget} onOpenChange={(open) => !open && setBankTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Dados bancários</DialogTitle>
            <DialogDescription>
              Use estas informações para executar a transferência PIX do contrato.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-3 rounded-2xl border border-border/60 bg-card/60 p-4 text-sm">
            <InfoLine label="Banco" value={bankTarget?.dados_bancarios?.banco} />
            <InfoLine label="Agência" value={bankTarget?.dados_bancarios?.agencia} />
            <InfoLine label="Conta" value={bankTarget?.dados_bancarios?.conta} />
            <InfoLine label="Tipo" value={bankTarget?.dados_bancarios?.tipo_conta} />
            <InfoLine label="Chave PIX" value={bankTarget?.dados_bancarios?.chave_pix || "—"} />
          </div>
        </DialogContent>
      </Dialog>

      <AssociadoDetailsDialog
        open={!!detailTarget}
        onOpenChange={(open) => !open && setDetailTarget(null)}
        associadoId={detailTarget?.associado_id ?? null}
        description="Consulta expandida do associado, contratos e ciclos diretamente na fila de novos contratos."
      />
    </div>
  );
}

function FilterField({
  label,
  children,
}: React.PropsWithChildren<{ label: string }>) {
  return (
    <div className="space-y-2">
      <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
        {label}
      </p>
      {children}
    </div>
  );
}

function ComprovanteSlot({
  label,
  existingUrl,
  existingName,
  draftFile,
  disabled,
  isProcessing,
  compact,
  onSelect,
  onClear,
}: {
  label: string;
  existingUrl?: string;
  existingName?: string;
  draftFile?: File;
  disabled?: boolean;
  isProcessing?: boolean;
  compact?: boolean;
  onSelect: (file: File) => void;
  onClear: () => void;
}) {
  const inputRef = React.useRef<HTMLInputElement | null>(null);
  const accept = React.useMemo(
    () => Object.values(comprovanteAccept).flat().join(","),
    [],
  );
  const canReplace = !disabled && !isProcessing;
  const handleFileSelection = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    onSelect(file);
    event.target.value = "";
  };

  const openPicker = () => {
    if (!canReplace) {
      return;
    }
    inputRef.current?.click();
  };

  const displayName = draftFile?.name || existingName;
  const displayUrl = draftFile ? undefined : existingUrl;
  const primaryActionLabel = label;

  return (
    <div
      className={compact
        ? "rounded-xl border border-border/60 bg-background/40 p-2"
        : "rounded-2xl border border-border/60 bg-background/40 p-3"}
    >
      <input
        ref={inputRef}
        type="file"
        className="hidden"
        accept={accept}
        disabled={!canReplace}
        onChange={handleFileSelection}
      />
      {compact ? (
        <div className="space-y-2">
          {displayUrl ? (
            <Button asChild size="xs" variant="outline" className="w-full justify-start">
              <a href={buildBackendFileUrl(displayUrl)} target="_blank" rel="noreferrer">
                <PaperclipIcon className="size-4" />
                {primaryActionLabel}
              </a>
            </Button>
          ) : (
            <Button
              size="xs"
              variant="outline"
              className="w-full justify-start"
              onClick={openPicker}
              disabled={!canReplace}
            >
              <UploadIcon className="size-4" />
              {primaryActionLabel}
            </Button>
          )}
          <div className="flex gap-2">
            <Button
              size="xs"
              variant="outline"
              className="flex-1"
              onClick={openPicker}
              disabled={!canReplace}
            >
              <UploadIcon className="size-4" />
              {displayName ? "Substituir" : "Enviar"}
            </Button>
            {draftFile ? (
              <Button size="icon-sm" variant="ghost" onClick={onClear}>
                <Trash2Icon className="size-4" />
              </Button>
            ) : null}
          </div>
        </div>
      ) : (
        <div className="space-y-2">
          <div className="mb-2 flex items-center justify-between gap-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-muted-foreground">
              {label}
            </p>
            {draftFile ? (
              <Button size="icon-sm" variant="ghost" onClick={onClear}>
                <Trash2Icon className="size-4" />
              </Button>
            ) : null}
          </div>
          {displayName ? (
            <div className="space-y-1 text-sm">
              <p className="font-medium" title={displayName}>
                {displayName}
              </p>
              {draftFile ? (
                <p className="text-xs text-muted-foreground">
                  {(draftFile.size / 1024 / 1024).toFixed(2)} MB pronto para envio.
                </p>
              ) : (
                <p className="text-xs text-muted-foreground">Arquivo já anexado.</p>
              )}
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">Nenhum arquivo enviado.</p>
          )}

          <div className="flex flex-wrap gap-2">
            {displayUrl ? (
              <Button asChild size="sm" variant="outline">
                <a href={buildBackendFileUrl(displayUrl)} target="_blank" rel="noreferrer">
                  <PaperclipIcon className="size-4" />
                  Ver arquivo
                </a>
              </Button>
            ) : null}
            <Button size="sm" variant="outline" onClick={openPicker} disabled={!canReplace}>
              <UploadIcon className="size-4" />
              {draftFile ? "Trocar" : displayUrl ? "Substituir" : "Enviar"}
            </Button>
          </div>
          <p className="text-[11px] text-muted-foreground">PDF, JPG ou PNG até 5 MB.</p>
        </div>
      )}
    </div>
  );
}

function InfoLine({ label, value }: { label: string; value?: string }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-medium capitalize">{value || "—"}</span>
    </div>
  );
}
