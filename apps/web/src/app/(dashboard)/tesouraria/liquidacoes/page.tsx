"use client";

import * as React from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { format } from "date-fns";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CalendarCheck2Icon,
  HandCoinsIcon,
  ReceiptTextIcon,
  RotateCcwIcon,
  WalletCardsIcon,
} from "lucide-react";
import { toast } from "sonner";

import type {
  LiquidacaoContratoItem,
  LiquidacaoKpis,
  PaginatedResponse,
} from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import { buildBackendFileUrl } from "@/lib/backend-files";
import { usePermissions } from "@/hooks/use-permissions";
import { formatCurrency, formatDate, formatMonthYear } from "@/lib/formatters";
import CalendarCompetencia from "@/components/custom/calendar-competencia";
import FileUploadDropzone from "@/components/custom/file-upload-dropzone";
import StatusBadge from "@/components/custom/status-badge";
import DataTable, { type DataTableColumn } from "@/components/shared/data-table";
import StatsCard from "@/components/shared/stats-card";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";

type ListingStatus = "elegivel" | "liquidado";
type LiquidacaoResponse = PaginatedResponse<LiquidacaoContratoItem> & {
  kpis: LiquidacaoKpis;
};

type LiquidarState = {
  row: LiquidacaoContratoItem;
  comprovantes: File[];
  dataLiquidacao: string;
  valorTotal: string;
  observacao: string;
};

const comprovanteAccept = {
  "application/pdf": [".pdf"],
  "image/png": [".png"],
  "image/jpeg": [".jpg", ".jpeg"],
};

function useLiquidacoesQuery({
  page,
  tab,
  search,
  competencia,
  estado,
  contractId,
}: {
  page: number;
  tab: ListingStatus;
  search: string;
  competencia?: Date;
  estado: string;
  contractId?: number;
}) {
  return useQuery({
    queryKey: [
      "tesouraria-liquidacoes",
      tab,
      page,
      search,
      competencia?.toISOString(),
      estado,
      contractId,
    ],
    queryFn: () =>
      apiFetch<LiquidacaoResponse>("tesouraria/liquidacoes", {
        query: {
          page,
          page_size: 20,
          status: tab,
          search: search || undefined,
          competencia: competencia ? format(competencia, "yyyy-MM") : undefined,
          estado: tab === "liquidado" && estado !== "todos" ? estado : undefined,
          contract_id: contractId,
        },
      }),
  });
}

