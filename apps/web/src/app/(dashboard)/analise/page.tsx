"use client";

import * as React from "react";
import {
  useMutation,
  useQueries,
  useQuery,
  useQueryClient,
  type UseQueryResult,
} from "@tanstack/react-query";
import {
  BarChart3Icon,
  CalendarClockIcon,
  ExternalLinkIcon,
  FileTextIcon,
  PencilIcon,
  SearchIcon,
  ShieldCheckIcon,
  Trash2Icon,
  WalletIcon,
} from "lucide-react";
import { toast } from "sonner";

import type {
  AnaliseDadosItem,
  AnaliseMargemItem,
  AnaliseMargemMeta,
  AnalisePagamentoItem,
  AnaliseResumo,
  AnaliseSectionKey,
  EsteiraItem,
  PaginatedMetaResponse,
  PaginatedResponse,
} from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import { buildBackendFileUrl } from "@/lib/backend-files";
import { parseMonthValue } from "@/lib/date-value";
import { formatCurrency, formatDate, formatDateTime } from "@/lib/formatters";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { usePermissions } from "@/hooks/use-permissions";
import CalendarCompetencia from "@/components/custom/calendar-competencia";
import DateTimePicker from "@/components/custom/date-time-picker";
import StatusBadge from "@/components/custom/status-badge";
import DataTable, { type DataTableColumn } from "@/components/shared/data-table";
import EmptyState from "@/components/shared/empty-state";
import StatsCard from "@/components/shared/stats-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";

const FILA_SECTIONS: Array<{
  key: AnaliseSectionKey;
  title: string;
  description: string;
  emptyMessage: string;
}> = [
  {
    key: "ativos",
    title: "Ativos",
    description: "Cadastros ainda pendentes de saneamento documental ou sem documentação inicial.",
    emptyMessage: "Nenhum cadastro ativo pendente de ação.",
  },
  {
    key: "todos",
    title: "Todos",
    description: "Visão geral do backlog ainda em cadastro ou análise.",
    emptyMessage: "Nenhum cadastro disponível no backlog do analista.",
  },
  {
    key: "recebidos",
    title: "Recebidos",
    description: "Itens com documentação anexada e prontos para análise inicial.",
    emptyMessage: "Nenhum item recebido aguardando primeira análise.",
  },
  {
    key: "recebida",
    title: "Recebida",
    description: "Itens já assumidos e em andamento pelo analista.",
    emptyMessage: "Nenhum item em andamento no momento.",
  },
  {
    key: "reenvio",
    title: "Reenvio",
    description: "Itens que já voltaram do agente após correção e pedem nova validação.",
    emptyMessage: "Nenhum reenvio aguardando validação.",
  },
  {
    key: "incompleta",
    title: "Incompleta",
    description: "Pendências documentais ainda abertas para acompanhamento.",
    emptyMessage: "Nenhuma documentação incompleta aberta.",
  },
  {
    key: "pendente",
    title: "Pendente",
    description: "Cadastros sem documentação anexada nem reenvio registrado.",
    emptyMessage: "Nenhum cadastro pendente de documentos.",
  },
];

type DialogState =
  | { mode: "assumir"; item: EsteiraItem }
  | { mode: "aprovar"; item: EsteiraItem }
  | { mode: "documentos"; item: EsteiraItem }
  | { mode: "correcao"; item: EsteiraItem }
  | { mode: "ajuste-pagamento"; item: AnalisePagamentoItem }
  | { mode: "excluir-pagamento"; item: AnalisePagamentoItem }
  | { mode: "editar-nome"; item: AnaliseDadosItem }
  | null;

function getInitialSectionPages() {
  return FILA_SECTIONS.reduce<Record<AnaliseSectionKey, number>>(
    (accumulator, section) => ({
      ...accumulator,
      [section.key]: 1,
    }),
    {
      ativos: 1,
      todos: 1,
      recebidos: 1,
      recebida: 1,
      reenvio: 1,
      incompleta: 1,
      pendente: 1,
    },
  );
}

function toDatetimeLocalValue(value?: string | null) {
  const date = value ? new Date(value) : new Date();
  if (Number.isNaN(date.getTime())) return "";
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  return `${year}-${month}-${day}T${hours}:${minutes}`;
}

