"use client";

import Link from "next/link";
import * as React from "react";
import {
  useMutation,
  useQueries,
  useQuery,
  useQueryClient,
  type UseQueryResult,
} from "@tanstack/react-query";
import {
  ExternalLinkIcon,
  FileTextIcon,
  SearchIcon,
  SlidersHorizontalIcon,
  ShieldCheckIcon,
  Trash2Icon,
  WalletIcon,
} from "lucide-react";
import { toast } from "sonner";

import type {
  AnaliseResumo,
  AnaliseSectionKey,
  EsteiraItem,
  PaginatedMetaResponse,
  SimpleUser,
  SystemUserListItem,
  SystemUsersMeta,
} from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import { buildBackendFileUrl } from "@/lib/backend-files";
import {
  dashboardOptionsQueryOptions,
  dashboardRetainedQueryOptions,
} from "@/lib/dashboard-query";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { usePermissions } from "@/hooks/use-permissions";
import DatePicker from "@/components/custom/date-picker";
import SearchableSelect from "@/components/custom/searchable-select";
import StatusBadge from "@/components/custom/status-badge";
import CopySnippet from "@/components/shared/copy-snippet";
import DataTable, {
  type DataTableColumn,
} from "@/components/shared/data-table";
import EmptyState from "@/components/shared/empty-state";
import {
  InlinePanelSkeleton,
  MetricCardSkeleton,
  WorklistRouteSkeleton,
} from "@/components/shared/page-skeletons";
import StatsCard from "@/components/shared/stats-card";
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
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";

const FILA_SECTIONS: Array<{
  key: AnaliseSectionKey;
  title: string;
  tooltip?: string;
  description: string;
  emptyMessage: string;
  tone: "positive" | "warning" | "neutral";
  icon: typeof SearchIcon;
  delta: (summary: AnaliseResumo | undefined) => string;
}> = [
  {
    key: "novos_contratos",
    title: "Novos Contratos",
    tooltip:
      "Entradas novas da análise sem pendência aberta e ainda não encaminhadas.",
    description:
      "Entradas novas da análise sem pendência documental aberta e prontas para triagem inicial.",
    emptyMessage: "Nenhum novo contrato aguardando triagem no momento.",
    tone: "neutral",
    icon: FileTextIcon,
    delta: (summary) =>
      `${summary?.filas.pendencias ?? 0} seguem com pendência documental`,
  },
  {
    key: "ver_todos",
    title: "Ver todos",
    description:
      "Visão completa do pipeline do analista, incluindo encaminhados, efetivados e cancelados.",
    emptyMessage: "Nenhum item encontrado no fluxo consolidado.",
    tone: "neutral",
    icon: SearchIcon,
    delta: (summary) =>
      `${summary?.filas.pendencias ?? 0} ainda exigem ação do analista`,
  },
  {
    key: "pendencias",
    title: "Pendências",
    tooltip:
      "Casos com documento faltando, pendência aberta ou cadastro sem documentação válida.",
    description:
      "Pendências documentais abertas ou cadastros ainda sem documentação inicial.",
    emptyMessage: "Nenhuma pendência aberta no momento.",
    tone: "warning",
    icon: ShieldCheckIcon,
    delta: (summary) =>
      `${summary?.filas.pendencias_corrigidas ?? 0} corrigidas aguardando conferência`,
  },
  {
    key: "pendencias_corrigidas",
    title: "Pendências Corrigidas",
    tooltip:
      "Casos reenviados após correção e aguardando nova conferência do analista.",
    description:
      "Itens corrigidos pelo agente e reenviados para nova validação do analista.",
    emptyMessage: "Nenhuma pendência corrigida aguardando validação.",
    tone: "positive",
    icon: FileTextIcon,
    delta: (summary) =>
      `${summary?.filas.pendencias ?? 0} ainda seguem em pendência`,
  },
  {
    key: "enviado_tesouraria",
    title: "Enviado para Tesouraria",
    tooltip:
      "Casos aprovados pela análise e já encaminhados para a etapa financeira.",
    description:
      "Itens já aprovados na análise e aguardando a etapa financeira.",
    emptyMessage: "Nenhum item aguardando tesouraria.",
    tone: "neutral",
    icon: WalletIcon,
    delta: () => "Acompanhamento pós-análise",
  },
  {
    key: "enviado_coordenacao",
    title: "Enviado para Coordenação",
    tooltip:
      "Casos que ainda dependem de validação da coordenação antes da etapa financeira.",
    description:
      "Itens encaminhados para coordenação antes da liberação financeira.",
    emptyMessage: "Nenhum item aguardando coordenação.",
    tone: "neutral",
    icon: ExternalLinkIcon,
    delta: () => "Aguardando validação da coordenação",
  },
  {
    key: "efetivados",
    title: "Efetivados",
    description:
      "Fluxos concluídos com contrato liberado e sem cancelamento posterior.",
    emptyMessage: "Nenhum fluxo efetivado encontrado.",
    tone: "positive",
    icon: ShieldCheckIcon,
    delta: () => "Concluídos com sucesso na esteira",
  },
  {
    key: "cancelados",
    title: "Cancelados",
    description: "Fluxos cujo contrato atual foi cancelado.",
    emptyMessage: "Nenhum fluxo cancelado encontrado.",
    tone: "warning",
    icon: Trash2Icon,
    delta: () => "Contrato atual cancelado",
  },
];

