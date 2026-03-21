"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  BadgeCheckIcon,
  HandCoinsIcon,
  PaperclipIcon,
  RefreshCcwIcon,
  WalletIcon,
} from "lucide-react";

import type {
  ContratoListItem,
  PaginatedResponse,
  RefinanciamentoItem,
  RefinanciamentoResumo,
} from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import { buildBackendFileUrl } from "@/lib/backend-files";
import {
  formatCurrency,
  formatDateTime,
  formatMonthYear,
} from "@/lib/formatters";
import { maskCPFCNPJ } from "@/lib/masks";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import StatusBadge from "@/components/custom/status-badge";
import DataTable, { type DataTableColumn } from "@/components/shared/data-table";
import { MetricCardSkeleton } from "@/components/shared/page-skeletons";
import StatsCard from "@/components/shared/stats-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

type RefinanciadosTab = "efetivados" | "aptos";

const FINAL_STATUS_OPTIONS = [
  { value: "todos", label: "Todos finalizados" },
  { value: "efetivado", label: "Efetivados" },
  { value: "concluido", label: "Concluídos" },
];

const EMPTY_RESUMO: RefinanciamentoResumo = {
  total: 0,
  em_analise: 0,
  assumidos: 0,
  aprovados: 0,
  efetivados: 0,
  concluidos: 0,
  bloqueados: 0,
  revertidos: 0,
  em_fluxo: 0,
  com_anexo_agente: 0,
  repasse_total: "0.00",
};

