"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  BellRingIcon,
  BriefcaseBusiness,
  ChevronRightIcon,
  EyeIcon,
  FilterIcon,
  TriangleAlertIcon,
  WalletIcon,
} from "lucide-react";

import type {
  Ciclo,
  ContratoListItem,
  ContratoResumoCards,
  PaginatedResponse,
} from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import {
  formatDateValue,
  formatMonthValue,
  parseDateValue,
  parseMonthValue,
} from "@/lib/date-value";
import { formatCurrency, formatDate, formatMonthYear } from "@/lib/formatters";
import { cn } from "@/lib/utils";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { usePermissions } from "@/hooks/use-permissions";
import CalendarCompetencia from "@/components/custom/calendar-competencia";
import DatePicker from "@/components/custom/date-picker";
import StatusBadge from "@/components/custom/status-badge";
import CopySnippet from "@/components/shared/copy-snippet";
import DataTable, {
  type DataTableColumn,
} from "@/components/shared/data-table";
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
import { Spinner } from "@/components/ui/spinner";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const CONTRATO_STATUS_LABELS: Record<string, string> = {
  pendente: "Pendente",
  ativo: "Ativo",
  desativado: "Desativado",
  inadimplente: "Inadimplente",
};

const ETAPA_FLUXO_LABELS: Record<string, string> = {
  analise: "Análise",
  tesouraria: "Tesouraria",
  concluido: "Concluído",
};

const STATUS_FILTER_OPTIONS = [
  { value: "todos", label: "Todos os status" },
  { value: "pendente", label: "Pendente" },
  { value: "ativo", label: "Ativo" },
  { value: "desativado", label: "Desativado" },
  { value: "inadimplente", label: "Inadimplente" },
];

const ETAPA_FILTER_OPTIONS = [
  { value: "todas", label: "Todas as etapas" },
  { value: "analise", label: "Análise" },
  { value: "tesouraria", label: "Tesouraria" },
  { value: "concluido", label: "Concluído" },
];

const PAGE_SIZE_OPTIONS = [
  { value: "10", label: "10 por página" },
  { value: "20", label: "20 por página" },
  { value: "50", label: "50 por página" },
  { value: "100", label: "100 por página" },
  { value: "all", label: "Todos" },
];

function normalizeEtapaFluxo(stage: string) {
  if (stage === "tesouraria") return "tesouraria";
  if (stage === "concluido") return "concluido";
  return "analise";
}

function ContratoCiclosPanel({ associadoId }: { associadoId: number }) {
  const ciclosQuery = useQuery({
    queryKey: ["contrato-associado-ciclos", associadoId],
    queryFn: () => apiFetch<Ciclo[]>(`associados/${associadoId}/ciclos`),
  });

  if (ciclosQuery.isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Spinner />
        Carregando ciclos...
      </div>
    );
  }

  const ciclos = ciclosQuery.data ?? [];
  if (!ciclos.length) {
    return (
      <p className="text-sm text-muted-foreground">Nenhum ciclo encontrado.</p>
    );
  }

  return (
    <Tabs defaultValue={String(ciclos[0]?.id)}>
      <TabsList variant="line">
        {ciclos.map((ciclo) => (
          <TabsTrigger key={ciclo.id} value={String(ciclo.id)}>
            Ciclo {ciclo.numero}
          </TabsTrigger>
        ))}
      </TabsList>
      {ciclos.map((ciclo) => (
        <TabsContent key={ciclo.id} value={String(ciclo.id)} className="pt-4">
          <div className="mb-4 flex items-center justify-between">
            <p className="text-sm text-muted-foreground">
              Referências de {formatMonthYear(ciclo.data_inicio)} até{" "}
              {formatMonthYear(ciclo.data_fim)}
            </p>
            <StatusBadge status={ciclo.status} />
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            {ciclo.parcelas.map((parcela) => (
              <div
                key={parcela.id}
                className="rounded-2xl border border-border/60 bg-background/70 p-4"
              >
                <div className="flex items-center justify-between gap-3">
                  <p className="font-medium">Parcela {parcela.numero}/3</p>
                  <StatusBadge status={parcela.status} />
                </div>
                <p className="mt-2 text-sm text-muted-foreground">
                  {formatMonthYear(parcela.referencia_mes)}
                </p>
              </div>
            ))}
          </div>
        </TabsContent>
      ))}
    </Tabs>
  );
}