type DialogState =
  | { mode: "assumir"; item: EsteiraItem }
  | { mode: "aprovar"; item: EsteiraItem }
  | { mode: "documentos"; item: EsteiraItem }
  | { mode: "excluir"; item: EsteiraItem }
  | { mode: "correcao"; item: EsteiraItem }
  | null;

function getInitialSectionPages() {
  return FILA_SECTIONS.reduce(
    (accumulator, section) => {
      accumulator[section.key] = 1;
      return accumulator;
    },
    {} as Record<AnaliseSectionKey, number>,
  );
}

function getTotalPages(count: number | undefined, pageSize: string) {
  return Math.max(1, Math.ceil((count ?? 0) / Number(pageSize)));
}

function getSectionId(sectionKey: AnaliseSectionKey) {
  return `analise-section-${sectionKey}`;
}

function SummaryCard({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-border/60 bg-card/60 p-4">
      <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
        {label}
      </p>
      <div className="mt-3 space-y-2 text-sm font-medium text-foreground">
        {children}
      </div>
    </div>
  );
}

export default function AnalisePage() {
  const queryClient = useQueryClient();
  const { hasAnyRole, hasRole, status, user } = usePermissions();
  const isAnalistaEnabled = hasAnyRole(["ANALISTA", "COORDENADOR", "ADMIN"]);
  const [search, setSearch] = React.useState("");
  const [pageSize, setPageSize] = React.useState("5");
  const [filaPages, setFilaPages] = React.useState<
    Record<AnaliseSectionKey, number>
  >(getInitialSectionPages);
  const [filtersOpen, setFiltersOpen] = React.useState(false);
  const [agenteFilter, setAgenteFilter] = React.useState("");
  const [analistaFilter, setAnalistaFilter] = React.useState("");
  const [etapaFilter, setEtapaFilter] = React.useState("");
  const [statusFilter, setStatusFilter] = React.useState("");
  const [dataInicio, setDataInicio] = React.useState<Date | undefined>();
  const [dataFim, setDataFim] = React.useState<Date | undefined>();
  const [draftAgenteFilter, setDraftAgenteFilter] = React.useState("");
  const [draftAnalistaFilter, setDraftAnalistaFilter] = React.useState("");
  const [draftEtapaFilter, setDraftEtapaFilter] = React.useState("");
  const [draftStatusFilter, setDraftStatusFilter] = React.useState("");
  const [draftDataInicio, setDraftDataInicio] = React.useState<
    Date | undefined
  >();
  const [draftDataFim, setDraftDataFim] = React.useState<Date | undefined>();
  const [dialogState, setDialogState] = React.useState<DialogState>(null);
  const [observacao, setObservacao] = React.useState("");
  const debouncedSearch = useDebouncedValue(search, 300);
  const documentoItemId =
    dialogState?.mode === "documentos" ? dialogState.item.id : null;

  const formatDateForQuery = React.useCallback((value?: Date) => {
    if (!value) return undefined;

    const year = value.getFullYear();
    const month = String(value.getMonth() + 1).padStart(2, "0");
    const day = String(value.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  }, []);

  const resetPages = React.useCallback(() => {
    setFilaPages(getInitialSectionPages());
  }, []);

  const invalidateAnaliseQueries = React.useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ["analise-resumo"] });
    void queryClient.invalidateQueries({ queryKey: ["analise-filas"] });
    void queryClient.invalidateQueries({ queryKey: ["esteira"] });
    void queryClient.invalidateQueries({ queryKey: ["esteira-detalhe"] });
    void queryClient.invalidateQueries({ queryKey: ["dashboard-esteira"] });
  }, [queryClient]);

  const scrollToSection = React.useCallback((sectionKey: AnaliseSectionKey) => {
    const section = document.getElementById(getSectionId(sectionKey));
    section?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  const summaryQuery = useQuery({
    queryKey: [
      "analise-resumo",
      debouncedSearch,
      agenteFilter,
      analistaFilter,
      etapaFilter,
      statusFilter,
      formatDateForQuery(dataInicio),
      formatDateForQuery(dataFim),
    ],
    queryFn: () =>
      apiFetch<AnaliseResumo>("analise", {
        query: {
          search: debouncedSearch,
          agente: agenteFilter || undefined,
          analista: analistaFilter || undefined,
          etapa: etapaFilter || undefined,
          status: statusFilter || undefined,
          data_inicio: formatDateForQuery(dataInicio),
          data_fim: formatDateForQuery(dataFim),
        },
      }),
    enabled: isAnalistaEnabled,
    ...dashboardRetainedQueryOptions,
  });

  const agentesQuery = useQuery({
    queryKey: ["analise-agentes"],
    queryFn: () => apiFetch<SimpleUser[]>("associados/agentes"),
    enabled: isAnalistaEnabled,
    ...dashboardOptionsQueryOptions,
  });

  const analistasQuery = useQuery({
    queryKey: ["analise-analistas"],
    queryFn: () =>
      apiFetch<PaginatedMetaResponse<SystemUserListItem, SystemUsersMeta>>(
        "configuracoes/usuarios",
        {
          query: {
            role: "ANALISTA",
            page_size: 100,
          },
        },
      ),
    enabled: hasAnyRole(["ADMIN", "COORDENADOR"]),
    ...dashboardOptionsQueryOptions,
  });

  const filaQueries = useQueries({
    queries: FILA_SECTIONS.map((section) => ({
      queryKey: [
        "analise-filas",
        section.key,
        filaPages[section.key],
        pageSize,
        debouncedSearch,
        agenteFilter,
        analistaFilter,
        etapaFilter,
        statusFilter,
        formatDateForQuery(dataInicio),
        formatDateForQuery(dataFim),
      ],
      queryFn: () =>
        apiFetch<
          PaginatedMetaResponse<EsteiraItem, { secao: AnaliseSectionKey }>
        >("analise/filas", {
          query: {
            secao: section.key,
            page: filaPages[section.key],
            page_size: Number(pageSize),
            search: debouncedSearch,
            agente: agenteFilter || undefined,
            analista: analistaFilter || undefined,
            etapa: etapaFilter || undefined,
            status: statusFilter || undefined,
            data_inicio: formatDateForQuery(dataInicio),
            data_fim: formatDateForQuery(dataFim),
          },
        }),
      enabled: isAnalistaEnabled,
      ...dashboardRetainedQueryOptions,
    })),
  }) as Array<
    UseQueryResult<
      PaginatedMetaResponse<EsteiraItem, { secao: AnaliseSectionKey }>,
      Error
    >
  >;

  const detalheQuery = useQuery({
    queryKey: ["esteira-detalhe", documentoItemId],
    queryFn: () => apiFetch<EsteiraItem>(`esteira/${documentoItemId}`),
    enabled: !!documentoItemId,
  });

  const actionMutation = useMutation({
    mutationFn: async ({
      item,
      action,
      payload,
    }: {
      item: EsteiraItem;
      action:
        | "assumir"
        | "aprovar"
        | "validar-documento"
        | "solicitar-correcao";
      payload?: Record<string, string>;
    }) => {
      await apiFetch(`esteira/${item.id}/${action}`, {
        method: "POST",
        body: payload,
      });
    },
    onSuccess: (_, variables) => {
      toast.success("Ação executada com sucesso.");
      setDialogState(null);
      setObservacao("");
      invalidateAnaliseQueries();
      if (variables.action === "aprovar") {
        void queryClient.invalidateQueries({
          queryKey: ["tesouraria-contratos"],
        });
        void queryClient.invalidateQueries({
          queryKey: ["dashboard-tesouraria"],
        });
      }
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : "Falha ao executar ação.",
      );
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (item: EsteiraItem) => {
      await apiFetch(`esteira/${item.id}`, {
        method: "DELETE",
      });
    },
    onSuccess: () => {
      toast.success("Solicitação excluída com sucesso.");
      setDialogState(null);
      setObservacao("");
      invalidateAnaliseQueries();
    },
    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : "Falha ao excluir solicitação.",
      );
    },
  });

  const filaColumns = React.useMemo<DataTableColumn<EsteiraItem>[]>(
    () => [
      {
        id: "assumir",
        header: "Assumir",
        cell: (row) =>
          row.etapa_atual === "analise" &&
          row.acoes_disponiveis.includes("assumir") ? (
            <Button
              size="sm"
              onClick={() => setDialogState({ mode: "assumir", item: row })}
            >
              Assumir
            </Button>
          ) : (
            "-"
          ),
      },
      {
        id: "nome",
        header: "Nome",
        cell: (row) => (
          <CopySnippet
            label="Nome"
            value={row.contrato?.associado_nome ?? "-"}
            inline
          />
        ),
      },
      {
        id: "cpf",
        header: "CPF",
        cell: (row) => (
          <CopySnippet
            label="CPF"
            value={row.contrato?.cpf_cnpj ?? "-"}
            mono
            inline
          />
        ),
      },
      {
        id: "matricula",
        header: "Matrícula",
        cell: (row) => (
          <CopySnippet
            label="Matrícula"
            value={
              row.contrato?.matricula_display ?? row.contrato?.matricula ?? "-"
            }
            mono
            inline
          />
        ),
      },
      {
        id: "documentacao",
        header: "Documentação",
        cell: (row) => <StatusBadge status={row.status_documentacao} />,
      },
      {
        id: "fluxo",
        header: "Status",
        cell: (row) => <StatusBadge status={row.status} />,
      },
      {
        id: "agente",
        header: "Agente",
        cell: (row) => row.agente?.full_name ?? "-",
      },
      {
        id: "analista",
        header: "Analista responsável",
        cell: (row) => row.analista_responsavel?.full_name ?? "Sem responsável",
      },
      {
        id: "documentos",
        header: "Docs",
        cell: (row) => (
          <Button
            variant="outline"
            size="sm"
            className="gap-2 rounded-xl"
            onClick={() => setDialogState({ mode: "documentos", item: row })}
          >
            <FileTextIcon className="size-4" />
            Ver docs
            <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-semibold text-primary">
              {row.documentos_count}
            </span>
          </Button>
        ),
      },
      {
        id: "acoes",
        header: "Ações",
        cell: (row) => (
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="outline" asChild>
              <Link href={`/associados/${row.associado_id}`}>Ver detalhes</Link>
            </Button>
            {row.etapa_atual === "analise" &&
            row.status_documentacao === "reenvio_pendente" ? (
              <Button
                size="sm"
                variant="outline"
                onClick={() =>
                  actionMutation.mutate({
                    item: row,
                    action: "validar-documento",
                  })
                }
              >
                Validar revisto
              </Button>
            ) : null}
            {row.etapa_atual === "analise" &&
            row.acoes_disponiveis.includes("aprovar") ? (
              <Button
                size="sm"
                onClick={() => setDialogState({ mode: "aprovar", item: row })}
              >
                Aprovar
              </Button>
            ) : null}
            {row.etapa_atual === "analise" &&
            row.acoes_disponiveis.includes("solicitar_correcao") ? (
              <Button
                size="sm"
                variant="outline"
                onClick={() => setDialogState({ mode: "correcao", item: row })}
              >
                Solicitar correção
              </Button>
            ) : null}
            {row.acoes_disponiveis.includes("excluir") ? (
              <Button
                size="sm"
                variant="destructive"
                onClick={() => setDialogState({ mode: "excluir", item: row })}
              >
                Excluir
              </Button>
            ) : null}
          </div>
        ),
      },
    ],
    [actionMutation],
  );

  const activeFiltersCount =
    Number(Boolean(agenteFilter)) +
    Number(Boolean(analistaFilter)) +
    Number(Boolean(etapaFilter)) +
    Number(Boolean(statusFilter)) +
    Number(Boolean(dataInicio)) +
    Number(Boolean(dataFim));

  const agentOptions = React.useMemo(
    () =>
      (agentesQuery.data ?? []).map((item) => ({
        value: String(item.id),
        label: item.full_name,
      })),
    [agentesQuery.data],
  );

  const analystOptions = React.useMemo(() => {
    const options = [
      { value: "sem_responsavel", label: "Sem responsável" },
      ...(hasAnyRole(["ADMIN", "COORDENADOR"])
        ? (analistasQuery.data?.results ?? []).map((item) => ({
            value: String(item.id),
            label: item.full_name,
          }))
        : user
          ? [
              {
                value: String(user.id),
                label: `${user.full_name} · meus casos`,
              },
            ]
          : []),
    ];

    return options;
  }, [analistasQuery.data?.results, hasAnyRole, user]);

  if (status !== "authenticated") {
    return <WorklistRouteSkeleton />;
  }

  if (!isAnalistaEnabled) {
    return (
      <EmptyState
        title="Acesso não disponível"
        description="Este módulo está liberado para perfis de analista, coordenador ou administrador."
      />
    );
  }

  const documentoItem =
    dialogState?.mode === "documentos" ? dialogState.item : null;
  const detalheItem = detalheQuery.data ?? documentoItem;
  const pendenciasAbertas =
    detalheQuery.data?.pendencias?.filter(
      (pendencia) => pendencia.status === "aberta",
    ).length ?? 0;
  const pendenciasResolvidas =
    detalheQuery.data?.pendencias?.filter(
      (pendencia) => pendencia.status === "resolvida",
    ).length ?? 0;

  return (
    <div className="space-y-8">
      <section className="space-y-4">
        <div className="space-y-2">
          <p className="text-sm uppercase tracking-[0.2em] text-muted-foreground">
            Análise operacional
          </p>
          <h1 className="text-3xl font-semibold text-foreground">
            Dashboard de análise
          </h1>
          <p className="max-w-4xl text-sm text-muted-foreground">
            Painel consolidado das filas da esteira para revisar documentação,
            acompanhar encaminhamentos, excluir solicitações elegíveis e entrar
            no detalhe completo de cada associado.
          </p>
        </div>

        <div className="flex flex-col gap-3 xl:flex-row xl:items-center">
          <div className="relative flex-1">
            <SearchIcon className="pointer-events-none absolute top-1/2 left-4 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                resetPages();
              }}
              placeholder="Buscar por nome, CPF, matrícula ou contrato..."
              className="rounded-2xl border-border/60 bg-card/60 pl-11"
            />
          </div>
          <Select
            value={pageSize}
            onValueChange={(value) => {
              setPageSize(value);
              resetPages();
            }}
          >
            <SelectTrigger className="w-full rounded-2xl bg-card/60 xl:w-40">
              <SelectValue placeholder="5/página" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="5">5/página</SelectItem>
              <SelectItem value="10">10/página</SelectItem>
              <SelectItem value="20">20/página</SelectItem>
            </SelectContent>
          </Select>
          <Sheet
            open={filtersOpen}
            onOpenChange={(open) => {
              if (open) {
                setDraftAgenteFilter(agenteFilter);
                setDraftAnalistaFilter(analistaFilter);
                setDraftEtapaFilter(etapaFilter);
                setDraftStatusFilter(statusFilter);
                setDraftDataInicio(dataInicio);
                setDraftDataFim(dataFim);
              }
              setFiltersOpen(open);
            }}
          >
            <SheetTrigger asChild>
              <Button variant="outline" className="rounded-2xl">
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
                  Refine a fila por analista responsável, agente, etapa, status
                  e janela de criação.
                </SheetDescription>
              </SheetHeader>

              <div className="space-y-5 overflow-y-auto px-4 pb-4">
                <div className="space-y-2">
                  <Label>Agente</Label>
                  <SearchableSelect
                    options={agentOptions}
                    value={draftAgenteFilter}
                    onChange={setDraftAgenteFilter}
                    placeholder="Todos os agentes"
                    searchPlaceholder="Buscar agente"
                    clearLabel="Limpar agente"
                  />
                </div>

                <div className="space-y-2">
                  <Label>Analista responsável</Label>
                  <SearchableSelect
                    options={analystOptions}
                    value={draftAnalistaFilter}
                    onChange={setDraftAnalistaFilter}
                    placeholder="Todos os analistas"
                    searchPlaceholder="Buscar analista"
                    clearLabel="Limpar analista"
                  />
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label>Etapa</Label>
                    <Select
                      value={draftEtapaFilter || "todos"}
                      onValueChange={(value) =>
                        setDraftEtapaFilter(value === "todos" ? "" : value)
                      }
                    >
                      <SelectTrigger className="rounded-xl border-border/60 bg-card/60">
                        <SelectValue placeholder="Todas as etapas" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="todos">Todas</SelectItem>
                        <SelectItem value="cadastro">Cadastro</SelectItem>
                        <SelectItem value="analise">Análise</SelectItem>
                        <SelectItem value="coordenacao">Coordenação</SelectItem>
                        <SelectItem value="tesouraria">Tesouraria</SelectItem>
                        <SelectItem value="concluido">Concluído</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label>Status</Label>
                    <Select
                      value={draftStatusFilter || "todos"}
                      onValueChange={(value) =>
                        setDraftStatusFilter(value === "todos" ? "" : value)
                      }
                    >
                      <SelectTrigger className="rounded-xl border-border/60 bg-card/60">
                        <SelectValue placeholder="Todos os status" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="todos">Todos</SelectItem>
                        <SelectItem value="aguardando">Aguardando</SelectItem>
                        <SelectItem value="em_andamento">
                          Em andamento
                        </SelectItem>
                        <SelectItem value="pendenciado">Pendenciado</SelectItem>
                        <SelectItem value="aprovado">Aprovado</SelectItem>
                        <SelectItem value="rejeitado">Rejeitado</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label>Data inicial</Label>
                    <DatePicker
                      value={draftDataInicio}
                      onChange={setDraftDataInicio}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Data final</Label>
                    <DatePicker
                      value={draftDataFim}
                      onChange={setDraftDataFim}
                    />
                  </div>
                </div>
              </div>

              <SheetFooter>
                <Button
                  variant="outline"
                  onClick={() => {
                    setDraftAgenteFilter("");
                    setDraftAnalistaFilter("");
                    setDraftEtapaFilter("");
                    setDraftStatusFilter("");
                    setDraftDataInicio(undefined);
                    setDraftDataFim(undefined);
                    setAgenteFilter("");
                    setAnalistaFilter("");
                    setEtapaFilter("");
                    setStatusFilter("");
                    setDataInicio(undefined);
                    setDataFim(undefined);
                    resetPages();
                    setFiltersOpen(false);
                  }}
                >
                  Limpar
                </Button>
                <Button
                  onClick={() => {
                    setAgenteFilter(draftAgenteFilter);
                    setAnalistaFilter(draftAnalistaFilter);
                    setEtapaFilter(draftEtapaFilter);
                    setStatusFilter(draftStatusFilter);
                    setDataInicio(draftDataInicio);
                    setDataFim(draftDataFim);
                    resetPages();
                    setFiltersOpen(false);
                  }}
                >
                  Aplicar
                </Button>
              </SheetFooter>
            </SheetContent>
          </Sheet>
          <Button onClick={resetPages}>Atualizar</Button>
          <Button
            variant="outline"
            onClick={() => {
              setSearch("");
              setAgenteFilter("");
              setAnalistaFilter("");
              setEtapaFilter("");
              setStatusFilter("");
              setDataInicio(undefined);
              setDataFim(undefined);
              resetPages();
            }}
          >
            Limpar
          </Button>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-7">
        {summaryQuery.isLoading && !summaryQuery.data
          ? Array.from({ length: FILA_SECTIONS.length }).map((_, index) => (
              <MetricCardSkeleton key={index} />
            ))
          : FILA_SECTIONS.map((section) => (
              <StatsCard
                key={section.key}
                title={section.title}
                tooltip={section.tooltip}
                value={String(summaryQuery.data?.filas[section.key] ?? 0)}
                delta={section.delta(summaryQuery.data)}
                tone={section.tone}
                icon={section.icon}
                onClick={() => scrollToSection(section.key)}
              />
            ))}
      </section>

      <section className="space-y-6">
        {FILA_SECTIONS.map((section, index) => {
          const query = filaQueries[index];
          const count =
            summaryQuery.data?.filas[section.key] ?? query.data?.count ?? 0;

          return (
            <Card
              id={getSectionId(section.key)}
              key={section.key}
              className="scroll-mt-24 rounded-[1.75rem] border-border/60 bg-card/70 shadow-xl shadow-black/20"
            >
              <CardHeader>
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <CardTitle>{section.title}</CardTitle>
                    <CardDescription>{section.description}</CardDescription>
                  </div>
                  <Badge variant="outline">{count} itens</Badge>
                </div>
              </CardHeader>
              <CardContent>
                <DataTable
                  data={query.data?.results ?? []}
                  columns={filaColumns}
                  currentPage={filaPages[section.key]}
                  totalPages={getTotalPages(query.data?.count, pageSize)}
                  onPageChange={(page) =>
                    setFilaPages((current) => ({
                      ...current,
                      [section.key]: page,
                    }))
                  }
                  emptyMessage={section.emptyMessage}
                  loading={query.isLoading}
                  skeletonRows={5}
                />
              </CardContent>
            </Card>
          );
        })}
      </section>

      <Dialog
        open={!!dialogState}
        onOpenChange={(open) => {
          if (open) return;
          setDialogState(null);
          setObservacao("");
        }}
      >
        <DialogContent
          className={
            dialogState?.mode === "documentos"
              ? "grid h-[min(94vh,58rem)] w-[calc(100vw-2rem)] !max-w-[1680px] grid-rows-[auto_minmax(0,1fr)_auto] overflow-hidden p-0 xl:w-[calc(100vw-5rem)]"
              : "max-w-2xl"
          }
        >
          <DialogHeader
            className={
              dialogState?.mode === "documentos"
                ? "border-b border-border/60 px-6 pb-4 pt-6 pr-14"
                : undefined
            }
          >
            <DialogTitle>
              {dialogState?.mode === "assumir"
                ? "Assumir análise"
                : dialogState?.mode === "aprovar"
                  ? "Confirmar aprovação"
                  : dialogState?.mode === "excluir"
                    ? "Excluir solicitação"
                    : dialogState?.mode === "correcao"
                      ? "Solicitar correção"
                      : "Documentos e formulário"}
            </DialogTitle>
            <DialogDescription>
              {dialogState?.mode === "assumir"
                ? `Deseja assumir a análise do contrato ${dialogState.item.contrato?.codigo}?`
                : dialogState?.mode === "aprovar"
                  ? `Confirme a aprovação do contrato ${dialogState.item.contrato?.codigo} para a próxima etapa da esteira.`
                  : dialogState?.mode === "excluir"
                    ? `Confirme a exclusão lógica da solicitação ${dialogState.item.contrato?.codigo}. O associado, a esteira e a árvore contratual ativa serão removidos das filas operacionais.`
                    : dialogState?.mode === "correcao"
                      ? "Informe a observação que deve ser enviada ao agente."
                      : "Documentos anexados e resumo rápido do cadastro em análise."}
            </DialogDescription>
          </DialogHeader>

          {dialogState?.mode === "documentos" ? (
            detalheQuery.isLoading ? (
              <div className="px-6 py-6">
                <InlinePanelSkeleton rows={3} />
              </div>
            ) : (
              <div className="grid min-h-0 grid-cols-1 overflow-hidden xl:grid-cols-[320px_minmax(0,1fr)] 2xl:grid-cols-[360px_minmax(0,1fr)]">
                <div className="min-h-0 overflow-y-auto border-b border-border/60 xl:border-b-0 xl:border-r">
                  <div className="space-y-4 p-6">
                    <SummaryCard label="Associado">
                      <p>{detalheItem?.contrato?.associado_nome ?? "-"}</p>
                      <p className="text-muted-foreground">
                        Órgão: {detalheItem?.orgao_publico || "-"}
                      </p>
                    </SummaryCard>
                    <SummaryCard label="Contrato">
                      <p className="break-all">
                        {detalheItem?.contrato?.codigo ?? "-"}
                      </p>
                      <p className="text-muted-foreground">
                        Assumido em{" "}
                        {detalheItem?.assumido_em
                          ? new Intl.DateTimeFormat("pt-BR", {
                              day: "2-digit",
                              month: "2-digit",
                              year: "numeric",
                              hour: "2-digit",
                              minute: "2-digit",
                              hour12: false,
                            }).format(new Date(detalheItem.assumido_em))
                          : "N/I"}
                      </p>
                    </SummaryCard>
                    <SummaryCard label="CPF / Matrícula">
                      <p>{detalheItem?.contrato?.cpf_cnpj ?? "-"}</p>
                      <p className="text-muted-foreground">
                        {detalheItem?.contrato?.matricula_display ??
                          detalheItem?.contrato?.matricula ??
                          "-"}
                      </p>
                    </SummaryCard>
                    <SummaryCard label="Status do fluxo">
                      <div className="flex flex-wrap gap-2">
                        <StatusBadge
                          status={
                            detalheItem?.status_documentacao ?? "incompleta"
                          }
                        />
                        <StatusBadge
                          status={detalheItem?.status ?? "aguardando"}
                        />
                      </div>
                    </SummaryCard>
                    <SummaryCard label="Pendências">
                      <div className="flex flex-wrap gap-2">
                        <Badge variant="outline">
                          {pendenciasAbertas} abertas
                        </Badge>
                        <Badge variant="outline">
                          {pendenciasResolvidas} resolvidas
                        </Badge>
                      </div>
                      <p className="text-muted-foreground">
                        {detalheQuery.data?.pendencias?.length
                          ? "Resumo rápido das ocorrências registradas na esteira."
                          : "Nenhuma pendência registrada neste item."}
                      </p>
                    </SummaryCard>
                  </div>
                </div>

                <div className="flex min-h-0 min-w-0 flex-col overflow-hidden">
                  <div className="border-b border-border/60 px-6 py-5">
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-foreground">
                          Documentos anexados
                        </p>
                        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
                          Revise os arquivos do cadastro e siga para o detalhe
                          completo quando precisar analisar o histórico inteiro
                          do associado.
                        </p>
                      </div>
                      {detalheItem?.associado_id ? (
                        <Button
                          asChild
                          variant="outline"
                          size="sm"
                          className="shrink-0"
                        >
                          <Link
                            href={`/associados/${detalheItem.associado_id}`}
                          >
                            Ver detalhes completos
                          </Link>
                        </Button>
                      ) : null}
                    </div>
                  </div>

                  <div className="min-h-0 overflow-y-auto overflow-x-hidden p-6">
                    <div className="min-w-0">
                      <div className="grid gap-4 lg:grid-cols-2 2xl:grid-cols-3">
                        {detalheQuery.data?.documentos?.length ? (
                          detalheQuery.data.documentos.map((documento) => (
                            <div
                              key={documento.id}
                              className="min-w-0 rounded-2xl border border-border/60 bg-card/60 p-4"
                            >
                              <div className="space-y-3">
                                <div className="space-y-2">
                                  <p className="font-medium capitalize">
                                    {documento.tipo.replaceAll("_", " ")}
                                  </p>
                                  <StatusBadge status={documento.status} />
                                  <p className="break-words text-sm text-muted-foreground">
                                    {documento.nome_original ||
                                      documento.arquivo_referencia ||
                                      "Sem nome disponível"}
                                  </p>
                                  {documento.observacao ? (
                                    <p className="break-words text-sm text-muted-foreground">
                                      {documento.observacao}
                                    </p>
                                  ) : null}
                                </div>
                                {documento.arquivo_disponivel_localmente &&
                                documento.arquivo ? (
                                  <Button
                                    asChild
                                    size="sm"
                                    variant="outline"
                                    className="w-full"
                                  >
                                    <a
                                      href={buildBackendFileUrl(
                                        documento.arquivo,
                                      )}
                                      target="_blank"
                                      rel="noreferrer"
                                    >
                                      <ExternalLinkIcon className="size-4" />
                                      Ver documento
                                    </a>
                                  </Button>
                                ) : (
                                  <div className="text-sm text-muted-foreground">
                                    <p>Arquivo indisponível localmente.</p>
                                    <p className="break-words text-xs text-amber-200">
                                      {documento.arquivo_referencia ||
                                        "Referência de arquivo legado"}
                                    </p>
                                  </div>
                                )}
                              </div>
                            </div>
                          ))
                        ) : (
                          <p className="text-sm text-muted-foreground">
                            Nenhum documento anexado.
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )
          ) : null}

          {dialogState?.mode === "correcao" ? (
            <Textarea
              value={observacao}
              onChange={(event) => setObservacao(event.target.value)}
              placeholder="Descreva a correção necessária..."
              className="min-h-32"
            />
          ) : null}

          <DialogFooter
            className={
              dialogState?.mode === "documentos"
                ? "border-t border-border/60 px-6 py-4"
                : undefined
            }
          >
            <Button variant="outline" onClick={() => setDialogState(null)}>
              Cancelar
            </Button>
            {dialogState?.mode === "documentos" && detalheItem?.associado_id ? (
              <Button asChild>
                <Link href={`/associados/${detalheItem.associado_id}`}>
                  Ver detalhes completos
                </Link>
              </Button>
            ) : null}
            {dialogState?.mode === "assumir" ? (
              <Button
                onClick={() =>
                  actionMutation.mutate({
                    item: dialogState.item,
                    action: "assumir",
                  })
                }
              >
                Confirmar
              </Button>
            ) : null}
            {dialogState?.mode === "aprovar" ? (
              <Button
                onClick={() =>
                  actionMutation.mutate({
                    item: dialogState.item,
                    action: "aprovar",
                  })
                }
              >
                Aprovar e encaminhar
              </Button>
            ) : null}
            {dialogState?.mode === "correcao" ? (
              <Button
                onClick={() =>
                  actionMutation.mutate({
                    item: dialogState.item,
                    action: "solicitar-correcao",
                    payload: { observacao },
                  })
                }
              >
                Enviar correção
              </Button>
            ) : null}
            {dialogState?.mode === "excluir" ? (
              <Button
                variant="destructive"
                onClick={() => deleteMutation.mutate(dialogState.item)}
              >
                Excluir solicitação
              </Button>
            ) : null}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