export default function LiquidacoesTesourariaPage() {
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const { hasRole } = usePermissions();
  const isAdmin = hasRole("ADMIN");
  const contractId = React.useMemo(() => {
    const value = searchParams.get("contrato");
    const parsed = Number(value);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : undefined;
  }, [searchParams]);
  const origem = searchParams.get("origem");
  const refinanciamentoId = searchParams.get("refinanciamento");
  const initialTab = searchParams.get("status") === "liquidado" ? "liquidado" : "elegivel";
  const [tab, setTab] = React.useState<ListingStatus>(initialTab);
  const [page, setPage] = React.useState(1);
  const [search, setSearch] = React.useState("");
  const [competencia, setCompetencia] = React.useState<Date | undefined>();
  const [estado, setEstado] = React.useState("todos");
  const [liquidarState, setLiquidarState] = React.useState<LiquidarState | null>(null);
  const [reverterTarget, setReverterTarget] = React.useState<LiquidacaoContratoItem | null>(null);
  const [motivoReversao, setMotivoReversao] = React.useState("");

  React.useEffect(() => {
    setPage(1);
  }, [tab, search, competencia, estado]);

  const query = useLiquidacoesQuery({
    page,
    tab,
    search,
    competencia,
    estado,
    contractId,
  });

  const liquidarMutation = useMutation({
    mutationFn: async (payload: LiquidarState) => {
      const formData = new FormData();
      payload.comprovantes.forEach((arquivo) => {
        formData.append("comprovantes", arquivo);
      });
      formData.append("data_liquidacao", payload.dataLiquidacao);
      formData.append("valor_total", payload.valorTotal);
      formData.append("observacao", payload.observacao);
      return apiFetch<LiquidacaoContratoItem>(
        `tesouraria/liquidacoes/${payload.row.contrato_id}/liquidar`,
        {
          method: "POST",
          formData,
        },
      );
    },
    onSuccess: () => {
      toast.success("Liquidação registrada com sucesso.");
      setLiquidarState(null);
      void queryClient.invalidateQueries({ queryKey: ["tesouraria-liquidacoes"] });
      void queryClient.invalidateQueries({ queryKey: ["associados"] });
      void queryClient.invalidateQueries({ queryKey: ["contratos"] });
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Não foi possível liquidar o contrato.");
    },
  });

  const reverterMutation = useMutation({
    mutationFn: async ({
      contratoId,
      motivo,
    }: {
      contratoId: number;
      motivo: string;
    }) =>
      apiFetch<LiquidacaoContratoItem>(`tesouraria/liquidacoes/${contratoId}/reverter`, {
        method: "POST",
        body: { motivo_reversao: motivo },
      }),
    onSuccess: () => {
      toast.success("Liquidação revertida com sucesso.");
      setReverterTarget(null);
      setMotivoReversao("");
      void queryClient.invalidateQueries({ queryKey: ["tesouraria-liquidacoes"] });
      void queryClient.invalidateQueries({ queryKey: ["associados"] });
      void queryClient.invalidateQueries({ queryKey: ["contratos"] });
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Não foi possível reverter a liquidação.");
    },
  });

  const rows = query.data?.results ?? [];
  const kpis = query.data?.kpis;
  const totalCount = query.data?.count ?? 0;

  const columns = React.useMemo<DataTableColumn<LiquidacaoContratoItem>[]>(
    () => [
      {
        id: "associado",
        header: "Associado",
        cell: (row) => (
          <div>
            <p className="font-medium">{row.nome}</p>
            <p className="text-xs text-muted-foreground">
              {row.cpf_cnpj} · {row.matricula}
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
        id: "referencias",
        header: "Parcelas / Referências",
        cell: (row) => (
          <div>
            <p className="font-medium">{row.quantidade_parcelas} parcela(s)</p>
            <p className="text-xs text-muted-foreground">
              {row.referencia_inicial && row.referencia_final
                ? `${formatMonthYear(row.referencia_inicial)} até ${formatMonthYear(row.referencia_final)}`
                : "Sem referências"}
            </p>
          </div>
        ),
      },
      {
        id: "valor_total",
        header: "Valor Total",
        cell: (row) => <span className="font-semibold">{formatCurrency(row.valor_total)}</span>,
      },
      {
        id: "status",
        header: "Status",
        cell: (row) => (
          <div className="space-y-2">
            <StatusBadge status={row.status_liquidacao} />
            {row.status_renovacao === "solicitado_para_liquidacao" ? (
              <StatusBadge
                status={row.status_renovacao}
                label="Solicitado via renovação"
              />
            ) : null}
            {row.data_liquidacao ? (
              <p className="text-xs text-muted-foreground">
                Em {formatDate(row.data_liquidacao)}
              </p>
            ) : (
              <p className="text-xs text-muted-foreground">
                Contrato {row.status_contrato.replaceAll("_", " ")}
              </p>
            )}
          </div>
        ),
      },
      {
        id: "acoes",
        header: "Ações",
        cellClassName: "w-[280px]",
        cell: (row) => (
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="outline">
              <Link href={`/associados/${row.associado_id}`}>Ver cadastro</Link>
            </Button>
            {tab === "elegivel" ? (
              <Button
                size="sm"
                variant="success"
                onClick={() =>
                    setLiquidarState({
                      row,
                      comprovantes: [],
                      dataLiquidacao: format(new Date(), "yyyy-MM-dd"),
                      valorTotal: row.valor_total,
                      observacao: "",
                  })
                }
              >
                Liquidar
              </Button>
            ) : null}
            {tab === "liquidado" && isAdmin && row.pode_reverter ? (
              <Button size="sm" variant="outline" onClick={() => setReverterTarget(row)}>
                <RotateCcwIcon className="mr-1.5 size-3.5" />
                Reverter
              </Button>
            ) : null}
          </div>
        ),
      },
    ],
    [isAdmin, tab],
  );

  const renderExpanded = React.useCallback(
    (row: LiquidacaoContratoItem) => (
      <div className="space-y-3">
        <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
          Parcelas {tab === "elegivel" ? "que serão liquidadas" : "liquidadas"} — {row.nome}
        </p>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {row.parcelas.map((parcela) => (
            <div
              key={`${row.contrato_id}-${parcela.id}-${parcela.referencia_mes}`}
              className="rounded-2xl border border-border/60 bg-background/50 p-4"
            >
              <div className="flex items-center justify-between gap-3">
                <p className="font-medium">Parcela {parcela.numero}</p>
                <StatusBadge status={parcela.status} />
              </div>
              <p className="mt-2 text-sm text-muted-foreground">
                {formatMonthYear(parcela.referencia_mes)} · {formatCurrency(parcela.valor)}
              </p>
              <p className="text-sm text-muted-foreground">
                Vencimento {formatDate(parcela.data_vencimento)}
              </p>
              {parcela.data_pagamento ? (
                <p className="text-sm text-muted-foreground">
                  Pago em {formatDate(parcela.data_pagamento)}
                </p>
              ) : null}
            </div>
          ))}
        </div>
        {row.anexos.length ? (
          <div className="rounded-2xl border border-border/60 bg-background/50 p-4 text-sm">
            <p className="font-medium">Anexos da liquidação</p>
            <div className="mt-2 flex flex-wrap gap-2">
              {row.anexos.map((anexo) => (
                <Button key={`${row.id}-${anexo.arquivo_referencia}-${anexo.nome}`} asChild size="sm" variant="outline">
                  <a href={buildBackendFileUrl(anexo.url)} target="_blank" rel="noreferrer">
                    {anexo.nome}
                  </a>
                </Button>
              ))}
            </div>
          </div>
        ) : null}
        {row.observacao ? (
          <div className="rounded-2xl border border-border/60 bg-background/50 p-4 text-sm text-muted-foreground">
            {row.observacao}
          </div>
        ) : null}
      </div>
    ),
    [tab],
  );

  return (
    <div className="space-y-6">
      <section className="rounded-[1.75rem] border border-border/60 bg-card/70 p-6">
        <div className="space-y-1">
          <h1 className="text-3xl font-semibold">Liquidação</h1>
          <p className="text-sm text-muted-foreground">
            Encerre contratos pela tesouraria com comprovante, trilha financeira e reversão
            administrativa controlada.
          </p>
        </div>
      </section>

      {origem === "renovacao" ? (
        <section className="rounded-[1.5rem] border border-amber-500/30 bg-amber-500/10 p-4">
          <p className="text-sm text-amber-100">
            Solicitação aberta a partir do fluxo de renovação.
            {contractId ? ` Contrato pré-selecionado: ${contractId}.` : ""}
            {refinanciamentoId ? ` Refinanciamento de origem: ${refinanciamentoId}.` : ""}
          </p>
        </section>
      ) : null}

      <Tabs value={tab} onValueChange={(value) => setTab(value as ListingStatus)}>
        <TabsList variant="line" className="justify-start">
          <TabsTrigger value="elegivel">Elegíveis</TabsTrigger>
          <TabsTrigger value="liquidado">Liquidados</TabsTrigger>
        </TabsList>

        <TabsContent value={tab} className="space-y-6">
          <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatsCard
              title={tab === "elegivel" ? "Contratos Elegíveis" : "Contratos Liquidados"}
              value={String(kpis?.total_contratos ?? "0")}
              delta={tab === "elegivel" ? "prontos para encerramento" : "histórico no recorte"}
              icon={HandCoinsIcon}
              tone="neutral"
            />
            <StatsCard
              title="Parcelas Impactadas"
              value={String(kpis?.total_parcelas ?? "0")}
              delta="parcelas já geradas no fluxo"
              icon={ReceiptTextIcon}
              tone="warning"
            />
            <StatsCard
              title="Valor Total"
              value={kpis ? formatCurrency(kpis.valor_total) : "—"}
              delta={tab === "elegivel" ? "valor informado para liquidação" : "valor liquidado"}
              icon={WalletCardsIcon}
              tone="positive"
            />
            <StatsCard
              title={tab === "elegivel" ? "Associados Impactados" : "Liquidações Revertidas"}
              value={String(tab === "elegivel" ? kpis?.associados_impactados ?? 0 : kpis?.revertidas ?? 0)}
              delta={tab === "elegivel" ? "cadastros no recorte" : "histórico revertido"}
              icon={tab === "elegivel" ? CalendarCheck2Icon : RotateCcwIcon}
              tone={tab === "elegivel" ? "neutral" : "warning"}
            />
          </section>

          <section className="rounded-[1.75rem] border border-border/60 bg-card/70 p-5">
            <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_220px_220px]">
              <Input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder={
                  contractId
                    ? "Filtro travado no contrato vindo da renovação"
                    : "Buscar por nome, CPF, matrícula ou contrato..."
                }
                className="rounded-2xl border-border/60 bg-background/60"
                disabled={Boolean(contractId)}
              />
              <CalendarCompetencia
                value={competencia}
                onChange={setCompetencia}
              />
              <Select value={estado} onValueChange={setEstado}>
                <SelectTrigger className="rounded-2xl border-border/60 bg-background/60">
                  <SelectValue placeholder="Status da liquidação" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="todos">Todos status</SelectItem>
                  {tab === "liquidado" ? (
                    <>
                      <SelectItem value="ativa">Ativas</SelectItem>
                      <SelectItem value="revertida">Revertidas</SelectItem>
                    </>
                  ) : null}
                </SelectContent>
              </Select>
            </div>
          </section>

          <DataTable
            columns={columns}
            data={rows}
            renderExpanded={renderExpanded}
            pageSize={20}
            currentPage={page}
            totalPages={Math.max(1, Math.ceil(totalCount / 20))}
            onPageChange={setPage}
            loading={query.isLoading}
            emptyMessage={
              tab === "elegivel"
                ? "Nenhum contrato elegível para liquidação."
                : "Nenhuma liquidação encontrada."
            }
          />
        </TabsContent>
      </Tabs>

      <Dialog
        open={!!liquidarState}
        onOpenChange={(open) => {
          if (!open) {
            setLiquidarState(null);
          }
        }}
      >
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Liquidar Contrato</DialogTitle>
            <DialogDescription>
              {liquidarState ? (
                <>
                  <strong>{liquidarState.row.nome}</strong> · {liquidarState.row.contrato_codigo}
                </>
              ) : null}
            </DialogDescription>
          </DialogHeader>
          {liquidarState ? (
            <div className="space-y-5">
              <div className="grid gap-4 md:grid-cols-3">
                <div className="rounded-2xl border border-border/60 bg-background/60 p-4">
                  <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                    Parcelas
                  </p>
                  <p className="mt-2 text-lg font-semibold">
                    {liquidarState.row.quantidade_parcelas}
                  </p>
                </div>
                <div className="rounded-2xl border border-border/60 bg-background/60 p-4">
                  <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                    Recorte
                  </p>
                  <p className="mt-2 text-sm font-medium">
                    {liquidarState.row.referencia_inicial && liquidarState.row.referencia_final
                      ? `${formatMonthYear(liquidarState.row.referencia_inicial)} até ${formatMonthYear(
                          liquidarState.row.referencia_final,
                        )}`
                      : "Sem referências"}
                  </p>
                </div>
                <div className="rounded-2xl border border-border/60 bg-background/60 p-4">
                  <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                    Valor sugerido
                  </p>
                  <p className="mt-2 text-sm font-medium">
                    {formatCurrency(liquidarState.row.valor_total)}
                  </p>
                </div>
              </div>

              <div className="space-y-2">
                <Label>Anexos da liquidação *</Label>
                <FileUploadDropzone
                  accept={comprovanteAccept}
                  maxSize={10 * 1024 * 1024}
                  files={liquidarState.comprovantes}
                  multiple
                  onUploadMany={(files) =>
                    setLiquidarState((current) =>
                      current ? { ...current, comprovantes: files } : current,
                    )
                  }
                  isProcessing={false}
                />
                {liquidarState.comprovantes.length ? (
                  <div className="space-y-1 text-sm text-emerald-300">
                    <p>{liquidarState.comprovantes.length} anexo(s) pronto(s) para envio.</p>
                    {liquidarState.comprovantes.slice(0, 3).map((arquivo) => (
                      <p key={`${arquivo.name}-${arquivo.size}`}>{arquivo.name}</p>
                    ))}
                  </div>
                ) : null}
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label>Data da liquidação *</Label>
                  <Input
                    type="date"
                    value={liquidarState.dataLiquidacao}
                    onChange={(event) =>
                      setLiquidarState((current) =>
                        current ? { ...current, dataLiquidacao: event.target.value } : current,
                      )
                    }
                    className="rounded-2xl border-border/60 bg-background/60"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Valor total *</Label>
                  <Input
                    type="number"
                    min="0"
                    step="0.01"
                    value={liquidarState.valorTotal}
                    onChange={(event) =>
                      setLiquidarState((current) =>
                        current ? { ...current, valorTotal: event.target.value } : current,
                      )
                    }
                    className="rounded-2xl border-border/60 bg-background/60"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label>Observação *</Label>
                <Textarea
                  value={liquidarState.observacao}
                  onChange={(event) =>
                    setLiquidarState((current) =>
                      current ? { ...current, observacao: event.target.value } : current,
                    )
                  }
                  className="min-h-24"
                  placeholder="Descreva o encerramento e o contexto da liquidação..."
                />
              </div>
            </div>
          ) : null}
          <DialogFooter>
            <Button variant="outline" onClick={() => setLiquidarState(null)}>
              Cancelar
            </Button>
            <Button
              variant="success"
              disabled={
                liquidarMutation.isPending ||
                !liquidarState?.comprovantes.length ||
                !liquidarState.dataLiquidacao ||
                !liquidarState.valorTotal ||
                !liquidarState.observacao.trim()
              }
              onClick={() => {
                if (!liquidarState?.comprovantes.length) {
                  toast.error("Envie pelo menos um anexo da liquidação.");
                  return;
                }
                liquidarMutation.mutate(liquidarState);
              }}
            >
              Liquidar contrato
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={!!reverterTarget}
        onOpenChange={(open) => {
          if (!open) {
            setReverterTarget(null);
            setMotivoReversao("");
          }
        }}
      >
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Reverter liquidação</DialogTitle>
            <DialogDescription>
              {reverterTarget ? (
                <>
                  <strong>{reverterTarget.nome}</strong> · {reverterTarget.contrato_codigo}
                </>
              ) : null}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <Label>Motivo da reversão *</Label>
            <Textarea
              value={motivoReversao}
              onChange={(event) => setMotivoReversao(event.target.value)}
              className="min-h-24"
              placeholder="Explique por que a liquidação precisa ser revertida..."
            />
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setReverterTarget(null);
                setMotivoReversao("");
              }}
            >
              Cancelar
            </Button>
            <Button
              disabled={reverterMutation.isPending || !motivoReversao.trim()}
              onClick={() => {
                if (!reverterTarget) {
                  return;
                }
                reverterMutation.mutate({
                  contratoId: reverterTarget.contrato_id,
                  motivo: motivoReversao,
                });
              }}
            >
              Confirmar reversão
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