export default function MeusContratosPage() {
  const { hasRole } = usePermissions();
  const isAdmin = hasRole("ADMIN");
  const [associadoFilter, setAssociadoFilter] = React.useState("");
  const [agenteFilter, setAgenteFilter] = React.useState("");
  const [statusFilter, setStatusFilter] = React.useState("todos");
  const [etapaFilter, setEtapaFilter] = React.useState("todas");
  const [competenciaFilter, setCompetenciaFilter] = React.useState("");
  const [dataInicio, setDataInicio] = React.useState("");
  const [dataFim, setDataFim] = React.useState("");
  const [page, setPage] = React.useState(1);
  const [pageSize, setPageSize] = React.useState("10");
  const [mensalidadesFilter, setMensalidadesFilter] = React.useState("todas");
  const debouncedAssociadoFilter = useDebouncedValue(associadoFilter, 300);
  const debouncedAgenteFilter = useDebouncedValue(agenteFilter, 300);
  const isAllPageSize = pageSize === "all";

  const resetAdvancedFilters = React.useCallback(() => {
    setAgenteFilter("");
    setStatusFilter("todos");
    setEtapaFilter("todas");
    setCompetenciaFilter("");
    setDataInicio("");
    setDataFim("");
    setMensalidadesFilter("todas");
    setPageSize("10");
    setPage(1);
  }, []);

  const resumoQuery = useQuery({
    queryKey: [
      "contratos-resumo",
      isAdmin,
      debouncedAssociadoFilter,
      debouncedAgenteFilter,
      statusFilter,
      etapaFilter,
      competenciaFilter,
      dataInicio,
      dataFim,
      mensalidadesFilter,
    ],
    queryFn: () =>
      apiFetch<ContratoResumoCards>("contratos/resumo", {
        query: {
          associado: debouncedAssociadoFilter || undefined,
          agente: isAdmin ? debouncedAgenteFilter || undefined : undefined,
          status_visual: statusFilter === "todos" ? undefined : statusFilter,
          etapa_fluxo: etapaFilter === "todas" ? undefined : etapaFilter,
          competencia: competenciaFilter || undefined,
          data_inicio: dataInicio || undefined,
          data_fim: dataFim || undefined,
          mensalidades:
            mensalidadesFilter === "todas"
              ? undefined
              : Number(mensalidadesFilter),
        },
      }),
  });

  const contratosQuery = useQuery({
    queryKey: [
      "contratos-lista",
      isAdmin,
      page,
      pageSize,
      debouncedAssociadoFilter,
      debouncedAgenteFilter,
      statusFilter,
      etapaFilter,
      competenciaFilter,
      dataInicio,
      dataFim,
      mensalidadesFilter,
    ],
    queryFn: () =>
      apiFetch<PaginatedResponse<ContratoListItem>>("contratos", {
        query: {
          page,
          page_size: isAllPageSize ? "all" : Number(pageSize),
          associado: debouncedAssociadoFilter || undefined,
          agente: isAdmin ? debouncedAgenteFilter || undefined : undefined,
          status_visual: statusFilter === "todos" ? undefined : statusFilter,
          etapa_fluxo: etapaFilter === "todas" ? undefined : etapaFilter,
          competencia: competenciaFilter || undefined,
          data_inicio: dataInicio || undefined,
          data_fim: dataFim || undefined,
          mensalidades:
            mensalidadesFilter === "todas"
              ? undefined
              : Number(mensalidadesFilter),
        },
      }),
  });

  const rows = contratosQuery.data?.results ?? [];
  const totalCount = contratosQuery.data?.count ?? 0;
  const totalPages = Math.max(
    1,
    isAllPageSize ? 1 : Math.ceil(totalCount / Number(pageSize)),
  );
  const activeAdvancedFiltersCount = React.useMemo(
    () =>
      [
        Boolean(agenteFilter.trim()),
        statusFilter !== "todos",
        etapaFilter !== "todas",
        Boolean(competenciaFilter),
        Boolean(dataInicio),
        Boolean(dataFim),
        mensalidadesFilter !== "todas",
        pageSize !== "10",
      ].filter(Boolean).length,
    [
      agenteFilter,
      statusFilter,
      etapaFilter,
      competenciaFilter,
      dataInicio,
      dataFim,
      mensalidadesFilter,
      pageSize,
    ],
  );

  React.useEffect(() => {
    if (page > totalPages) {
      setPage(totalPages);
    }
  }, [page, totalPages]);

  const columns = React.useMemo<DataTableColumn<ContratoListItem>[]>(
    () => [
      {
        id: "associado",
        header: "Associado",
        headerClassName: "w-[19%] whitespace-normal leading-5",
        cellClassName: "whitespace-normal break-words",
        cell: (row) => (
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <ChevronRightIcon className="size-4 shrink-0 text-muted-foreground" />
              <div className="min-w-0 space-y-1">
                <CopySnippet
                  label="Nome"
                  value={row.associado.nome_completo}
                  inline
                  className="max-w-full"
                />
                <p className="text-xs text-muted-foreground">
                  Clique na linha para ver ciclos
                </p>
              </div>
            </div>
            <div className="flex flex-wrap gap-2 pl-7">
              <CopySnippet label="CPF" value={row.associado.cpf_cnpj} mono />
              <CopySnippet
                label="Matrícula"
                value={row.associado.matricula_orgao || row.associado.matricula}
                mono
              />
            </div>
          </div>
        ),
      },
      ...(isAdmin
        ? [
            {
              id: "agente",
              header: "Agente",
              headerClassName: "w-[11%] whitespace-normal leading-5",
              cellClassName: "whitespace-normal break-words",
              cell: (row: ContratoListItem) =>
                row.agente?.full_name ?? "Sem agente",
            } satisfies DataTableColumn<ContratoListItem>,
          ]
        : []),
      {
        id: "status",
        header: "Status do Contrato",
        headerClassName: "w-[14%] whitespace-normal leading-5",
        cellClassName: "whitespace-normal",
        cell: (row) => (
          <div className="space-y-3">
            <div className="space-y-1">
              <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                Status do contrato
              </p>
              <StatusBadge
                status={row.status_contrato_visual}
                label={
                  CONTRATO_STATUS_LABELS[row.status_contrato_visual] ??
                  "Pendente"
                }
              />
            </div>
            <div className="space-y-1">
              <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
                Etapa do fluxo
              </p>
              <StatusBadge
                status={normalizeEtapaFluxo(row.etapa_fluxo)}
                label={
                  ETAPA_FLUXO_LABELS[normalizeEtapaFluxo(row.etapa_fluxo)] ??
                  "Análise"
                }
              />
            </div>
          </div>
        ),
      },
      {
        id: "mensalidade",
        header: "Mensalidade",
        headerClassName: "w-[10%] whitespace-normal leading-5",
        cell: (row) => formatCurrency(row.valor_mensalidade),
      },
      {
        id: "auxilio",
        header: "Auxílio do Agente",
        headerClassName: "w-[12%] whitespace-normal leading-5",
        cellClassName: "whitespace-normal",
        cell: (row) => (
          <div>
            <p>{formatCurrency(row.comissao_agente)}</p>
            <p className="text-xs text-muted-foreground">10% da margem</p>
          </div>
        ),
      },
      {
        id: "mensalidades",
        header: "Mensalidades do ciclo atual",
        headerClassName: "w-[16%] whitespace-normal leading-5",
        cellClassName: "whitespace-normal",
        cell: (row) => (
          <div className="space-y-2">
            <p className="font-medium">
              {row.mensalidades.pagas}/{row.mensalidades.total}
            </p>
            <p className="text-xs text-muted-foreground">
              {row.mensalidades.descricao}
            </p>
            <div className="flex flex-wrap gap-2">
              {row.mensalidades.apto_refinanciamento ? (
                <Badge className="rounded-full bg-emerald-500/15 text-emerald-200">
                  Apto a refinanciamento
                </Badge>
              ) : null}
              {row.mensalidades.refinanciamento_ativo ? (
                <Badge className="rounded-full bg-amber-500/15 text-amber-200">
                  CPF já possui refinanciamento
                </Badge>
              ) : null}
            </div>
          </div>
        ),
      },
      {
        id: "liberacao",
        header: "Liberação do Auxílio",
        headerClassName: "w-[10%] whitespace-normal leading-5",
        cellClassName: "whitespace-normal",
        cell: (row) =>
          row.auxilio_liberado_em ? (
            <div className="space-y-1">
              <StatusBadge status="pago" label="Pago" />
              <p className="text-xs text-muted-foreground">
                {formatDate(row.auxilio_liberado_em)}
              </p>
            </div>
          ) : (
            <StatusBadge status="pendente" label="Pendente" />
          ),
      },
      {
        id: "acoes",
        header: "Ações",
        headerClassName: "w-[8%] whitespace-normal leading-5",
        cellClassName: "whitespace-normal",
        cell: (row) => (
          <div
            className="flex items-center gap-2"
            onClick={(event) => event.stopPropagation()}
          >
            <Button variant="outline" size="icon-sm" asChild>
              <Link href={`/associados/${row.associado.id}`}>
                <EyeIcon className="size-4" />
              </Link>
            </Button>
          </div>
        ),
      },
    ],
    [isAdmin],
  );

  return (
    <div className="min-w-0 space-y-6">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatsCard
          title="Contratos cadastrados"
          value={String(resumoQuery.data?.total ?? 0)}
          delta={`${resumoQuery.data?.pendentes ?? 0} pendentes no recorte atual`}
          tone="neutral"
          icon={BriefcaseBusiness}
        />
        <StatsCard
          title="Contratos ativos"
          value={String(resumoQuery.data?.ativos ?? 0)}
          delta="Liberados para acompanhamento mensal"
          tone="positive"
          icon={WalletIcon}
        />
        <StatsCard
          title="Contratos pendentes"
          value={String(resumoQuery.data?.pendentes ?? 0)}
          delta="Aguardando análise ou tesouraria"
          tone="warning"
          icon={BellRingIcon}
        />
        <StatsCard
          title="Contratos inadimplentes"
          value={String(resumoQuery.data?.inadimplentes ?? 0)}
          delta="Associados com pendência de desconto"
          tone="warning"
          icon={TriangleAlertIcon}
        />
      </section>

      <section className="min-w-0 space-y-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h1 className="text-2xl font-semibold">
              {isAdmin ? "Todos os Contratos" : "Meus Contratos"}
            </h1>
            <p className="text-sm text-muted-foreground">
              {isAdmin
                ? "Visão consolidada de todos os contratos com filtros por período, associado, agente e status."
                : "Acompanhe seus contratos, mensalidades e elegibilidade para refinanciamento."}
            </p>
          </div>
          {!isAdmin ? (
            <Button asChild>
              <Link href="/agentes/cadastrar-associado">+ Novo Associado</Link>
            </Button>
          ) : null}
        </div>

        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div className="relative w-full max-w-2xl">
            <Input
              value={associadoFilter}
              onChange={(event) => {
                setAssociadoFilter(event.target.value);
                setPage(1);
              }}
              placeholder="Buscar por nome, CPF ou matrícula"
              className="w-full rounded-2xl border-border/60 bg-card/60"
            />
          </div>
          <div className="flex flex-wrap gap-3">
            <Sheet>
              <SheetTrigger asChild>
                <Button variant="outline">
                  <FilterIcon className="size-4" />
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
                    Ajuste etapa do fluxo, competência, período, mensalidades,
                    paginação e filtros administrativos.
                  </SheetDescription>
                </SheetHeader>

                <div className="space-y-5 overflow-y-auto px-4 pb-4">
                  {isAdmin ? (
                    <FilterField label="Agente">
                      <Input
                        value={agenteFilter}
                        onChange={(event) => {
                          setAgenteFilter(event.target.value);
                          setPage(1);
                        }}
                        placeholder="Nome ou email do agente"
                        className="w-full rounded-2xl border-border/60 bg-card/60"
                      />
                    </FilterField>
                  ) : null}

                  <div className="grid gap-4 md:grid-cols-2">
                    <FilterField label="Status do contrato">
                      <Select
                        value={statusFilter}
                        onValueChange={(value) => {
                          setStatusFilter(value);
                          setPage(1);
                        }}
                      >
                        <SelectTrigger className="w-full rounded-2xl bg-card/60">
                          <SelectValue placeholder="Status do contrato" />
                        </SelectTrigger>
                        <SelectContent>
                          {STATUS_FILTER_OPTIONS.map((option) => (
                            <SelectItem key={option.value} value={option.value}>
                              {option.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </FilterField>

                    <FilterField label="Etapa do fluxo">
                      <Select
                        value={etapaFilter}
                        onValueChange={(value) => {
                          setEtapaFilter(value);
                          setPage(1);
                        }}
                      >
                        <SelectTrigger className="w-full rounded-2xl bg-card/60">
                          <SelectValue placeholder="Etapa do fluxo" />
                        </SelectTrigger>
                        <SelectContent>
                          {ETAPA_FILTER_OPTIONS.map((option) => (
                            <SelectItem key={option.value} value={option.value}>
                              {option.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </FilterField>
                  </div>

                  <div className="grid gap-4 md:grid-cols-2">
                    <FilterField label="Mês e ano">
                      <CalendarCompetencia
                        value={parseMonthValue(competenciaFilter)}
                        onChange={(value) => {
                          setCompetenciaFilter(formatMonthValue(value));
                          setPage(1);
                        }}
                      />
                    </FilterField>

                    <FilterField label="Itens por página">
                      <Select
                        value={pageSize}
                        onValueChange={(value) => {
                          setPageSize(value);
                          setPage(1);
                        }}
                      >
                        <SelectTrigger className="w-full rounded-2xl bg-card/60">
                          <SelectValue placeholder="Itens por página" />
                        </SelectTrigger>
                        <SelectContent>
                          {PAGE_SIZE_OPTIONS.map((option) => (
                            <SelectItem key={option.value} value={option.value}>
                              {option.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </FilterField>
                  </div>

                  <div className="grid gap-4 md:grid-cols-2">
                    <FilterField label="Data inicial">
                      <DatePicker
                        value={parseDateValue(dataInicio)}
                        onChange={(value) => {
                          setDataInicio(formatDateValue(value));
                          setPage(1);
                        }}
                        placeholder="Data inicial"
                      />
                    </FilterField>

                    <FilterField label="Data final">
                      <DatePicker
                        value={parseDateValue(dataFim)}
                        onChange={(value) => {
                          setDataFim(formatDateValue(value));
                          setPage(1);
                        }}
                        placeholder="Data final"
                      />
                    </FilterField>
                  </div>

                  <FilterField label="Mensalidades do ciclo atual">
                    <Select
                      value={mensalidadesFilter}
                      onValueChange={(value) => {
                        setMensalidadesFilter(value);
                        setPage(1);
                      }}
                    >
                      <SelectTrigger className="w-full rounded-2xl bg-card/60">
                        <SelectValue placeholder="Mensalidades" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="todas">Todas</SelectItem>
                        <SelectItem value="1">1/3</SelectItem>
                        <SelectItem value="2">2/3</SelectItem>
                        <SelectItem value="3">3/3</SelectItem>
                      </SelectContent>
                    </Select>
                  </FilterField>
                </div>

                <SheetFooter className="border-t border-border/60">
                  <Button
                    variant="outline"
                    onClick={resetAdvancedFilters}
                    type="button"
                  >
                    Limpar avançados
                  </Button>
                  <SheetClose asChild>
                    <Button type="button">Fechar</Button>
                  </SheetClose>
                </SheetFooter>
              </SheetContent>
            </Sheet>
          </div>
        </div>

        <p className="text-sm text-muted-foreground">
          Mostrando{" "}
          {rows.length
            ? `${isAllPageSize ? 1 : (page - 1) * Number(pageSize) + 1}-${isAllPageSize ? rows.length : (page - 1) * Number(pageSize) + rows.length}`
            : "0"}{" "}
          de {totalCount}
        </p>
      </section>

      {contratosQuery.isLoading ? (
        <div className="flex items-center gap-3 rounded-3xl border border-border/60 bg-card/60 px-6 py-8 text-sm text-muted-foreground">
          <Spinner />
          Carregando contratos...
        </div>
      ) : (
        <DataTable
          data={rows}
          columns={columns}
          renderExpanded={(row) => (
            <ContratoCiclosPanel associadoId={row.associado.id} />
          )}
          currentPage={page}
          totalPages={totalPages}
          onPageChange={setPage}
          emptyMessage="Nenhum contrato encontrado para os filtros informados."
        />
      )}
    </div>
  );
}

function FilterField({
  label,
  className,
  children,
}: React.PropsWithChildren<{ label: string; className?: string }>) {
  return (
    <div className={cn("space-y-2", className)}>
      <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
        {label}
      </p>
      {children}
    </div>
  );
}