export default function AgenteRefinanciadosPage() {
  const [tab, setTab] = React.useState<RefinanciadosTab>("efetivados");
  const [search, setSearch] = React.useState("");
  const [finalStatus, setFinalStatus] = React.useState("todos");
  const [cycleKey, setCycleKey] = React.useState("");
  const [pageSize, setPageSize] = React.useState("15");
  const [page, setPage] = React.useState(1);
  const debouncedSearch = useDebouncedValue(search, 300);

  const resolvedFinalStatus =
    finalStatus === "todos" ? "efetivado,concluido" : finalStatus;

  const refinanciamentosQuery = useQuery({
    queryKey: [
      "agente-refinanciados-finalizados",
      debouncedSearch,
      resolvedFinalStatus,
      cycleKey,
      pageSize,
      page,
    ],
    enabled: tab === "efetivados",
    queryFn: () =>
      apiFetch<PaginatedResponse<RefinanciamentoItem>>("refinanciamentos", {
        query: {
          page,
          page_size: Number(pageSize),
          search: debouncedSearch || undefined,
          status: resolvedFinalStatus,
          cycle_key: cycleKey || undefined,
        },
      }),
  });

  const resumoQuery = useQuery({
    queryKey: [
      "agente-refinanciados-finalizados-resumo",
      debouncedSearch,
      resolvedFinalStatus,
      cycleKey,
    ],
    enabled: tab === "efetivados",
    queryFn: () =>
      apiFetch<RefinanciamentoResumo>("refinanciamentos/resumo", {
        query: {
          search: debouncedSearch || undefined,
          status: resolvedFinalStatus,
          cycle_key: cycleKey || undefined,
        },
      }),
  });

  const aptosQuery = useQuery({
    queryKey: ["agente-refinanciados-aptos", debouncedSearch, pageSize, page],
    enabled: tab === "aptos",
    queryFn: () =>
      apiFetch<PaginatedResponse<ContratoListItem>>("contratos", {
        query: {
          page,
          page_size: Number(pageSize),
          associado: debouncedSearch || undefined,
          status_renovacao: "apto_a_renovar",
        },
      }),
  });

  const refinanciadosRows = refinanciamentosQuery.data?.results ?? [];
  const aptosRows = aptosQuery.data?.results ?? [];
  const resumo = resumoQuery.data ?? EMPTY_RESUMO;

  const refinanciadosColumns = React.useMemo<DataTableColumn<RefinanciamentoItem>[]>(
    () => [
      {
        id: "associado",
        header: "Associado",
        cellClassName: "min-w-[20rem]",
        cell: (row) => (
          <AssociadoSummary
            nome={row.associado_nome}
            cpf={row.cpf_cnpj}
            matricula={row.matricula_display || row.matricula}
          />
        ),
      },
      {
        id: "contrato",
        header: "Contrato",
        cellClassName: "min-w-[14rem]",
        cell: (row) => (
          <div className="space-y-2">
            <p className="font-mono text-xs text-foreground">{row.contrato_codigo}</p>
            <StatusBadge status={row.status} />
          </div>
        ),
      },
      {
        id: "ciclo",
        header: "Ciclo",
        cellClassName: "min-w-[14rem]",
        cell: (row) => <CycleSignature cicloKey={row.ciclo_key} />,
      },
      {
        id: "refs",
        header: "Referências",
        cellClassName: "min-w-[14rem]",
        cell: (row) => <ReferenceList referencias={row.referencias} />,
      },
      {
        id: "ativacao",
        header: "Renovação",
        cellClassName: "min-w-[15rem]",
        cell: (row) => <RenovacaoSummary row={row} />,
      },
      {
        id: "repasse",
        header: "Repasse agente",
        cellClassName: "whitespace-nowrap",
        cell: (row) => (
          <span className="font-medium text-emerald-400">
            {formatCurrency(row.repasse_agente)}
          </span>
        ),
      },
      {
        id: "comprovantes",
        header: "Anexo do agente",
        cellClassName: "min-w-[16rem]",
        cell: (row) => <AgentAttachmentList comprovantes={row.comprovantes} />,
      },
    ],
    [],
  );

  const aptosColumns = React.useMemo<DataTableColumn<ContratoListItem>[]>(
    () => [
      {
        id: "associado",
        header: "Associado",
        cellClassName: "min-w-[20rem]",
        cell: (row) => (
          <AssociadoSummary
            nome={row.associado.nome_completo}
            cpf={row.associado.cpf_cnpj}
            matricula={row.associado.matricula_display || row.associado.matricula}
          />
        ),
      },
      {
        id: "contrato",
        header: "Contrato",
        cellClassName: "min-w-[14rem]",
        cell: (row) => (
          <div className="space-y-2">
            <p className="font-mono text-xs text-foreground">{row.codigo}</p>
            <StatusBadge
              status={row.status_renovacao || "apto_a_renovar"}
              label="Apto a renovar"
            />
          </div>
        ),
      },
      {
        id: "mensalidades",
        header: "Mensalidades do ciclo",
        cellClassName: "min-w-[15rem]",
        cell: (row) => (
          <div className="space-y-1">
            <p className="font-medium">
              {row.mensalidades.pagas}/{row.mensalidades.total}
            </p>
            <p className="text-xs text-muted-foreground">
              {row.mensalidades.descricao}
            </p>
          </div>
        ),
      },
      {
        id: "status_contrato",
        header: "Contrato atual",
        cell: (row) => (
          <StatusBadge
            status={row.status_visual_slug}
            label={row.status_visual_label}
          />
        ),
      },
      {
        id: "valor",
        header: "Mensalidade",
        cellClassName: "whitespace-nowrap",
        cell: (row) => formatCurrency(row.valor_mensalidade),
      },
    ],
    [],
  );

  return (
    <Tabs
      value={tab}
      onValueChange={(value) => {
        setTab(value as RefinanciadosTab);
        setPage(1);
      }}
      className="space-y-6"
    >
      <section className="rounded-[1.75rem] border border-border/60 bg-card/70 p-6 shadow-xl shadow-black/15">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-2">
            <h1 className="text-3xl font-semibold tracking-tight">
              Refinanciados
            </h1>
            <p className="max-w-3xl text-sm text-muted-foreground">
              Acompanhe separadamente os contratos com renovação já efetivada e
              os contratos que ainda estão aptos a renovar.
            </p>
          </div>
          <TabsList variant="line">
            <TabsTrigger value="efetivados">Renovação efetivada</TabsTrigger>
            <TabsTrigger value="aptos">Aptos a renovar</TabsTrigger>
          </TabsList>
        </div>
      </section>

      <TabsContent value="efetivados" className="space-y-6">
        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {resumoQuery.isLoading && !resumoQuery.data ? (
            Array.from({ length: 4 }).map((_, index) => (
              <MetricCardSkeleton key={index} />
            ))
          ) : (
            <>
              <StatsCard
                title="Contratos refinanciados"
                value={String(resumo.total)}
                delta={`${resumo.efetivados} com status efetivado`}
                icon={RefreshCcwIcon}
                tone="neutral"
              />
              <StatsCard
                title="Efetivados"
                value={String(resumo.efetivados)}
                delta={`${resumo.concluidos} finalizados no recorte`}
                icon={BadgeCheckIcon}
                tone="positive"
              />
              <StatsCard
                title="Com anexo do agente"
                value={String(resumo.com_anexo_agente)}
                delta="Comprovante do agente disponível"
                icon={PaperclipIcon}
                tone="neutral"
              />
              <StatsCard
                title="Repasse total"
                value={formatCurrency(resumo.repasse_total)}
                delta="Soma do repasse do agente no recorte"
                icon={HandCoinsIcon}
                tone="positive"
              />
            </>
          )}
        </section>

        <section className="grid gap-3 rounded-[1.75rem] border border-border/60 bg-card/50 p-4 xl:grid-cols-[minmax(0,1fr)_220px_minmax(0,0.9fr)_160px_auto_auto]">
          <Input
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
            placeholder="Buscar por nome, CPF, matrícula, contrato ou ciclo..."
            className="rounded-2xl border-border/60 bg-card/60"
          />
          <Select
            value={finalStatus}
            onValueChange={(value) => {
              setFinalStatus(value);
              setPage(1);
            }}
          >
            <SelectTrigger className="rounded-2xl bg-card/60">
              <SelectValue placeholder="Todos finalizados" />
            </SelectTrigger>
            <SelectContent>
              {FINAL_STATUS_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Input
            value={cycleKey}
            onChange={(event) => {
              setCycleKey(event.target.value);
              setPage(1);
            }}
            placeholder="Ciclo (ex: 2026-03|2026-04|2026-05)"
            className="rounded-2xl border-border/60 bg-card/60"
          />
          <PageSizeSelect
            value={pageSize}
            onValueChange={(value) => {
              setPageSize(value);
              setPage(1);
            }}
          />
          <Button onClick={() => setPage(1)}>Aplicar</Button>
          <Button
            variant="outline"
            onClick={() => {
              setSearch("");
              setFinalStatus("todos");
              setCycleKey("");
              setPageSize("15");
              setPage(1);
            }}
          >
            Limpar
          </Button>
        </section>

        <DataTable
          data={refinanciadosRows}
          columns={refinanciadosColumns}
          currentPage={page}
          totalPages={Math.max(
            1,
            Math.ceil(
              (refinanciamentosQuery.data?.count ?? 0) / Number(pageSize),
            ),
          )}
          onPageChange={setPage}
          emptyMessage="Nenhum contrato com renovação efetivada encontrado."
          loading={refinanciamentosQuery.isLoading}
          skeletonRows={6}
        />
      </TabsContent>

      <TabsContent value="aptos" className="space-y-6">
        <section className="rounded-[1.75rem] border border-border/60 bg-card/60 p-5">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="space-y-1">
              <p className="text-sm font-medium text-foreground">
                Contratos aptos a renovar
              </p>
              <p className="text-sm text-muted-foreground">
                Esta aba mostra somente os contratos do agente que já podem
                entrar em uma nova renovação.
              </p>
            </div>
            <StatsCard
              title="Aptos a renovar"
              value={String(aptosQuery.data?.count ?? 0)}
              delta={`${aptosRows.length} exibidos na página atual`}
              icon={WalletIcon}
              tone="neutral"
            />
          </div>
        </section>

        <section className="grid gap-3 rounded-[1.75rem] border border-border/60 bg-card/50 p-4 xl:grid-cols-[minmax(0,1fr)_160px_auto_auto]">
          <Input
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
            placeholder="Buscar por nome, CPF, matrícula ou contrato..."
            className="rounded-2xl border-border/60 bg-card/60"
          />
          <PageSizeSelect
            value={pageSize}
            onValueChange={(value) => {
              setPageSize(value);
              setPage(1);
            }}
          />
          <Button onClick={() => setPage(1)}>Aplicar</Button>
          <Button
            variant="outline"
            onClick={() => {
              setSearch("");
              setPageSize("15");
              setPage(1);
            }}
          >
            Limpar
          </Button>
        </section>

        <DataTable
          data={aptosRows}
          columns={aptosColumns}
          currentPage={page}
          totalPages={Math.max(
            1,
            Math.ceil((aptosQuery.data?.count ?? 0) / Number(pageSize)),
          )}
          onPageChange={setPage}
          emptyMessage="Nenhum contrato apto a renovar encontrado."
          loading={aptosQuery.isLoading}
          skeletonRows={6}
        />
      </TabsContent>
    </Tabs>
  );
}

function AssociadoSummary({
  nome,
  cpf,
  matricula,
}: {
  nome: string;
  cpf: string;
  matricula: string;
}) {
  return (
    <div className="space-y-1.5">
      <p className="font-semibold leading-tight text-foreground">{nome}</p>
      <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
        <span>{maskCPFCNPJ(cpf)}</span>
        <span>Mat.: {matricula || "N/I"}</span>
      </div>
    </div>
  );
}

function CycleSignature({ cicloKey }: { cicloKey: string }) {
  const parts = cicloKey
    .split("|")
    .map((value) => value.trim())
    .filter(Boolean);

  if (!parts.length) {
    return <span className="text-sm text-muted-foreground">Sem ciclo definido</span>;
  }

  return (
    <div className="flex flex-wrap gap-2">
      {parts.map((part) => (
        <Badge
          key={part}
          variant="outline"
          className="rounded-full border-border/60 bg-background/40 font-mono text-[11px]"
        >
          {part}
        </Badge>
      ))}
    </div>
  );
}

function ReferenceList({ referencias }: { referencias: string[] }) {
  if (!referencias.length) {
    return <span className="text-sm text-muted-foreground">Sem referências</span>;
  }

  return (
    <div className="flex flex-wrap gap-2">
      {referencias.map((referencia) => (
        <Badge
          key={referencia}
          className="rounded-full bg-sky-500/15 text-sky-200"
        >
          {formatMonthYear(referencia)}
        </Badge>
      ))}
    </div>
  );
}

function RenovacaoSummary({ row }: { row: RefinanciamentoItem }) {
  const activationDate = row.data_ativacao_ciclo || row.executado_em;
  const helperLabel = row.data_ativacao_ciclo
    ? "Ciclo ativado"
    : row.executado_em
      ? "Efetivado na tesouraria"
      : "Data não identificada";

  if (!activationDate) {
    return <span className="text-sm text-muted-foreground">N/I</span>;
  }

  return (
    <div className="space-y-1.5">
      <p className="text-sm font-medium">{formatDateTime(activationDate, "N/I")}</p>
      <div className="flex flex-wrap gap-2">
        <Badge className="rounded-full bg-emerald-500/15 text-emerald-200">
          {helperLabel}
        </Badge>
        {row.ativacao_inferida ? (
          <Badge className="rounded-full bg-amber-500/15 text-amber-200">
            Inferido
          </Badge>
        ) : null}
      </div>
    </div>
  );
}

function AgentAttachmentList({
  comprovantes,
}: {
  comprovantes: RefinanciamentoItem["comprovantes"];
}) {
  if (!comprovantes.length) {
    return (
      <span className="text-sm text-muted-foreground">
        Sem anexo do agente.
      </span>
    );
  }

  return (
    <div className="flex flex-wrap gap-2">
      {comprovantes.map((comprovante) =>
        comprovante.arquivo_disponivel_localmente ? (
          <Button key={comprovante.id} size="sm" variant="outline" asChild>
            <a
              href={buildBackendFileUrl(comprovante.arquivo)}
              target="_blank"
              rel="noreferrer"
            >
              {comprovante.nome_original || "Abrir anexo"}
            </a>
          </Button>
        ) : (
          <span
            key={comprovante.id}
            className="inline-flex items-center rounded-full border border-dashed border-border/60 px-3 py-1 text-xs text-muted-foreground"
            title={comprovante.arquivo_referencia}
          >
            Referência legado
          </span>
        ),
      )}
    </div>
  );
}

function PageSizeSelect({
  value,
  onValueChange,
}: {
  value: string;
  onValueChange: (value: string) => void;
}) {
  return (
    <Select value={value} onValueChange={onValueChange}>
      <SelectTrigger className="rounded-2xl bg-card/60">
        <SelectValue placeholder="15" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="15">15 / página</SelectItem>
        <SelectItem value="30">30 / página</SelectItem>
        <SelectItem value="50">50 / página</SelectItem>
      </SelectContent>
    </Select>
  );
}
