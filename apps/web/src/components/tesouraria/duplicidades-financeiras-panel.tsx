"use client";

import * as React from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { XCircleIcon } from "lucide-react";
import { toast } from "sonner";

import type {
  DuplicidadeFinanceiraItem,
  DuplicidadeFinanceiraKpis,
  PaginatedResponse,
  SimpleUser,
} from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import { decimalToCents, formatCurrency, formatMonthYear } from "@/lib/formatters";
import CalendarCompetencia from "@/components/custom/calendar-competencia";
import DatePicker from "@/components/custom/date-picker";
import FileUploadDropzone from "@/components/custom/file-upload-dropzone";
import InputCurrency from "@/components/custom/input-currency";
import SearchableSelect from "@/components/custom/searchable-select";
import StatusBadge from "@/components/custom/status-badge";
import DataTable, { type DataTableColumn } from "@/components/shared/data-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
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
import { Textarea } from "@/components/ui/textarea";

const COMPROVANTE_ACCEPT = {
  "application/pdf": [".pdf"],
  "image/png": [".png"],
  "image/jpeg": [".jpg", ".jpeg"],
};

type DuplicidadeResponse = PaginatedResponse<DuplicidadeFinanceiraItem> & {
  kpis: DuplicidadeFinanceiraKpis;
};

type ResolveState = {
  row: DuplicidadeFinanceiraItem;
  dataDevolucao?: Date;
  valor: number | null;
  motivo: string;
  comprovantes: File[];
};

type DuplicidadesFinanceirasPanelProps = {
  arquivoRetornoId?: number;
  contextBadge?: string;
  emptyMessage?: string;
};

function totalPages(count?: number, pageSize = 10) {
  return Math.max(1, Math.ceil((count ?? 0) / pageSize));
}

