"use client";

import * as React from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BadgeCheckIcon,
  BriefcaseBusinessIcon,
  HandCoinsIcon,
  PaperclipIcon,
} from "lucide-react";

import type {
  PagamentoAgenteNotificacoes,
  PaginatedPagamentosAgenteResponse,
  PagamentoAgenteItem,
  PagamentoAgenteResumo,
} from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import { buildBackendFileUrl } from "@/lib/backend-files";
import { parseMonthValue } from "@/lib/date-value";
import { formatCurrency, formatDate, formatDateTime, formatMonthYear } from "@/lib/formatters";
import { maskCPFCNPJ } from "@/lib/masks";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import CalendarCompetencia from "@/components/custom/calendar-competencia";
import StatusBadge from "@/components/custom/status-badge";
import DataTable, { type DataTableColumn } from "@/components/shared/data-table";
import { MetricCardSkeleton } from "@/components/shared/page-skeletons";
import StatsCard from "@/components/shared/stats-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const EMPTY_RESUMO: PagamentoAgenteResumo = {
  total: 0,
  efetivados: 0,
  com_anexos: 0,
  parcelas_pagas: 0,
  parcelas_total: 0,
};

function resolveCount(value?: number | null) {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

const STATUS_OPTIONS = [
  { value: "todos", label: "Todos status" },
  { value: "ativo", label: "Ativo" },
  { value: "em_analise", label: "Em análise" },
  { value: "encerrado", label: "Encerrado" },
  { value: "cancelado", label: "Cancelado" },
];

function ComprovanteChip({
  comprovante,
}: {
  comprovante: {
    id: string;
    nome: string;
    url: string;
    arquivo_referencia: string;
    arquivo_disponivel_localmente: boolean;
    tipo_referencia: string;
    origem: string;
    papel: string;
  };
}) {
  const label =
    resolvePapelLabel(comprovante.papel) ||
    resolveComprovanteLabel(comprovante.nome, comprovante.origem);
  const description = comprovante.arquivo_referencia || comprovante.nome;

  if (comprovante.arquivo_disponivel_localmente && comprovante.url) {
    return (
      <Button size="sm" variant="outline" asChild>
        <a href={buildBackendFileUrl(comprovante.url)} target="_blank" rel="noreferrer">
          {label}
        </a>
      </Button>
    );
  }

  return (
    <div className="rounded-2xl border border-dashed border-border/60 bg-background/40 px-3 py-2">
      <p className="text-sm font-medium">{label}</p>
      <p className="mt-1 max-w-[22rem] truncate text-xs text-muted-foreground">{description}</p>
      <p className="mt-1 text-[11px] text-amber-200">
        {resolveReferenceLabel(comprovante.tipo_referencia)}
      </p>
    </div>
  );
}

export default function MeusPagamentosPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = React.useState("");
  const [status, setStatus] = React.useState("todos");
  const [mes, setMes] = React.useState("");
  const [pageSize, setPageSize] = React.useState("15");
  const [page, setPage] = React.useState(1);
  const debouncedSearch = useDebouncedValue(search, 300);
  const markedUnreadCountRef = React.useRef(0);

  const query = useQuery({
    queryKey: ["agente-pagamentos", page, pageSize, debouncedSearch, status, mes],
    queryFn: () =>
      apiFetch<PaginatedPagamentosAgenteResponse>("agente/pagamentos", {
        query: {
          page,
          page_size: Number(pageSize),
          search: debouncedSearch || undefined,
          status: status === "todos" ? undefined : status,
          mes: mes || undefined,
        },
      }),
  });
  const notificacoesQuery = useQuery({
    queryKey: ["agente-pagamentos-notificacoes"],
    queryFn: () =>
      apiFetch<PagamentoAgenteNotificacoes>("agente/pagamentos/notificacoes"),
  });

  React.useEffect(() => {
    const unreadCount = notificacoesQuery.data?.unread_count ?? 0;
    if (!unreadCount || unreadCount === markedUnreadCountRef.current) {
      if (!unreadCount) {
        markedUnreadCountRef.current = 0;
      }
      return;
    }

    markedUnreadCountRef.current = unreadCount;
    void apiFetch<{ marked_count: number }>(
      "agente/pagamentos/notificacoes/marcar-lidas",
      { method: "POST" },
    ).then(() => {
      void queryClient.invalidateQueries({
        queryKey: ["agente-pagamentos-notificacoes"],
      });
    });
  }, [notificacoesQuery.data?.unread_count, queryClient]);

  const rows = query.data?.results ?? [];
  const resumo: PagamentoAgenteResumo = {
    total: resolveCount(query.data?.resumo?.total ?? EMPTY_RESUMO.total),
    efetivados: resolveCount(query.data?.resumo?.efetivados ?? EMPTY_RESUMO.efetivados),
    com_anexos: resolveCount(query.data?.resumo?.com_anexos ?? EMPTY_RESUMO.com_anexos),
    parcelas_pagas: resolveCount(query.data?.resumo?.parcelas_pagas ?? EMPTY_RESUMO.parcelas_pagas),
    parcelas_total: resolveCount(query.data?.resumo?.parcelas_total ?? EMPTY_RESUMO.parcelas_total),
  };
  const totalPages = Math.max(1, Math.ceil((query.data?.count ?? 0) / Number(pageSize)));

  const columns = React.useMemo<DataTableColumn<PagamentoAgenteItem>[]>(
    () => [
      {
        id: "associado",
        header: "Associado",
        cell: (row) => (
          <div className="space-y-1">
            <p className="font-medium">{row.nome}</p>
            <p className="font-mono text-xs text-muted-foreground">
              {maskCPFCNPJ(row.cpf_cnpj)}
            </p>
            <p className="text-xs text-muted-foreground">Clique na linha para ver anexos e ciclos.</p>
          </div>
        ),
      },
      {
        id: "contrato",
        header: "Contrato",
        cell: (row) => (
          <div className="space-y-1">
            <p className="font-mono text-xs">{row.contrato_codigo}</p>
            <p className="text-xs text-muted-foreground">
              Assinado em {formatDate(row.data_contrato)}
            </p>
          </div>
        ),
      },
      {
        id: "status",
        header: "Status",
        cell: (row) => (
          <div className="space-y-1">
            <StatusBadge
              status={row.status_visual_slug}
              label={row.status_visual_label}
            />
            {row.possui_meses_nao_descontados ? (
              <p className="text-xs text-amber-200">
                {row.meses_nao_descontados_count} mês(es) não descontado(s)
              </p>
            ) : null}
          </div>
        ),
      },
      {
        id: "pagamento_inicial",
        header: "Pagamento inicial",
        cell: (row) => (
          <div className="space-y-2">
            <StatusBadge
              status={row.pagamento_inicial_status}
              label={row.pagamento_inicial_status_label}
            />
            <p className="text-xs text-muted-foreground">
              {row.pagamento_inicial_paid_at
                ? formatDateTime(row.pagamento_inicial_paid_at)
                : "Aguardando tesouraria"}
            </p>
          </div>
        ),
      },
      {
        id: "valor_pago",
        header: "Valor pago",
        cell: (row) => (
          <div className="space-y-1">
            <p className="font-medium">
              {row.pagamento_inicial_valor
                ? formatCurrency(row.pagamento_inicial_valor)
                : "—"}
            </p>
            <p className="text-xs text-emerald-400">
              Comissão {formatCurrency(row.comissao_agente)}
            </p>
          </div>
        ),
      },
      {
        id: "parcelas",
        header: "Parcelas",
        cell: (row) => (
          <div className="space-y-1">
            <p className="font-medium">
              {row.parcelas_pagas}/{row.parcelas_total}
            </p>
            <p className="text-xs text-muted-foreground">Parcelas pagas no recorte</p>
          </div>
        ),
      },
      {
        id: "anexos",
        header: "Efetivação",
        cell: (row) => (
          <div className="space-y-1">
            <Badge className="rounded-full bg-sky-500/15 text-sky-200">
              {row.pagamento_inicial_evidencias.length} evidência(s)
            </Badge>
            <p className="text-xs text-muted-foreground">
              {row.auxilio_liberado_em
                ? `Liberado em ${formatDate(row.auxilio_liberado_em)}`
                : "Aguardando efetivação"}
            </p>
          </div>
        ),
      },
    ],
    [],
  );

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {query.isLoading && !query.data ? (
          Array.from({ length: 4 }).map((_, index) => <MetricCardSkeleton key={index} />)
        ) : (
          <>
            <StatsCard
              title="Contratos com repasse"
              value={resolveCount(resumo.total).toLocaleString("pt-BR")}
              delta={`${resolveCount(resumo.efetivados).toLocaleString("pt-BR")} efetivados no recorte`}
              icon={BriefcaseBusinessIcon}
              tone="neutral"
            />
            <StatsCard
              title="Efetivados"
              value={resolveCount(resumo.efetivados).toLocaleString("pt-BR")}
              delta="Pagamentos iniciais já confirmados"
              icon={BadgeCheckIcon}
              tone="positive"
            />
            <StatsCard
              title="Com anexos"
              value={resolveCount(resumo.com_anexos).toLocaleString("pt-BR")}
              delta="Contratos com evidência disponível"
              icon={PaperclipIcon}
              tone="neutral"
            />
            <StatsCard
              title="Parcelas pagas"
              value={`${resolveCount(resumo.parcelas_pagas).toLocaleString("pt-BR")}/${resolveCount(resumo.parcelas_total).toLocaleString("pt-BR")}`}
              delta={`${Math.max(resolveCount(resumo.parcelas_total) - resolveCount(resumo.parcelas_pagas), 0).toLocaleString("pt-BR")} ainda pendentes`}
              icon={HandCoinsIcon}
              tone="positive"
            />
          </>
        )}
      </section>

      <section className="grid gap-3 rounded-[1.75rem] border border-border/60 bg-card/50 p-4 xl:grid-cols-[minmax(0,1fr)_180px_160px_160px_auto_auto]">
        <Input
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
            setPage(1);
          }}
          placeholder="Nome, CPF, matrícula ou código do contrato..."
          className="rounded-2xl border-border/60 bg-card/60"
        />
        <Select
          value={status}
          onValueChange={(value) => {
            setStatus(value);
            setPage(1);
          }}
        >
          <SelectTrigger className="rounded-2xl bg-card/60">
            <SelectValue placeholder="Todos status" />
          </SelectTrigger>
          <SelectContent>
            {STATUS_OPTIONS.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <CalendarCompetencia
          value={parseMonthValue(mes)}
          onChange={(value) => {
            setMes(`${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}`);
            setPage(1);
          }}
          className="rounded-2xl"
        />
        <Select
          value={pageSize}
          onValueChange={(value) => {
            setPageSize(value);
            setPage(1);
          }}
        >
          <SelectTrigger className="rounded-2xl bg-card/60">
            <SelectValue placeholder="15" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="15">15 / página</SelectItem>
            <SelectItem value="30">30 / página</SelectItem>
            <SelectItem value="50">50 / página</SelectItem>
          </SelectContent>
        </Select>
        <Button onClick={() => setPage(1)}>Aplicar</Button>
        <Button
          variant="outline"
          onClick={() => {
            setSearch("");
            setStatus("todos");
            setMes("");
            setPageSize("15");
            setPage(1);
          }}
        >
          Limpar
        </Button>
      </section>

      {query.isError ? (
        <div className="rounded-[1.75rem] border border-destructive/40 bg-destructive/10 px-6 py-5 text-sm text-destructive">
          {query.error instanceof Error
            ? query.error.message
            : "Falha ao carregar pagamentos do agente."}
        </div>
      ) : (
        <DataTable
          data={rows}
          columns={columns}
          renderExpanded={(row) => <PagamentoExpandido row={row} />}
          currentPage={page}
          totalPages={totalPages}
          onPageChange={setPage}
          emptyMessage="Nenhum contrato encontrado para os filtros informados."
          loading={query.isLoading}
          skeletonRows={6}
        />
      )}
    </div>
  );
}