function getTotalPages(count: number | undefined, pageSize: string) {
  return Math.max(1, Math.ceil((count ?? 0) / Number(pageSize)));
}

export default function AnalisePage() {
  const queryClient = useQueryClient();
  const { hasAnyRole, status } = usePermissions();
  const isAnalistaEnabled = hasAnyRole(["ANALISTA", "ADMIN"]);
  const [search, setSearch] = React.useState("");
  const [pageSize, setPageSize] = React.useState("5");
  const [competencia, setCompetencia] = React.useState(() => {
    const now = new Date();
    const month = String(now.getMonth() + 1).padStart(2, "0");
    return `${now.getFullYear()}-${month}`;
  });
  const [filaPages, setFilaPages] = React.useState<Record<AnaliseSectionKey, number>>(
    getInitialSectionPages,
  );
  const [ajustesPage, setAjustesPage] = React.useState(1);
  const [margemPage, setMargemPage] = React.useState(1);
  const [dadosPage, setDadosPage] = React.useState(1);
  const [dialogState, setDialogState] = React.useState<DialogState>(null);
  const [observacao, setObservacao] = React.useState("");
  const [newPaymentDate, setNewPaymentDate] = React.useState("");
  const [nomeCompleto, setNomeCompleto] = React.useState("");
  const debouncedSearch = useDebouncedValue(search, 300);
  const documentoItemId = dialogState?.mode === "documentos" ? dialogState.item.id : null;

  const resetPages = React.useCallback(() => {
    setFilaPages(getInitialSectionPages());
    setAjustesPage(1);
    setMargemPage(1);
    setDadosPage(1);
  }, []);

  const invalidateAnaliseQueries = React.useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ["analise-resumo"] });
    void queryClient.invalidateQueries({ queryKey: ["analise-filas"] });
    void queryClient.invalidateQueries({ queryKey: ["analise-ajustes"] });
    void queryClient.invalidateQueries({ queryKey: ["analise-margem"] });
    void queryClient.invalidateQueries({ queryKey: ["analise-dados"] });
    void queryClient.invalidateQueries({ queryKey: ["esteira"] });
    void queryClient.invalidateQueries({ queryKey: ["esteira-detalhe"] });
    void queryClient.invalidateQueries({ queryKey: ["dashboard-esteira"] });
  }, [queryClient]);

  const summaryQuery = useQuery({
    queryKey: ["analise-resumo", debouncedSearch, competencia],
    queryFn: () =>
      apiFetch<AnaliseResumo>("analise", {
        query: {
          search: debouncedSearch,
          competencia,
        },
      }),
    enabled: isAnalistaEnabled,
  });

  const filaQueries = useQueries({
    queries: FILA_SECTIONS.map((section) => ({
      queryKey: [
        "analise-filas",
        section.key,
        filaPages[section.key],
        pageSize,
        debouncedSearch,
      ],
      queryFn: () =>
        apiFetch<PaginatedMetaResponse<EsteiraItem, { secao: AnaliseSectionKey }>>(
          "analise/filas",
          {
            query: {
              secao: section.key,
              page: filaPages[section.key],
              page_size: Number(pageSize),
              search: debouncedSearch,
            },
          },
        ),
      enabled: isAnalistaEnabled,
    })),
  }) as Array<
    UseQueryResult<PaginatedMetaResponse<EsteiraItem, { secao: AnaliseSectionKey }>, Error>
  >;

  const ajustesQuery = useQuery({
    queryKey: ["analise-ajustes", ajustesPage, pageSize, debouncedSearch, competencia],
    queryFn: () =>
      apiFetch<
        PaginatedMetaResponse<
          AnalisePagamentoItem,
          {
            competencia: {
              mes: string;
              inicio: string;
              fim: string;
              intervalo_label: string;
            };
          }
        >
      >("analise/ajustes", {
        query: {
          page: ajustesPage,
          page_size: Number(pageSize),
          search: debouncedSearch,
          competencia,
        },
      }),
    enabled: isAnalistaEnabled,
  });

  const margemQuery = useQuery({
    queryKey: ["analise-margem", margemPage, pageSize, debouncedSearch, competencia],
    queryFn: () =>
      apiFetch<PaginatedMetaResponse<AnaliseMargemItem, AnaliseMargemMeta>>(
        "analise/margem",
        {
          query: {
            page: margemPage,
            page_size: Number(pageSize),
            search: debouncedSearch,
            competencia,
          },
        },
      ),
    enabled: isAnalistaEnabled,
  });

  const dadosQuery = useQuery({
    queryKey: ["analise-dados", dadosPage, pageSize, debouncedSearch],
    queryFn: () =>
      apiFetch<PaginatedResponse<AnaliseDadosItem>>("analise/dados", {
        query: {
          page: dadosPage,
          page_size: Number(pageSize),
          search: debouncedSearch,
        },
      }),
    enabled: isAnalistaEnabled,
  });

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
      action: "assumir" | "aprovar" | "validar-documento" | "solicitar-correcao";
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
        void queryClient.invalidateQueries({ queryKey: ["tesouraria-contratos"] });
        void queryClient.invalidateQueries({ queryKey: ["dashboard-tesouraria"] });
      }
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Falha ao executar ação.");
    },
  });

  const paymentDateMutation = useMutation({
    mutationFn: async (item: AnalisePagamentoItem) => {
      await apiFetch(`analise/ajustes/${item.id}/data-pagamento`, {
        method: "PATCH",
        body: { new_date: newPaymentDate },
      });
    },
    onSuccess: () => {
      toast.success("Data do pagamento atualizada.");
      setDialogState(null);
      setNewPaymentDate("");
      invalidateAnaliseQueries();
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Falha ao atualizar o pagamento.");
    },
  });

  const deletePaymentMutation = useMutation({
    mutationFn: async (item: AnalisePagamentoItem) => {
      await apiFetch(`analise/ajustes/${item.id}`, {
        method: "DELETE",
      });
    },
    onSuccess: () => {
      toast.success("Ajuste excluído com sucesso.");
      setDialogState(null);
      invalidateAnaliseQueries();
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Falha ao excluir o ajuste.");
    },
  });

  const renameMutation = useMutation({
    mutationFn: async (item: AnaliseDadosItem) => {
      await apiFetch(`analise/dados/${item.id}/nome`, {
        method: "PATCH",
        body: { nome_completo: nomeCompleto },
      });
    },
    onSuccess: () => {
      toast.success("Nome atualizado com sucesso.");
      setDialogState(null);
      setNomeCompleto("");
      invalidateAnaliseQueries();
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Falha ao atualizar o nome.");
    },
  });

  const filaColumns = React.useMemo<DataTableColumn<EsteiraItem>[]>(
    () => [
      {
        id: "assumir",
        header: "Assumir",
        cell: (row) =>
          row.acoes_disponiveis.includes("assumir") ? (
            <Button size="sm" onClick={() => setDialogState({ mode: "assumir", item: row })}>
              Assumir
            </Button>
          ) : (
            "-"
          ),
      },
      {
        id: "codigo",
        header: "Contrato",
        cell: (row) => (
          <div className="space-y-1">
            <p className="font-medium text-foreground">{row.contrato?.codigo ?? "-"}</p>
            <p className="text-xs text-muted-foreground">{row.contrato?.associado_nome ?? "-"}</p>
          </div>
        ),
      },
      {
        id: "cpf",
        header: "CPF / Matrícula",
        cell: (row) => (
          <div className="text-sm">
            <p>{row.contrato?.cpf_cnpj ?? "-"}</p>
            <p className="text-muted-foreground">{row.contrato?.matricula ?? "-"}</p>
          </div>
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
        id: "documentos",
        header: "Docs",
        cell: (row) => (
          <Button
            variant="outline"
            size="sm"
            onClick={() => setDialogState({ mode: "documentos", item: row })}
          >
            <FileTextIcon className="size-4" />
            Ver ({row.documentos_count})
          </Button>
        ),
      },
      {
        id: "acoes",
        header: "Ações",
        cell: (row) => (
          <div className="flex flex-wrap gap-2">
            {row.status_documentacao === "reenvio_pendente" ? (
              <Button
                size="sm"
                variant="outline"
                onClick={() => actionMutation.mutate({ item: row, action: "validar-documento" })}
              >
                Validar revisto
              </Button>
            ) : null}
            {row.acoes_disponiveis.includes("aprovar") ? (
              <Button size="sm" onClick={() => setDialogState({ mode: "aprovar", item: row })}>
                Aprovar
              </Button>
            ) : null}
            {row.acoes_disponiveis.includes("solicitar_correcao") ? (
              <Button
                size="sm"
                variant="outline"
                onClick={() => setDialogState({ mode: "correcao", item: row })}
              >
                Solicitar correção
              </Button>
            ) : null}
          </div>
        ),
      },
    ],
    [actionMutation],
  );

  const ajustesColumns = React.useMemo<DataTableColumn<AnalisePagamentoItem>[]>(
    () => [
      {
        id: "associado",
        header: "Associado",
        cell: (row) => (
          <div className="space-y-1">
            <p className="font-medium text-foreground">{row.full_name}</p>
            <p className="text-xs text-muted-foreground">{row.contrato_codigo || row.cpf_cnpj}</p>
          </div>
        ),
      },
      {
        id: "agente",
        header: "Agente",
        cell: (row) => row.agente_responsavel || "-",
      },
      {
        id: "status",
        header: "Status",
        cell: (row) => <StatusBadge status={row.status} />,
      },
      {
        id: "valor",
        header: "Valor",
        cell: (row) => (
          <div className="space-y-1 text-sm">
            <p>{formatCurrency(row.valor_pago)}</p>
            <p className="text-muted-foreground">
              Antecipação: {formatCurrency(row.contrato_valor_antecipacao)}
            </p>
          </div>
        ),
      },
      {
        id: "referencia",
        header: "Referência",
        cell: (row) => formatDateTime(row.paid_at ?? row.referencia_at),
      },
      {
        id: "acoes",
        header: "Ações",
        cell: (row) => (
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                setNewPaymentDate(toDatetimeLocalValue(row.paid_at ?? row.referencia_at));
                setDialogState({ mode: "ajuste-pagamento", item: row });
              }}
            >
              <CalendarClockIcon className="size-4" />
              Ajustar data
            </Button>
            {row.status !== "pago" ? (
              <Button
                size="sm"
                variant="outline"
                onClick={() => setDialogState({ mode: "excluir-pagamento", item: row })}
              >
                <Trash2Icon className="size-4" />
                Excluir
              </Button>
            ) : null}
          </div>
        ),
      },
    ],
    [],
  );

  const margemColumns = React.useMemo<DataTableColumn<AnaliseMargemItem>[]>(
    () => [
      {
        id: "contrato",
        header: "Contrato",
        cell: (row) => (
          <div className="space-y-1">
            <p className="font-medium text-foreground">{row.codigo}</p>
            <p className="text-xs text-muted-foreground">{row.nome_completo}</p>
          </div>
        ),
      },
      {
        id: "agente",
        header: "Agente",
        cell: (row) => row.agente?.full_name ?? "-",
      },
      {
        id: "base",
        header: "Base",
        cell: (row) => (
          <div className="space-y-1 text-sm">
            <p>Bruto: {formatCurrency(row.valor_bruto)}</p>
            <p className="text-muted-foreground">Líquido: {formatCurrency(row.valor_liquido)}</p>
          </div>
        ),
      },
      {
        id: "mensalidade",
        header: "Mensalidade",
        cell: (row) => (
          <div className="space-y-1 text-sm">
            <p>{formatCurrency(row.valor_mensalidade)}</p>
            <p className="text-muted-foreground">{row.prazo_meses} meses</p>
          </div>
        ),
      },
      {
        id: "margem",
        header: "Margem",
        cell: (row) => (
          <div className="space-y-1 text-sm">
            <p>{formatCurrency(row.calc_margem)}</p>
            <p className="text-muted-foreground">30% bruto: {formatCurrency(row.calc_trinta_bruto)}</p>
          </div>
        ),
      },
      {
        id: "antecipacao",
        header: "Antecipação",
        cell: (row) => (
          <div className="space-y-1 text-sm">
            <p>{formatCurrency(row.calc_valor_antecipacao)}</p>
            <p className="text-muted-foreground">Doação: {formatCurrency(row.calc_doacao_fundo)}</p>
          </div>
        ),
      },
      {
        id: "status",
        header: "Status",
        cell: (row) => (
          <Badge variant="outline">{row.calc_pode_prosseguir ? "Pode prosseguir" : "Bloqueado"}</Badge>
        ),
      },
    ],
    [],
  );

  const dadosColumns = React.useMemo<DataTableColumn<AnaliseDadosItem>[]>(
    () => [
      {
        id: "nome",
        header: "Associado",
        cell: (row) => (
          <div className="space-y-1">
            <p className="font-medium text-foreground">{row.nome_completo}</p>
            <p className="text-xs text-muted-foreground">{row.contrato_codigo ?? row.matricula}</p>
          </div>
        ),
      },
      {
        id: "cpf",
        header: "CPF / Matrícula",
        cell: (row) => (
          <div className="space-y-1 text-sm">
            <p>{row.cpf_cnpj}</p>
            <p className="text-muted-foreground">{row.matricula}</p>
          </div>
        ),
      },
      {
        id: "agente",
        header: "Agente",
        cell: (row) => row.agente?.full_name ?? "-",
      },
      {
        id: "created_at",
        header: "Criado em",
        cell: (row) => formatDate(row.created_at),
      },
      {
        id: "acoes",
        header: "Ações",
        cell: (row) => (
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              setNomeCompleto(row.nome_completo);
              setDialogState({ mode: "editar-nome", item: row });
            }}
          >
            <PencilIcon className="size-4" />
            Editar nome
          </Button>
        ),
      },
    ],
    [],
  );

  if (status !== "authenticated") {
    return (
      <div className="flex min-h-[40vh] items-center justify-center gap-3 rounded-[1.75rem] border border-border/60 bg-card/60 px-6 py-8 text-sm text-muted-foreground">
        <Spinner />
        Carregando módulo de análise...
      </div>
    );
  }

  if (!isAnalistaEnabled) {
    return (
      <EmptyState
        title="Acesso não disponível"
        description="Este módulo está liberado apenas para perfis de analista ou administrador."
      />
    );
  }

  return (
    <div className="space-y-8">
      <section className="space-y-4">
        <div className="space-y-2">
          <p className="text-sm uppercase tracking-[0.2em] text-muted-foreground">Análise operacional</p>
          <h1 className="text-3xl font-semibold text-foreground">Dashboard único do analista</h1>
          <p className="max-w-4xl text-sm text-muted-foreground">
            O módulo do analista foi consolidado em uma única rota. As antigas subáreas agora
            aparecem em seções empilhadas, usando o fluxo atual da esteira e os dados legados de
            ajustes, margem e dados cadastrais.
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
          <CalendarCompetencia
            value={parseMonthValue(competencia)}
            onChange={(value) => {
              setCompetencia(`${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}`);
              resetPages();
            }}
            className="w-full xl:w-44"
          />
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
          <Button onClick={resetPages}>Filtrar</Button>
          <Button
            variant="outline"
            onClick={() => {
              setSearch("");
              resetPages();
            }}
          >
            Limpar
          </Button>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatsCard
          title="Ativos"
          value={String(summaryQuery.data?.filas.ativos ?? 0)}
          delta={`${summaryQuery.data?.filas.incompleta ?? 0} com pendência aberta`}
          tone="warning"
          icon={ShieldCheckIcon}
        />
        <StatsCard
          title="Recebidos"
          value={String(summaryQuery.data?.filas.recebidos ?? 0)}
          delta={`${summaryQuery.data?.filas.reenvio ?? 0} em reenvio`}
          tone="positive"
          icon={FileTextIcon}
        />
        <StatsCard
          title="Ajustes no período"
          value={String(summaryQuery.data?.ajustes.count ?? 0)}
          delta={formatCurrency(summaryQuery.data?.ajustes.total_pago)}
          tone="neutral"
          icon={WalletIcon}
        />
        <StatsCard
          title="Margem da competência"
          value={String(summaryQuery.data?.margem.count ?? 0)}
          delta={formatCurrency(summaryQuery.data?.margem.soma_antecipacao)}
          tone="neutral"
          icon={BarChart3Icon}
        />
      </section>

      <section className="space-y-6">
        {FILA_SECTIONS.map((section, index) => {
          const query = filaQueries[index];
          const count = summaryQuery.data?.filas[section.key] ?? query.data?.count ?? 0;

          return (
            <Card
              key={section.key}
              className="rounded-[1.75rem] border-border/60 bg-card/70 shadow-xl shadow-black/20"
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
                {query.isLoading ? (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Spinner />
                    Carregando seção {section.title.toLowerCase()}...
                  </div>
                ) : (
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
                  />
                )}
              </CardContent>
            </Card>
          );
        })}
      </section>

      <section className="space-y-6">
        <Card className="rounded-[1.75rem] border-border/60 bg-card/70 shadow-xl shadow-black/20">
          <CardHeader>
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <CardTitle>Ajustes de pagamentos</CardTitle>
                <CardDescription>
                  Competência 06→05. {ajustesQuery.data?.meta.competencia.intervalo_label ?? ""}
                </CardDescription>
              </div>
              <Badge variant="outline">{summaryQuery.data?.ajustes.count ?? ajustesQuery.data?.count ?? 0} registros</Badge>
            </div>
          </CardHeader>
          <CardContent>
            {ajustesQuery.isLoading ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Spinner />
                Carregando ajustes de pagamentos...
              </div>
            ) : (
              <DataTable
                data={ajustesQuery.data?.results ?? []}
                columns={ajustesColumns}
                currentPage={ajustesPage}
                totalPages={getTotalPages(ajustesQuery.data?.count, pageSize)}
                onPageChange={setAjustesPage}
                emptyMessage="Nenhum ajuste encontrado para a competência selecionada."
              />
            )}
          </CardContent>
        </Card>

        <Card className="rounded-[1.75rem] border-border/60 bg-card/70 shadow-xl shadow-black/20">
          <CardHeader>
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <CardTitle>Margem da competência</CardTitle>
                <CardDescription>
                  Cálculo 30% bruto, margem líquida, antecipação e doação, consolidado pela
                  janela 06→05.
                </CardDescription>
              </div>
              <Badge variant="outline">
                {formatCurrency(margemQuery.data?.meta.totais.soma_margem ?? summaryQuery.data?.margem.soma_margem)}
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            {margemQuery.isLoading ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Spinner />
                Carregando cálculo de margem...
              </div>
            ) : (
              <DataTable
                data={margemQuery.data?.results ?? []}
                columns={margemColumns}
                currentPage={margemPage}
                totalPages={getTotalPages(margemQuery.data?.count, pageSize)}
                onPageChange={setMargemPage}
                emptyMessage="Nenhum contrato encontrado para a competência informada."
              />
            )}
          </CardContent>
        </Card>

        <Card className="rounded-[1.75rem] border-border/60 bg-card/70 shadow-xl shadow-black/20">
          <CardHeader>
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <CardTitle>Ajuste de dados</CardTitle>
                <CardDescription>
                  Correção rápida de nome no cadastro, mantendo o restante do fluxo intacto.
                </CardDescription>
              </div>
              <Badge variant="outline">{summaryQuery.data?.dados.count ?? dadosQuery.data?.count ?? 0} cadastros</Badge>
            </div>
          </CardHeader>
          <CardContent>
            {dadosQuery.isLoading ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Spinner />
                Carregando base de ajuste de dados...
              </div>
            ) : (
              <DataTable
                data={dadosQuery.data?.results ?? []}
                columns={dadosColumns}
                currentPage={dadosPage}
                totalPages={getTotalPages(dadosQuery.data?.count, pageSize)}
                onPageChange={setDadosPage}
                emptyMessage="Nenhum cadastro encontrado para ajuste de dados."
              />
            )}
          </CardContent>
        </Card>
      </section>

      <Dialog
        open={!!dialogState}
        onOpenChange={(open) => {
          if (open) return;
          setDialogState(null);
          setObservacao("");
          setNewPaymentDate("");
          setNomeCompleto("");
        }}
      >
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>
              {dialogState?.mode === "assumir"
                ? "Assumir análise"
                : dialogState?.mode === "aprovar"
                  ? "Confirmar aprovação"
                  : dialogState?.mode === "correcao"
                    ? "Solicitar correção"
                    : dialogState?.mode === "documentos"
                      ? "Documentos e formulário"
                      : dialogState?.mode === "ajuste-pagamento"
                        ? "Ajustar data do pagamento"
                        : dialogState?.mode === "excluir-pagamento"
                          ? "Excluir ajuste"
                          : "Editar nome do associado"}
            </DialogTitle>
            <DialogDescription>
              {dialogState?.mode === "assumir"
                ? `Deseja assumir a análise do contrato ${dialogState.item.contrato?.codigo}?`
                : dialogState?.mode === "aprovar"
                  ? `Confirme a aprovação do contrato ${dialogState.item.contrato?.codigo} para a próxima etapa da esteira.`
                  : dialogState?.mode === "correcao"
                    ? "Informe a observação que deve ser enviada ao agente."
                    : dialogState?.mode === "documentos"
                      ? "Documentos anexados e informações do item em análise."
                      : dialogState?.mode === "ajuste-pagamento"
                        ? "Atualize a data/hora do pagamento para corrigir a competência."
                        : dialogState?.mode === "excluir-pagamento"
                          ? "Essa exclusão afeta apenas o ajuste legado de pagamento e não remove o cadastro."
                          : "Altere o nome completo e salve a correção diretamente pelo módulo do analista."}
            </DialogDescription>
          </DialogHeader>

          {dialogState?.mode === "documentos" ? (
            detalheQuery.isLoading ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Spinner />
                Carregando documentos...
              </div>
            ) : (
              <div className="space-y-4">
                <div className="grid gap-3 md:grid-cols-2">
                  {detalheQuery.data?.documentos?.length ? (
                    detalheQuery.data.documentos.map((documento) => (
                      <div key={documento.id} className="rounded-2xl border border-border/60 bg-card/60 p-4">
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                          <div className="space-y-2">
                            <p className="font-medium capitalize">{documento.tipo.replaceAll("_", " ")}</p>
                            <StatusBadge status={documento.status} />
                          </div>
                          {documento.arquivo ? (
                            <Button asChild size="sm" variant="outline">
                              <a href={buildBackendFileUrl(documento.arquivo)} target="_blank" rel="noreferrer">
                                <ExternalLinkIcon className="size-4" />
                                Ver documento
                              </a>
                            </Button>
                          ) : (
                            <p className="text-sm text-muted-foreground">Arquivo indisponível.</p>
                          )}
                        </div>
                      </div>
                    ))
                  ) : (
                    <p className="text-sm text-muted-foreground">Nenhum documento anexado.</p>
                  )}
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

          {dialogState?.mode === "ajuste-pagamento" ? (
            <DateTimePicker
              value={newPaymentDate}
              onChange={setNewPaymentDate}
            />
          ) : null}

          {dialogState?.mode === "editar-nome" ? (
            <Input value={nomeCompleto} onChange={(event) => setNomeCompleto(event.target.value)} />
          ) : null}

          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogState(null)}>
              Cancelar
            </Button>
            {dialogState?.mode === "assumir" ? (
              <Button onClick={() => actionMutation.mutate({ item: dialogState.item, action: "assumir" })}>
                Confirmar
              </Button>
            ) : null}
            {dialogState?.mode === "aprovar" ? (
              <Button onClick={() => actionMutation.mutate({ item: dialogState.item, action: "aprovar" })}>
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
            {dialogState?.mode === "ajuste-pagamento" ? (
              <Button onClick={() => paymentDateMutation.mutate(dialogState.item)}>
                Salvar nova data
              </Button>
            ) : null}
            {dialogState?.mode === "excluir-pagamento" ? (
              <Button variant="destructive" onClick={() => deletePaymentMutation.mutate(dialogState.item)}>
                Excluir ajuste
              </Button>
            ) : null}
            {dialogState?.mode === "editar-nome" ? (
              <Button onClick={() => renameMutation.mutate(dialogState.item)}>Salvar nome</Button>
            ) : null}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
