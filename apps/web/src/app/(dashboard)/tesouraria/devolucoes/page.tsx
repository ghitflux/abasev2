"use client";

import * as React from "react";
import Link from "next/link";
import { format } from "date-fns";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CalendarCheck2Icon,
  HandCoinsIcon,
  ReceiptTextIcon,
  RotateCcwIcon,
  SlidersHorizontalIcon,
  WalletCardsIcon,
} from "lucide-react";
import { toast } from "sonner";

import type {
  DevolucaoAssociadoItem,
  DevolucaoContratoItem,
  DevolucaoKpis,
  PaginatedResponse,
} from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import { buildBackendFileUrl } from "@/lib/backend-files";
import { usePermissions } from "@/hooks/use-permissions";
import { formatCurrency, formatDate, formatMonthYear } from "@/lib/formatters";
import CalendarCompetencia from "@/components/custom/calendar-competencia";
import DatePicker from "@/components/custom/date-picker";
import FileUploadDropzone from "@/components/custom/file-upload-dropzone";
import InputCurrency from "@/components/custom/input-currency";
import StatusBadge from "@/components/custom/status-badge";
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
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";

type ListingTab = "registrar" | "historico";
type RegisterResponse = PaginatedResponse<DevolucaoContratoItem> & {
  kpis: DevolucaoKpis;
};
type HistoryResponse = PaginatedResponse<DevolucaoAssociadoItem> & {
  kpis: DevolucaoKpis;
};

type RegisterState = {
  row: DevolucaoContratoItem;
  tipo: "pagamento_indevido" | "desconto_indevido";
  dataDevolucao?: Date;
  quantidadeParcelas: number;
  valor: number | null;
  motivo: string;
  competenciaReferencia?: Date;
  comprovantes: File[];
};

const comprovanteAccept = {
  "application/pdf": [".pdf"],
  "image/png": [".png"],
  "image/jpeg": [".jpg", ".jpeg"],
};

function useDevolucaoContratosQuery({
  page,
  search,
  competencia,
  estado,
}: {
  page: number;
  search: string;
  competencia?: Date;
  estado: string;
}) {
  return useQuery({
    queryKey: [
      "tesouraria-devolucoes",
      "contratos",
      page,
      search,
      competencia?.toISOString(),
      estado,
    ],
    queryFn: () =>
      apiFetch<RegisterResponse>("tesouraria/devolucoes/contratos", {
        query: {
          page,
          page_size: 20,
          search: search || undefined,
          competencia: competencia ? format(competencia, "yyyy-MM") : undefined,
          estado: estado !== "todos" ? estado : undefined,
        },
      }),
  });
}

function useDevolucaoHistoricoQuery({
  page,
  search,
  competencia,
  tipo,
  status,
}: {
  page: number;
  search: string;
  competencia?: Date;
  tipo: string;
  status: string;
}) {
  return useQuery({
    queryKey: [
      "tesouraria-devolucoes",
      "historico",
      page,
      search,
      competencia?.toISOString(),
      tipo,
      status,
    ],
    queryFn: () =>
      apiFetch<HistoryResponse>("tesouraria/devolucoes", {
        query: {
          page,
          page_size: 20,
          search: search || undefined,
          competencia: competencia ? format(competencia, "yyyy-MM") : undefined,
          tipo: tipo !== "todos" ? tipo : undefined,
          status: status !== "todos" ? status : undefined,
        },
      }),
  });
}