export default function DuplicidadesFinanceirasPanel({
  arquivoRetornoId,
  contextBadge,
  emptyMessage = "Nenhuma duplicidade financeira encontrada.",
}: DuplicidadesFinanceirasPanelProps) {
  const queryClient = useQueryClient();
  const [page, setPage] = React.useState(1);
  const [search, setSearch] = React.useState("");
  const [status, setStatus] = React.useState("todos");
  const [motivo, setMotivo] = React.useState("todos");
  const [competencia, setCompetencia] = React.useState<Date | undefined>();
  const [agenteId, setAgenteId] = React.useState("");
  const [resolveState, setResolveState] = React.useState<ResolveState | null>(null);
  const [discardRow, setDiscardRow] = React.useState<DuplicidadeFinanceiraItem | null>(null);
  const [discardReason, setDiscardReason] = React.useState("");

  const agentesQuery = useQuery({
    queryKey: ["importacao-duplicidades-agentes"],
    queryFn: () => apiFetch<SimpleUser[]>("associados/agentes"),
    staleTime: 5 * 60 * 1000,
  });

  const agenteFiltro = React.useMemo(() => {
    if (!agenteId) {
      return undefined;
    }
    const match = (agentesQuery.data ?? []).find((item) => String(item.id) === agenteId);
    return match?.full_name || agenteId;
  }, [agenteId, agentesQuery.data]);

  const duplicidadesQuery = useQuery({
    queryKey: [
      "importacao-duplicidades-financeiras",
      arquivoRetornoId ?? "all",
      page,
      search,
      status,
      motivo,
      competencia?.toISOString(),
      agenteFiltro,
    ],
    queryFn: () =>
      apiFetch<DuplicidadeResponse>("importacao/duplicidades-financeiras", {
        query: {
          page,
          page_size: 10,
          search: search || undefined,
          status: status !== "todos" ? status : undefined,
          motivo: motivo !== "todos" ? motivo : undefined,
          competencia: competencia
            ? `${competencia.getFullYear()}-${String(competencia.getMonth() + 1).padStart(2, "0")}`
            : undefined,
          agente: agenteFiltro,
          arquivo_retorno_id: arquivoRetornoId,
        },
      }),
  });

  React.useEffect(() => {
    setPage(1);
  }, [arquivoRetornoId, search, status, motivo, competencia, agenteFiltro]);

  const invalidateDuplicidades = React.useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ["importacao-duplicidades-financeiras"] });
    void queryClient.invalidateQueries({ queryKey: ["tesouraria-devolucoes"] });
    void queryClient.invalidateQueries({ queryKey: ["tesouraria-duplicidades-sidebar"] });
  }, [queryClient]);

  const resolverDuplicidadeMutation = useMutation({
    mutationFn: async (payload: ResolveState) => {
      const formData = new FormData();
      formData.append(
        "data_devolucao",
        `${payload.dataDevolucao?.getFullYear()}-${String((payload.dataDevolucao?.getMonth() ?? 0) + 1).padStart(2, "0")}-${String(payload.dataDevolucao?.getDate() ?? 1).padStart(2, "0")}`,
      );
      formData.append("valor", ((payload.valor ?? 0) / 100).toFixed(2));
      formData.append("motivo", payload.motivo);
      payload.comprovantes.forEach((arquivo) => {
        formData.append("comprovantes", arquivo);
      });
      return apiFetch<DuplicidadeFinanceiraItem>(
        `importacao/duplicidades-financeiras/${payload.row.id}/resolver-devolucao`,
        {
          method: "POST",
          formData,
        },
      );
    },
    onSuccess: () => {
      toast.success("Duplicidade encaminhada para devolução.");
      setResolveState(null);
      invalidateDuplicidades();
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : "Não foi possível resolver a duplicidade.",
      );
    },
  });

  const descartarDuplicidadeMutation = useMutation({
    mutationFn: async ({ row, motivo }: { row: DuplicidadeFinanceiraItem; motivo: string }) =>
      apiFetch<DuplicidadeFinanceiraItem>(`importacao/duplicidades-financeiras/${row.id}/descartar`, {
        method: "POST",
        body: { motivo },
      }),
    onSuccess: () => {
      toast.success("Duplicidade descartada.");
      setDiscardRow(null);
      setDiscardReason("");
      invalidateDuplicidades();
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : "Não foi possível descartar a duplicidade.",
      );
    },
  });

  const rows = duplicidadesQuery.data?.results ?? [];
  const kpis = duplicidadesQuery.data?.kpis;
  const pages = totalPages(duplicidadesQuery.data?.count, 10);
  const agentOptions = (agentesQuery.data ?? []).map((item) => ({
    value: String(item.id),
    label: item.full_name,
  }));

  const columns = React.useMemo<DataTableColumn<DuplicidadeFinanceiraItem>[]>(
    () => [
      {
        id: "servidor",
        header: "Servidor",
        cell: (row) => (
          <div>
            <p className="font-medium text-foreground">{row.nome}</p>
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
            <p className="font-medium text-foreground">{row.contrato_codigo || "Sem contrato"}</p>
            <p className="text-xs text-muted-foreground">{row.agente_nome || "Sem agente"}</p>
          </div>
        ),
      },
      {
        id: "competencias",
        header: "Competências",
        cell: (row) => (
          <div className="space-y-1 text-sm">
            <p>Retorno: {formatMonthYear(row.competencia_retorno)}</p>
            <p className="text-muted-foreground">
              Manual: {row.competencia_manual ? formatMonthYear(row.competencia_manual) : "Sem baixa manual"}
            </p>
          </div>
        ),
      },
      {
        id: "valores",
        header: "Valores",
        cell: (row) => (
          <div className="space-y-1 text-sm">
            <p>Retorno {formatCurrency(row.valor_retorno)}</p>
            <p className="text-muted-foreground">Manual {formatCurrency(row.valor_manual)}</p>
          </div>
        ),
      },
      {
        id: "status",
        header: "Motivo / Status",
        cell: (row) => (
          <div className="space-y-2">
            <p className="text-sm font-medium capitalize text-foreground">
              {row.motivo.replaceAll("_", " ")}
            </p>
            <StatusBadge status={row.status} />
          </div>
        ),
      },
      {
        id: "acoes",
        header: "Ações",
        cellClassName: "w-[320px]",
        cell: (row) => (
          <div className="flex flex-wrap gap-2">
            {row.associado_id ? (
              <Button asChild size="sm" variant="outline">
                <Link href={`/associados/${row.associado_id}`}>Ver cadastro</Link>
              </Button>
            ) : null}
            {row.status !== "resolvida" && row.status !== "descartada" ? (
              <>
                <Button
                  size="sm"
                  onClick={() =>
                    setResolveState({
                      row,
                      dataDevolucao: new Date(),
                      valor: decimalToCents(row.valor_retorno ?? row.valor_manual ?? "0"),
                      motivo: "",
                      comprovantes: [],
                    })
                  }
                >
                  Resolver com devolução
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    setDiscardRow(row);
                    setDiscardReason("");
                  }}
                >
                  <XCircleIcon className="size-4" />
                  Descartar
                </Button>
              </>
            ) : null}
          </div>
        ),
      },
    ],
    [],
  );

  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card className="border-border/60 bg-card/70">
          <CardHeader>
            <CardDescription>Total</CardDescription>
            <CardTitle className="text-3xl">{kpis?.total ?? 0}</CardTitle>
          </CardHeader>
        </Card>
        <Card className="border-border/60 bg-card/70">
          <CardHeader>
            <CardDescription>Abertas</CardDescription>
            <CardTitle className="text-3xl">{kpis?.abertas ?? 0}</CardTitle>
          </CardHeader>
        </Card>
        <Card className="border-border/60 bg-card/70">
          <CardHeader>
            <CardDescription>Em tratamento</CardDescription>
            <CardTitle className="text-3xl">{kpis?.em_tratamento ?? 0}</CardTitle>
          </CardHeader>
        </Card>
        <Card className="border-border/60 bg-card/70">
          <CardHeader>
            <CardDescription>Resolvidas / descartadas</CardDescription>
            <CardTitle className="text-3xl">
              {(kpis?.resolvidas ?? 0) + (kpis?.descartadas ?? 0)}
            </CardTitle>
          </CardHeader>
        </Card>
      </div>

      <div className="grid gap-3 rounded-[1.75rem] border border-border/60 bg-card/50 p-4 xl:grid-cols-[minmax(0,1fr)_220px_220px_220px]">
        <div className="relative">
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Buscar por nome, CPF, matrícula ou contrato"
            className="h-11 rounded-2xl border-border/60 bg-card/60"
          />
        </div>
        <SearchableSelect
          options={agentOptions}
          value={agenteId}
          onChange={setAgenteId}
          placeholder="Todos os agentes"
          searchPlaceholder="Buscar agente"
          clearLabel="Limpar agente"
        />
        <Select value={status} onValueChange={setStatus}>
          <SelectTrigger className="h-11 rounded-2xl border-border/60 bg-card/60">
            <SelectValue placeholder="Todos os status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="todos">Todos os status</SelectItem>
            <SelectItem value="aberta">Aberta</SelectItem>
            <SelectItem value="em_tratamento">Em tratamento</SelectItem>
            <SelectItem value="resolvida">Resolvida</SelectItem>
            <SelectItem value="descartada">Descartada</SelectItem>
          </SelectContent>
        </Select>
        <Select value={motivo} onValueChange={setMotivo}>
          <SelectTrigger className="h-11 rounded-2xl border-border/60 bg-card/60">
            <SelectValue placeholder="Todos os motivos" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="todos">Todos os motivos</SelectItem>
            <SelectItem value="baixa_manual_duplicada">Baixa manual duplicada</SelectItem>
            <SelectItem value="baixa_manual_mes_errado">Baixa manual em mês errado</SelectItem>
            <SelectItem value="divergencia_valor">Divergência de valor</SelectItem>
            <SelectItem value="conflito_retorno">Conflito vindo do retorno</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-[1.75rem] border border-border/60 bg-card/50 p-4">
        <div className="w-full max-w-xs">
          <Label>Competência</Label>
          <CalendarCompetencia
            value={competencia}
            onChange={setCompetencia}
            className="mt-2 rounded-2xl bg-card/60"
          />
        </div>
        <div className="flex flex-wrap gap-2 self-end">
          <Button
            variant="outline"
            onClick={() => {
              setSearch("");
              setStatus("todos");
              setMotivo("todos");
              setCompetencia(undefined);
              setAgenteId("");
            }}
          >
            Limpar
          </Button>
          {contextBadge ? <Badge variant="outline">{contextBadge}</Badge> : null}
        </div>
      </div>

      <DataTable
        columns={columns}
        data={rows}
        currentPage={page}
        totalPages={pages}
        onPageChange={setPage}
        pageSize={10}
        loading={duplicidadesQuery.isLoading}
        emptyMessage={emptyMessage}
      />

      <Dialog open={!!resolveState} onOpenChange={(open) => !open && setResolveState(null)}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>Resolver duplicidade com devolução</DialogTitle>
            <DialogDescription>
              Abra a devolução já vinculada ao conflito financeiro detectado na importação.
            </DialogDescription>
          </DialogHeader>

          {resolveState ? (
            <div className="space-y-5">
              <div className="rounded-2xl border border-border/60 bg-card/50 p-4">
                <p className="font-medium">{resolveState.row.nome}</p>
                <p className="text-sm text-muted-foreground">
                  Linha {resolveState.row.linha_numero} · {resolveState.row.arquivo_nome}
                </p>
                <p className="mt-2 text-sm text-muted-foreground">
                  Motivo {resolveState.row.motivo.replaceAll("_", " ")} · retorno{" "}
                  {formatCurrency(resolveState.row.valor_retorno)} · manual{" "}
                  {formatCurrency(resolveState.row.valor_manual)}
                </p>
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label>Data da devolução</Label>
                  <DatePicker
                    value={resolveState.dataDevolucao}
                    onChange={(date) =>
                      setResolveState((current) =>
                        current ? { ...current, dataDevolucao: date } : current,
                      )
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label>Valor</Label>
                  <InputCurrency
                    value={resolveState.valor}
                    onChange={(value) =>
                      setResolveState((current) =>
                        current ? { ...current, valor: value } : current,
                      )
                    }
                    placeholder="R$ 0,00"
                    className="h-11 rounded-xl border-border/60 bg-card/60"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label>Motivo</Label>
                <Textarea
                  value={resolveState.motivo}
                  onChange={(event) =>
                    setResolveState((current) =>
                      current ? { ...current, motivo: event.target.value } : current,
                    )
                  }
                  className="min-h-28 rounded-2xl border-border/60 bg-card/60"
                  placeholder="Descreva a devolução que será aberta a partir da duplicidade."
                />
              </div>

              <div className="space-y-2">
                <Label>Comprovantes</Label>
                <FileUploadDropzone
                  accept={COMPROVANTE_ACCEPT}
                  files={resolveState.comprovantes}
                  multiple
                  onUploadMany={(files) =>
                    setResolveState((current) =>
                      current ? { ...current, comprovantes: files } : current,
                    )
                  }
                  emptyTitle="Anexar comprovantes da devolução"
                  emptyDescription="PDF, JPG ou PNG com até 10 MB por arquivo"
                />
              </div>
            </div>
          ) : null}

          <DialogFooter>
            <Button variant="outline" onClick={() => setResolveState(null)}>
              Cancelar
            </Button>
            <Button
              disabled={
                !resolveState?.dataDevolucao ||
                !resolveState?.valor ||
                !resolveState.motivo.trim() ||
                !resolveState.comprovantes.length ||
                resolverDuplicidadeMutation.isPending
              }
              onClick={() => resolveState && resolverDuplicidadeMutation.mutate(resolveState)}
            >
              {resolverDuplicidadeMutation.isPending ? "Salvando..." : "Abrir devolução"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!discardRow} onOpenChange={(open) => !open && setDiscardRow(null)}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Descartar duplicidade</DialogTitle>
            <DialogDescription>
              Use apenas quando o conflito financeiro já estiver tratado por outro fluxo.
            </DialogDescription>
          </DialogHeader>

          {discardRow ? (
            <div className="space-y-4">
              <div className="rounded-2xl border border-border/60 bg-card/50 p-4 text-sm">
                <p className="font-medium">{discardRow.nome}</p>
                <p className="text-muted-foreground">
                  {discardRow.contrato_codigo || "Sem contrato"} ·{" "}
                  {formatMonthYear(discardRow.competencia_retorno)}
                </p>
              </div>
              <div className="space-y-2">
                <Label>Motivo do descarte</Label>
                <Textarea
                  value={discardReason}
                  onChange={(event) => setDiscardReason(event.target.value)}
                  className="min-h-28 rounded-2xl border-border/60 bg-card/60"
                  placeholder="Descreva por que a duplicidade está sendo descartada."
                />
              </div>
            </div>
          ) : null}

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setDiscardRow(null);
                setDiscardReason("");
              }}
            >
              Cancelar
            </Button>
            <Button
              variant="outline"
              disabled={!discardRow || !discardReason.trim() || descartarDuplicidadeMutation.isPending}
              onClick={() =>
                discardRow &&
                descartarDuplicidadeMutation.mutate({
                  row: discardRow,
                  motivo: discardReason,
                })
              }
            >
              {descartarDuplicidadeMutation.isPending ? "Salvando..." : "Descartar caso"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