function PagamentoExpandido({ row }: { row: PagamentoAgenteItem }) {
  return (
    <div className="space-y-5">
      <section className="grid gap-4 md:grid-cols-3">
        <InfoCard label="Contrato" value={row.contrato_codigo} />
        <InfoCard label="Mensalidade" value={formatCurrency(row.valor_mensalidade)} />
        <InfoCard
          label="Liberação"
          value={row.auxilio_liberado_em ? formatDate(row.auxilio_liberado_em) : "Pendente"}
        />
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        <InfoCard label="Pagamento inicial" value={row.pagamento_inicial_status_label} />
        <InfoCard
          label="Valor pago"
          value={
            row.pagamento_inicial_valor
              ? formatCurrency(row.pagamento_inicial_valor)
              : "Não informado"
          }
        />
        <InfoCard
          label="Recebido em"
          value={
            row.pagamento_inicial_paid_at
              ? formatDateTime(row.pagamento_inicial_paid_at)
              : "Aguardando tesouraria"
          }
        />
      </section>

      <Card className="rounded-[1.5rem] border-border/60 bg-background/50">
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Pagamento inicial da efetivação</CardTitle>
        </CardHeader>
        <CardContent>
          {row.pagamento_inicial_evidencias.length ? (
            <div className="flex flex-wrap gap-2">
              {row.pagamento_inicial_evidencias.map((comprovante) => (
                <ComprovanteChip key={comprovante.id} comprovante={comprovante} />
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              Nenhuma evidência de pagamento inicial disponível.
            </p>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4 xl:grid-cols-2">
        {row.ciclos.length ? (
          row.ciclos.map((ciclo) => (
            <Card key={ciclo.id} className="rounded-[1.5rem] border-border/60 bg-background/50">
              <CardHeader className="pb-3">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <CardTitle className="text-base">Ciclo {ciclo.numero}</CardTitle>
                  <StatusBadge
                    status={ciclo.status_visual_slug}
                    label={ciclo.status_visual_label}
                  />
                </div>
                <p className="text-sm text-muted-foreground">
                  {formatMonthYear(ciclo.data_inicio)} até {formatMonthYear(ciclo.data_fim)}
                </p>
              </CardHeader>
              <CardContent className="space-y-3">
                {ciclo.parcelas.length ? (
                  ciclo.parcelas.map((parcela) => (
                    <div
                      key={parcela.id}
                      className="rounded-2xl border border-border/60 bg-card/60 p-4"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <p className="font-medium">
                            Parcela {parcela.numero} · {formatMonthYear(parcela.referencia_mes)}
                          </p>
                          <p className="text-sm text-muted-foreground">
                            {formatCurrency(parcela.valor)} · vencimento {formatDate(parcela.data_vencimento)}
                          </p>
                        </div>
                        <StatusBadge status={parcela.status} />
                      </div>

                      <div className="mt-3 flex flex-wrap gap-2">
                        {parcela.comprovantes.length ? (
                          parcela.comprovantes.map((comprovante) => (
                            <ComprovanteChip key={comprovante.id} comprovante={comprovante} />
                          ))
                        ) : (
                          <span className="text-sm text-muted-foreground">
                            Sem comprovante anexado para esta parcela.
                          </span>
                        )}
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-muted-foreground">
                    Nenhuma parcela encontrada para o filtro selecionado.
                  </p>
                )}
              </CardContent>
            </Card>
          ))
        ) : (
          <Card className="rounded-[1.5rem] border-border/60 bg-background/50">
            <CardContent className="p-6 text-sm text-muted-foreground">
              Nenhum ciclo encontrado para este contrato.
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}

function resolveComprovanteLabel(nome: string, origem: string) {
  if (origem === "arquivo_retorno") {
    return "Arquivo retorno";
  }
  if (origem === "relatorio_competencia") {
    return "Relatório mensal";
  }
  if (origem === "manual") {
    return nome || "Comprovante manual";
  }
  if (origem === "baixa_manual") {
    return "Baixa manual";
  }
  return nome || "Abrir comprovante";
}

function resolvePapelLabel(papel: string) {
  if (papel === "associado") {
    return "Comprovante associada";
  }
  if (papel === "agente") {
    return "Comprovante agente";
  }
  return "";
}

function resolveReferenceLabel(tipoReferencia: string) {
  if (tipoReferencia === "relatorio_competencia") {
    return "Relatório mensal da competência";
  }
  if (tipoReferencia === "placeholder_recebido") {
    return "Pagamento recebido e aguardando acervo";
  }
  if (tipoReferencia === "legado_sem_arquivo") {
    return "Referência de arquivo legado";
  }
  if (tipoReferencia === "sem_arquivo") {
    return "Sem arquivo individual";
  }
  return "Referência de arquivo";
}

function InfoCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border/60 bg-background/50 p-4">
      <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">{label}</p>
      <p className="mt-2 text-sm font-medium">{value}</p>
    </div>
  );
}