export default function DevolucoesAssociadoPage() {
  const queryClient = useQueryClient();
  const { hasRole } = usePermissions();
  const isAdmin = hasRole("ADMIN");

  const [tab, setTab] = React.useState<ListingTab>("registrar");
  const [page, setPage] = React.useState(1);
  const [search, setSearch] = React.useState("");
  const [competencia, setCompetencia] = React.useState<Date | undefined>();
  const [estado, setEstado] = React.useState("todos");
  const [tipo, setTipo] = React.useState("todos");
  const [status, setStatus] = React.useState("todos");
  const [filtersOpen, setFiltersOpen] = React.useState(false);
  const [draftCompetencia, setDraftCompetencia] = React.useState<Date | undefined>();
  const [draftEstado, setDraftEstado] = React.useState("todos");
  const [draftTipo, setDraftTipo] = React.useState("todos");
  const [draftStatus, setDraftStatus] = React.useState("todos");
  const [registerState, setRegisterState] = React.useState<RegisterState | null>(null);
  const [reverterTarget, setReverterTarget] = React.useState<DevolucaoAssociadoItem | null>(
    null,
  );
  const [motivoReversao, setMotivoReversao] = React.useState("");

  React.useEffect(() => {
    setPage(1);
  }, [tab, search, competencia, estado, tipo, status]);

  const contratosQuery = useDevolucaoContratosQuery({
    page,
    search,
    competencia,
    estado,
  });
  const historicoQuery = useDevolucaoHistoricoQuery({
    page,
    search,
    competencia,
    tipo,
    status,
  });

  const query = tab === "registrar" ? contratosQuery : historicoQuery;
  const totalCount = query.data?.count ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalCount / 20));

  const registrarMutation = useMutation({
    mutationFn: async (payload: RegisterState) => {
      const formData = new FormData();
      formData.append("tipo", payload.tipo);
      formData.append("data_devolucao", format(payload.dataDevolucao as Date, "yyyy-MM-dd"));
      formData.append("quantidade_parcelas", String(payload.quantidadeParcelas));
      formData.append("valor", ((payload.valor ?? 0) / 100).toFixed(2));
      formData.append("motivo", payload.motivo);
      payload.comprovantes.forEach((arquivo) => {
        formData.append("comprovantes", arquivo);
      });
      if (payload.competenciaReferencia) {
        formData.append(
          "competencia_referencia",
          format(payload.competenciaReferencia, "yyyy-MM-01"),
        );
      }
      return apiFetch<DevolucaoAssociadoItem>(
        `tesouraria/devolucoes/contratos/${payload.row.contrato_id}/registrar/`,
        {
          method: "POST",
          formData,
        },
      );
    },
    onSuccess: () => {
      toast.success("Devolução registrada com sucesso.");
      setRegisterState(null);
      setTab("historico");
      void queryClient.invalidateQueries({ queryKey: ["tesouraria-devolucoes"] });
      void queryClient.invalidateQueries({ queryKey: ["associados"] });
      void queryClient.invalidateQueries({ queryKey: ["contratos"] });
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : "Não foi possível registrar a devolução.",
      );
    },
  });

  const reverterMutation = useMutation({
    mutationFn: async ({ id, motivo }: { id: number; motivo: string }) =>
      apiFetch<DevolucaoAssociadoItem>(`tesouraria/devolucoes/${id}/reverter/`, {
        method: "POST",
        body: { motivo_reversao: motivo },
      }),
    onSuccess: () => {
      toast.success("Devolução revertida com sucesso.");
      setReverterTarget(null);
      setMotivoReversao("");
      void queryClient.invalidateQueries({ queryKey: ["tesouraria-devolucoes"] });
      void queryClient.invalidateQueries({ queryKey: ["associados"] });
      void queryClient.invalidateQueries({ queryKey: ["contratos"] });
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : "Não foi possível reverter a devolução.",
      );
    },
  });

  const registerColumns = React.useMemo<DataTableColumn<DevolucaoContratoItem>[]>(
    () => [
      {
        id: "associado",
        header: "Associado",
        cell: (row) => (
          <div>
            <p className="font-medium">{row.nome}</p>
            <p className="text-xs text-muted-foreground">
              {row.cpf_cnpj} · {row.matricula || "Sem matrícula"}
            </p>
          </div>
        ),
      },
      {
        id: "contrato",
        header: "Contrato / Agente",
        cell: (row) => (
          <div>
            <p className="font-medium">{row.contrato_codigo}</p>
            <p className="text-xs text-muted-foreground">{row.agente_nome || "Sem agente"}</p>
          </div>
        ),
      },
      {
        id: "datas",
        header: "Datas",
        cell: (row) => (
          <div className="space-y-1">
            <p className="text-sm text-foreground">Contrato em {formatDate(row.data_contrato)}</p>
            <p className="text-xs text-muted-foreground">
              Averbação{" "}
              {row.mes_averbacao ? formatMonthYear(row.mes_averbacao) : "não informada"}
            </p>
          </div>
        ),
      },
      {
        id: "status",
        header: "Status do contrato",
        cell: (row) => <StatusBadge status={row.status_contrato} />,
      },
      {
        id: "acoes",
        header: "Ações",
        cellClassName: "w-[220px]",
        cell: (row) => (
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="outline">
              <Link href={`/associados/${row.associado_id}`}>Ver cadastro</Link>
            </Button>
            <Button
              size="sm"
              variant="success"
              onClick={() =>
                setRegisterState({
                  row,
                  tipo: "pagamento_indevido",
                  dataDevolucao: new Date(),
                  quantidadeParcelas: 1,
                  valor: null,
                  motivo: "",
                  competenciaReferencia: undefined,
                  comprovantes: [],
                })
              }
            >
              Registrar devolução
            </Button>
          </div>
        ),
      },
    ],
    [],
  );

  const historyColumns = React.useMemo<DataTableColumn<DevolucaoAssociadoItem>[]>(
    () => [
      {
        id: "associado",
        header: "Associado",
        cell: (row) => (
          <div>
            <p className="font-medium">{row.nome}</p>
            <p className="text-xs text-muted-foreground">
              {row.cpf_cnpj} · {row.matricula || "Sem matrícula"}
            </p>
          </div>
        ),
      },
      {
        id: "tipo",
        header: "Tipo / Competência",
        cell: (row) => (
          <div className="space-y-1">
            <StatusBadge status={row.status_devolucao} />
            <p className="text-sm capitalize text-foreground">
              {row.tipo.replaceAll("_", " ")}
            </p>
            <p className="text-xs text-muted-foreground">
              {row.competencia_referencia
                ? `Competência ${formatMonthYear(row.competencia_referencia)}`
                : "Sem competência vinculada"}
            </p>
          </div>
        ),
      },
      {
        id: "valor",
        header: "Valor / Parcelas",
        cell: (row) => (
          <div>
            <p className="font-semibold">{formatCurrency(row.valor)}</p>
            <p className="text-xs text-muted-foreground">
              {row.quantidade_parcelas} parcela(s) · {formatDate(row.data_devolucao)}
            </p>
          </div>
        ),
      },
      {
        id: "comprovante",
        header: "Anexos",
        cell: (row) =>
          row.anexos.length ? (
            <div className="space-y-1">
              {row.anexos.slice(0, 2).map((anexo) => (
                <a
                  key={`${row.id}-${anexo.arquivo_referencia}-${anexo.nome}`}
                  href={buildBackendFileUrl(anexo.url)}
                  target="_blank"
                  rel="noreferrer"
                  className="block text-sm text-primary underline-offset-4 hover:underline"
                >
                  {anexo.nome}
                </a>
              ))}
              {row.anexos.length > 2 ? (
                <p className="text-xs text-muted-foreground">
                  + {row.anexos.length - 2} anexo(s)
                </p>
              ) : null}
            </div>
          ) : (
            <span className="text-sm text-muted-foreground">Sem anexo</span>
          ),
      },
      {
        id: "acoes",
        header: "Ações",
        cellClassName: "w-[220px]",
        cell: (row) => (
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="outline">
              <Link href={`/associados/${row.associado_id}`}>Ver cadastro</Link>
            </Button>
            {isAdmin && row.pode_reverter ? (
              <Button size="sm" variant="outline" onClick={() => setReverterTarget(row)}>
                <RotateCcwIcon className="mr-1.5 size-3.5" />
                Reverter
              </Button>
            ) : null}
          </div>
        ),
      },
    ],
    [isAdmin],
  );

  const registerRows = (contratosQuery.data?.results ?? []) as DevolucaoContratoItem[];
  const historyRows = (historicoQuery.data?.results ?? []) as DevolucaoAssociadoItem[];
  const kpis = query.data?.kpis;
  const activeFiltersCount =
    Number(Boolean(competencia)) +
    Number(tab === "registrar" ? estado !== "todos" : tipo !== "todos") +
    Number(tab === "historico" && status !== "todos");

  return (
    <div className="space-y-6">
      <section className="rounded-[1.75rem] border border-border/60 bg-card/70 p-6">
        <div className="space-y-1">
          <h1 className="text-3xl font-semibold">Devoluções</h1>
          <p className="text-sm text-muted-foreground">
            Registre devoluções por pagamento ou desconto indevido sem alterar parcelas,
            ciclos ou baixa financeira do contrato.
          </p>
        </div>
      </section>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatsCard
          title={tab === "registrar" ? "Contratos disponíveis" : "Registros"}
          value={String(tab === "registrar" ? kpis?.total_contratos ?? 0 : kpis?.total_registros ?? 0)}
          delta={tab === "registrar" ? "Base para registrar devoluções" : "Histórico total"}
          icon={ReceiptTextIcon}
          tone="neutral"
        />
        <StatsCard
          title="Associados impactados"
          value={String(kpis?.associados_impactados ?? 0)}
          delta="Associados distintos no recorte"
          icon={WalletCardsIcon}
          tone="neutral"
        />
        <StatsCard
          title={tab === "registrar" ? "Contratos ativos" : "Valor total"}
          value={
            tab === "registrar"
              ? String(kpis?.ativos ?? 0)
              : formatCurrency(kpis?.valor_total ?? "0")
          }
          delta={
            tab === "registrar"
              ? `${kpis?.encerrados ?? 0} encerrado(s) no recorte`
              : `${kpis?.registradas ?? 0} devolução(ões) ativa(s)`
          }
          icon={HandCoinsIcon}
          tone={tab === "registrar" ? "neutral" : "positive"}
        />
        <StatsCard
          title={tab === "registrar" ? "Cancelados" : "Revertidas"}
          value={String(tab === "registrar" ? kpis?.cancelados ?? 0 : kpis?.revertidas ?? 0)}
          delta={
            tab === "registrar"
              ? "Contratos cancelados disponíveis para consulta"
              : "Registros revertidos por administração"
          }
          icon={CalendarCheck2Icon}
          tone={tab === "registrar" ? "warning" : "warning"}
        />
      </div>

      <Tabs
        value={tab}
        onValueChange={(value) => setTab(value as ListingTab)}
        className="space-y-6"
      >
        <TabsList variant="line" className="justify-start">
          <TabsTrigger value="registrar">Registrar</TabsTrigger>
          <TabsTrigger value="historico">Histórico</TabsTrigger>
        </TabsList>

        <div className="grid gap-4 rounded-[1.75rem] border border-border/60 bg-card/70 p-6 lg:grid-cols-[minmax(0,1fr)_auto]">
          <div className="space-y-2">
            <Label htmlFor="devolucao-search">Buscar</Label>
            <Input
              id="devolucao-search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Nome, CPF, matrícula, contrato ou agente"
              className="h-11 rounded-xl border-border/60 bg-background/50"
            />
          </div>
          <div className="flex items-end justify-end">
            <Sheet
              open={filtersOpen}
              onOpenChange={(open) => {
                if (open) {
                  setDraftCompetencia(competencia);
                  setDraftEstado(estado);
                  setDraftTipo(tipo);
                  setDraftStatus(status);
                }
                setFiltersOpen(open);
              }}
            >
              <SheetTrigger asChild>
                <Button variant="outline" className="h-11 rounded-xl">
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
                    Ajuste competência e filtros específicos para registrar ou revisar devoluções.
                  </SheetDescription>
                </SheetHeader>

                <div className="space-y-5 overflow-y-auto px-4 pb-4">
                  <div className="space-y-2">
                    <Label>Competência</Label>
                    <CalendarCompetencia value={draftCompetencia} onChange={setDraftCompetencia} />
                  </div>

                  {tab === "registrar" ? (
                    <div className="space-y-2">
                      <Label>Status do contrato</Label>
                      <Select value={draftEstado} onValueChange={setDraftEstado}>
                        <SelectTrigger className="h-11 rounded-xl border-border/60 bg-background/50">
                          <SelectValue placeholder="Todos" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="todos">Todos</SelectItem>
                          <SelectItem value="ativo">Ativo</SelectItem>
                          <SelectItem value="encerrado">Encerrado</SelectItem>
                          <SelectItem value="cancelado">Cancelado</SelectItem>
                          <SelectItem value="em_analise">Em análise</SelectItem>
                          <SelectItem value="rascunho">Rascunho</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  ) : (
                    <>
                      <div className="space-y-2">
                        <Label>Tipo</Label>
                        <Select value={draftTipo} onValueChange={setDraftTipo}>
                          <SelectTrigger className="h-11 rounded-xl border-border/60 bg-background/50">
                            <SelectValue placeholder="Todos" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="todos">Todos</SelectItem>
                            <SelectItem value="pagamento_indevido">Pagamento indevido</SelectItem>
                            <SelectItem value="desconto_indevido">Desconto indevido</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-2">
                        <Label>Status</Label>
                        <Select value={draftStatus} onValueChange={setDraftStatus}>
                          <SelectTrigger className="h-11 rounded-xl border-border/60 bg-background/50">
                            <SelectValue placeholder="Todos" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="todos">Todos</SelectItem>
                            <SelectItem value="registrada">Registrada</SelectItem>
                            <SelectItem value="revertida">Revertida</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </>
                  )}
                </div>

                <SheetFooter>
                  <Button
                    variant="outline"
                    onClick={() => {
                      setDraftCompetencia(undefined);
                      setDraftEstado("todos");
                      setDraftTipo("todos");
                      setDraftStatus("todos");
                      setCompetencia(undefined);
                      setEstado("todos");
                      setTipo("todos");
                      setStatus("todos");
                      setFiltersOpen(false);
                    }}
                  >
                    Limpar
                  </Button>
                  <Button
                    onClick={() => {
                      setCompetencia(draftCompetencia);
                      setEstado(draftEstado);
                      setTipo(draftTipo);
                      setStatus(draftStatus);
                      setFiltersOpen(false);
                    }}
                  >
                    Aplicar
                  </Button>
                </SheetFooter>
              </SheetContent>
            </Sheet>
          </div>
        </div>

        <TabsContent value="registrar" className="mt-0">
          <DataTable
            columns={registerColumns}
            data={registerRows}
            loading={contratosQuery.isLoading}
            currentPage={page}
            totalPages={totalPages}
            onPageChange={setPage}
            pageSize={20}
            emptyMessage="Nenhum contrato encontrado para registrar devolução."
          />
        </TabsContent>

        <TabsContent value="historico" className="mt-0">
          <DataTable
            columns={historyColumns}
            data={historyRows}
            loading={historicoQuery.isLoading}
            currentPage={page}
            totalPages={totalPages}
            onPageChange={setPage}
            pageSize={20}
            emptyMessage="Nenhuma devolução registrada no histórico."
          />
        </TabsContent>
      </Tabs>

      <Dialog open={!!registerState} onOpenChange={(open) => !open && setRegisterState(null)}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>Registrar devolução</DialogTitle>
            <DialogDescription>
              O registro é manual e não altera parcelas, ciclos ou pagamentos mensais do
              contrato.
            </DialogDescription>
          </DialogHeader>
          {registerState ? (
            <div className="space-y-5">
              <div className="grid gap-4 rounded-2xl border border-border/60 bg-background/40 p-4 md:grid-cols-2">
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
                    Associado
                  </p>
                  <p className="mt-2 text-sm font-medium">{registerState.row.nome}</p>
                  <p className="text-xs text-muted-foreground">
                    {registerState.row.cpf_cnpj} · {registerState.row.matricula || "Sem matrícula"}
                  </p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
                    Contrato / Agente
                  </p>
                  <p className="mt-2 text-sm font-medium">{registerState.row.contrato_codigo}</p>
                  <p className="text-xs text-muted-foreground">
                    {registerState.row.agente_nome || "Sem agente responsável"}
                  </p>
                </div>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label>Tipo</Label>
                  <Select
                    value={registerState.tipo}
                    onValueChange={(value) =>
                      setRegisterState((current) =>
                        current
                          ? {
                              ...current,
                              tipo: value as RegisterState["tipo"],
                            }
                          : current,
                      )
                    }
                  >
                    <SelectTrigger className="h-11 rounded-xl border-border/60 bg-background/50">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="pagamento_indevido">Pagamento indevido</SelectItem>
                      <SelectItem value="desconto_indevido">Desconto indevido</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="data-devolucao">Data da devolução</Label>
                  <DatePicker
                    value={registerState.dataDevolucao}
                    onChange={(date) =>
                      setRegisterState((current) =>
                        current ? { ...current, dataDevolucao: date } : current,
                      )
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="valor-devolucao">Valor</Label>
                  <InputCurrency
                    value={registerState.valor}
                    onChange={(value) =>
                      setRegisterState((current) =>
                        current ? { ...current, valor: value } : current,
                      )
                    }
                    className="h-11 rounded-xl border-border/60 bg-background/50"
                    placeholder="R$ 0,00"
                  />
                </div>
                <div className="space-y-2">
                  <div className="flex items-center justify-between gap-3">
                    <Label htmlFor="competencia-referencia">Competência de referência</Label>
                    {registerState.competenciaReferencia ? (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-auto px-0 text-xs"
                        onClick={() =>
                          setRegisterState((current) =>
                            current ? { ...current, competenciaReferencia: undefined } : current,
                          )
                        }
                      >
                        Limpar
                      </Button>
                    ) : null}
                  </div>
                  <CalendarCompetencia
                    value={registerState.competenciaReferencia}
                    onChange={(value) =>
                      setRegisterState((current) =>
                        current ? { ...current, competenciaReferencia: value } : current,
                      )
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="quantidade-parcelas">Quantidade de parcelas</Label>
                  <Input
                    id="quantidade-parcelas"
                    type="number"
                    min={1}
                    step={1}
                    value={String(registerState.quantidadeParcelas)}
                    onChange={(event) =>
                      setRegisterState((current) =>
                        current
                          ? {
                              ...current,
                              quantidadeParcelas: Math.max(
                                1,
                                Number.parseInt(event.target.value || "1", 10) || 1,
                              ),
                            }
                          : current,
                      )
                    }
                    className="h-11 rounded-xl border-border/60 bg-background/50"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="motivo-devolucao">Motivo</Label>
                <Textarea
                  id="motivo-devolucao"
                  value={registerState.motivo}
                  onChange={(event) =>
                    setRegisterState((current) =>
                      current ? { ...current, motivo: event.target.value } : current,
                    )
                  }
                  placeholder="Descreva o motivo da devolução ao associado."
                  className="min-h-[120px] rounded-2xl border-border/60 bg-background/50"
                />
              </div>

              <div className="space-y-2">
                <Label>Anexos</Label>
                <FileUploadDropzone
                  accept={comprovanteAccept}
                  files={registerState.comprovantes}
                  multiple
                  onUploadMany={(files) =>
                    setRegisterState((current) =>
                      current ? { ...current, comprovantes: files } : current,
                    )
                  }
                  className="rounded-2xl"
                  emptyTitle="Envie os anexos da devolução"
                  emptyDescription="PDF, JPG ou PNG com limite de 10 MB por arquivo"
                />
              </div>
            </div>
          ) : null}
          <DialogFooter>
            <Button variant="ghost" onClick={() => setRegisterState(null)}>
              Cancelar
            </Button>
            <Button
              variant="success"
              disabled={
                !registerState?.comprovantes.length ||
                !registerState.dataDevolucao ||
                !registerState.valor ||
                !registerState.motivo.trim() ||
                (registerState.tipo === "desconto_indevido" &&
                  !registerState.competenciaReferencia) ||
                registrarMutation.isPending
              }
              onClick={() => registerState && registrarMutation.mutate(registerState)}
            >
              Registrar devolução
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!reverterTarget} onOpenChange={(open) => !open && setReverterTarget(null)}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Reverter devolução</DialogTitle>
            <DialogDescription>
              A reversão mantém o histórico e marca o registro como revertido.
            </DialogDescription>
          </DialogHeader>
          {reverterTarget ? (
            <div className="space-y-4">
              <div className="rounded-2xl border border-border/60 bg-background/40 p-4">
                <p className="font-medium">{reverterTarget.nome}</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  {reverterTarget.contrato_codigo} · {formatCurrency(reverterTarget.valor)}
                </p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="motivo-reversao">Motivo da reversão</Label>
                <Textarea
                  id="motivo-reversao"
                  value={motivoReversao}
                  onChange={(event) => setMotivoReversao(event.target.value)}
                  className="min-h-[120px] rounded-2xl border-border/60 bg-background/50"
                  placeholder="Descreva o motivo da reversão."
                />
              </div>
            </div>
          ) : null}
          <DialogFooter>
            <Button
              variant="ghost"
              onClick={() => {
                setReverterTarget(null);
                setMotivoReversao("");
              }}
            >
              Cancelar
            </Button>
            <Button
              variant="outline"
              disabled={!motivoReversao.trim() || reverterMutation.isPending || !reverterTarget}
              onClick={() =>
                reverterTarget &&
                reverterMutation.mutate({
                  id: reverterTarget.devolucao_id,
                  motivo: motivoReversao,
                })
              }
            >
              Reverter
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
