"use client";

import * as React from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  EyeIcon,
  PrinterIcon,
  SlidersHorizontalIcon,
} from "lucide-react";
import { toast } from "sonner";

import type { PaginatedResponse, RefinanciamentoItem } from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import { formatMonthYear } from "@/lib/formatters";
import { RefinanciamentoDetalhesDialog } from "@/components/refinanciamento/refinanciamento-detalhes-dialog";
import MultiSelect from "@/components/custom/multi-select";
import SearchableSelect, { type SelectOption } from "@/components/custom/searchable-select";
import StatusBadge from "@/components/custom/status-badge";
import CopySnippet from "@/components/shared/copy-snippet";
import DataTable, { type DataTableColumn } from "@/components/shared/data-table";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
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
  Sheet,
  SheetContent,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";

type DialogState =
  | { mode: "aprovar"; item: RefinanciamentoItem }
  | null;

type CoordAdvancedFilters = {
  year: string;
  competenciaStart: string;
  competenciaEnd: string;
  agent: string;
  statuses: string[];
  origins: string[];
  eligibilityBand: string;
};

type BulkApproveResponse = {
  success_count: number;
  failure_count: number;
  results: Array<{
    id: number;
    status: "sucesso" | "falha";
    motivo: string;
  }>;
};

const STATUS_OPTIONS: SelectOption[] = [
  {
    value: "aprovado_analise_renovacao",
    label: "Aguardando validação da coordenação",
  },
  { value: "aprovado_para_renovacao", label: "Enviado para tesouraria" },
  { value: "bloqueado", label: "Bloqueado" },
  { value: "revertido", label: "Revertido" },
];

const ORIGIN_OPTIONS: SelectOption[] = [
  { value: "legado", label: "Legado" },
  { value: "operacional", label: "Operacional" },
];

const ELIGIBILITY_OPTIONS: SelectOption[] = [
  { value: "", label: "Todas as faixas" },
  { value: "2_3", label: "2/3" },
  { value: "3_3", label: "3/3" },
  { value: "3_4", label: "3/4" },
  { value: "4_4", label: "4/4" },
];

const INITIAL_FILTERS: CoordAdvancedFilters = {
  year: String(new Date().getFullYear()),
  competenciaStart: "",
  competenciaEnd: "",
  agent: "",
  statuses: [],
  origins: [],
  eligibilityBand: "",
};

function countActiveFilters(filters: CoordAdvancedFilters) {
  return [
    filters.year && filters.year !== INITIAL_FILTERS.year ? filters.year : "",
    filters.competenciaStart,
    filters.competenciaEnd,
    filters.agent,
    filters.statuses.length ? "status" : "",
    filters.origins.length ? "origem" : "",
    filters.eligibilityBand,
  ].filter(Boolean).length;
}

function toCompetenciaDate(value: string) {
  return value ? `${value}-01` : undefined;
}

function isBulkEligible(item: RefinanciamentoItem) {
  return item.status === "aprovado_analise_renovacao";
}

export default function CoordenacaoRefinanciamentoPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = React.useState(1);
  const [search, setSearch] = React.useState("");
  const [sheetOpen, setSheetOpen] = React.useState(false);
  const [filters, setFilters] = React.useState<CoordAdvancedFilters>(INITIAL_FILTERS);
  const [draftFilters, setDraftFilters] = React.useState<CoordAdvancedFilters>(INITIAL_FILTERS);
  const [dialogState, setDialogState] = React.useState<DialogState>(null);
  const [observacao, setObservacao] = React.useState("");
  const [selectedIds, setSelectedIds] = React.useState<number[]>([]);
  const [bulkDialogOpen, setBulkDialogOpen] = React.useState(false);
  const [bulkConfirmText, setBulkConfirmText] = React.useState("");
  const [detailItem, setDetailItem] = React.useState<RefinanciamentoItem | null>(null);

  const refinanciamentoQuery = useQuery({
    queryKey: [
      "coordenacao-refinanciamento",
      page,
      search,
      filters.year,
      filters.competenciaStart,
      filters.competenciaEnd,
      filters.agent,
      filters.statuses.join(","),
      filters.origins.join(","),
      filters.eligibilityBand,
    ],
    queryFn: () =>
      apiFetch<PaginatedResponse<RefinanciamentoItem>>("coordenacao/refinanciamento", {
        query: {
          page,
          page_size: 20,
          search: search || undefined,
          year: filters.year || undefined,
          competencia_start: toCompetenciaDate(filters.competenciaStart),
          competencia_end: toCompetenciaDate(filters.competenciaEnd),
          agent: filters.agent || undefined,
          status: filters.statuses,
          origem: filters.origins,
          eligibility_band: filters.eligibilityBand || undefined,
        },
      }),
  });

  const actionMutation = useMutation({
    mutationFn: async ({
      id,
      body,
    }: {
      id: number;
      body?: Record<string, string>;
    }) =>
      apiFetch<RefinanciamentoItem>(`refinanciamentos/${id}/aprovar`, {
        method: "POST",
        body,
      }),
    onSuccess: () => {
      toast.success("Ação de coordenação concluída.");
      setDialogState(null);
      setObservacao("");
      void queryClient.invalidateQueries({ queryKey: ["coordenacao-refinanciamento"] });
      void queryClient.invalidateQueries({ queryKey: ["coordenacao-refinanciados"] });
      void queryClient.invalidateQueries({ queryKey: ["analise-refinanciamentos"] });
      void queryClient.invalidateQueries({ queryKey: ["agente-refinanciados"] });
      void queryClient.invalidateQueries({ queryKey: ["tesouraria-refinanciamentos"] });
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Falha ao processar refinanciamento.");
    },
  });

  const bulkApproveMutation = useMutation({
    mutationFn: async (ids: number[]) =>
      apiFetch<BulkApproveResponse>("coordenacao/refinanciamento/aprovar_em_massa", {
        method: "POST",
        body: {
          ids,
          confirm_text: bulkConfirmText,
        },
      }),
    onSuccess: (payload) => {
      const failureSummary = payload.results
        .filter((item) => item.status === "falha")
        .slice(0, 3)
        .map((item) => item.motivo)
        .filter(Boolean);
      if (payload.failure_count > 0) {
        toast.error(
          `${payload.success_count} validações concluídas e ${payload.failure_count} falhas.`,
          {
            description: failureSummary.join(" | ") || "Algumas linhas mudaram de status.",
          },
        );
      } else {
        toast.success(`${payload.success_count} renovações enviadas para tesouraria.`);
      }
      setBulkDialogOpen(false);
      setBulkConfirmText("");
      setSelectedIds([]);
      void queryClient.invalidateQueries({ queryKey: ["coordenacao-refinanciamento"] });
      void queryClient.invalidateQueries({ queryKey: ["analise-refinanciamentos"] });
      void queryClient.invalidateQueries({ queryKey: ["coordenacao-refinanciados"] });
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Falha ao aprovar em massa.");
    },
  });

  const rows = refinanciamentoQuery.data?.results ?? [];
  const totalCount = refinanciamentoQuery.data?.count ?? 0;
  const aptos = rows.filter(isBulkEligible).length;
  const selectableRows = rows.filter(isBulkEligible);
  const allSelected =
    selectableRows.length > 0 &&
    selectableRows.every((item) => selectedIds.includes(item.id));
  const someSelected = selectableRows.some((item) => selectedIds.includes(item.id)) && !allSelected;
  const activeAdvancedFiltersCount = countActiveFilters(filters);

  React.useEffect(() => {
    setSelectedIds([]);
  }, [
    page,
    search,
    filters.year,
    filters.competenciaStart,
    filters.competenciaEnd,
    filters.agent,
    filters.statuses.join(","),
    filters.origins.join(","),
    filters.eligibilityBand,
    rows.map((row) => row.id).join(","),
  ]);

  const toggleSelection = React.useCallback((id: number, checked: boolean) => {
    setSelectedIds((current) =>
      checked
        ? current.includes(id)
          ? current
          : [...current, id]
        : current.filter((item) => item !== id),
    );
  }, []);

  const columns = React.useMemo<DataTableColumn<RefinanciamentoItem>[]>(
    () => [
      {
        id: "select",
        header: (
          <Checkbox
            checked={allSelected ? true : someSelected ? "indeterminate" : false}
            onCheckedChange={(checked) => {
              const shouldSelect = checked === true;
              setSelectedIds(shouldSelect ? selectableRows.map((item) => item.id) : []);
            }}
            aria-label="Selecionar página atual"
          />
        ),
        cell: (row) => (
          <Checkbox
            checked={selectedIds.includes(row.id)}
            disabled={!isBulkEligible(row)}
            aria-label={`Selecionar ${row.associado_nome}`}
            onCheckedChange={(checked) => toggleSelection(row.id, checked === true)}
          />
        ),
        headerClassName: "w-12",
        cellClassName: "w-12",
      },
      {
        id: "agente",
        header: "Agente",
        cell: (row) => row.agente?.full_name ?? "—",
      },
      {
        id: "associado",
        header: "Associado",
        cell: (row) => (
          <div className="space-y-1">
            <p className="font-medium">{row.associado_nome}</p>
            <CopySnippet label="CPF" value={row.cpf_cnpj} mono inline />
          </div>
        ),
      },
      {
        id: "referencias",
        header: "Referências",
        cell: (row) => (
          <div className="space-y-1">
            {row.referencias.map((referencia) => (
              <p key={referencia}>{formatMonthYear(referencia)}</p>
            ))}
          </div>
        ),
      },
      {
        id: "mensalidades",
        header: "Mensalidades",
        cell: (row) => `${row.mensalidades_pagas}/${row.mensalidades_total}`,
      },
      {
        id: "motivo",
        header: "Motivo",
        cell: (row) => (
          <p className="max-w-sm text-sm text-muted-foreground">
            {row.motivo_apto_renovacao}
          </p>
        ),
      },
      {
        id: "refin",
        header: "Refinanciamento",
        cell: (row) => (
          <Badge className="rounded-full bg-sky-500/15 text-sky-200">
            {row.refinanciamento_numero}
          </Badge>
        ),
      },
      {
        id: "acao",
        header: "Ações",
        cell: (row) =>
          row.status !== "aprovado_analise_renovacao" ? (
            <div className="space-y-2">
              <div className="flex flex-wrap gap-2">
                <Button size="sm" variant="outline" onClick={() => setDetailItem(row)}>
                  <EyeIcon className="size-4" />
                  Detalhes
                </Button>
                <StatusBadge status={row.status} />
              </div>
              <p className="text-xs text-muted-foreground">
                {row.coordenador_note || row.motivo_bloqueio || "Sem observação registrada."}
              </p>
            </div>
          ) : (
            <div className="flex flex-wrap gap-2">
              <Button size="sm" variant="outline" onClick={() => setDetailItem(row)}>
                <EyeIcon className="size-4" />
                Detalhes
              </Button>
              <Button size="sm" onClick={() => setDialogState({ mode: "aprovar", item: row })}>
                Aprovar e enviar para tesouraria
              </Button>
              <Button asChild size="sm" variant="outline">
                <Link
                  href={`/tesouraria/liquidacoes?status=elegivel&contrato=${row.contrato_id}&origem=renovacao&refinanciamento=${row.id}`}
                >
                  Liquidar contrato
                </Link>
              </Button>
            </div>
          ),
      },
    ],
    [allSelected, selectableRows, selectedIds, someSelected, toggleSelection],
  );

  return (
    <div className="space-y-6">
      <section className="rounded-[1.75rem] border border-border/60 bg-card/70 p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-2">
            <div className="flex flex-wrap gap-2">
              <Button asChild variant="outline">
                <Link href="/coordenacao/refinanciados">Refinanciados</Link>
              </Button>
              <Button asChild>
                <Link href="/coordenacao/refinanciamento">Refinanciamento</Link>
              </Button>
            </div>
            <h1 className="text-3xl font-semibold">Refinanciamento em aprovação</h1>
            <p className="text-sm text-muted-foreground">
              Fila de coordenação para renovações já aprovadas pelo analista. Total: {totalCount} | Pendentes de validação: {aptos}
            </p>
          </div>
          <Button variant="outline" onClick={() => window.print()}>
            <PrinterIcon className="size-4" />
            Imprimir / PDF
          </Button>
        </div>
      </section>

      <section className="grid gap-3 rounded-[1.75rem] border border-border/60 bg-card/50 p-4 lg:grid-cols-[minmax(0,1fr)_auto]">
        <Input
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
            setPage(1);
          }}
          placeholder="Buscar por associado, CPF ou agente"
          className="rounded-2xl border-border/60 bg-card/60"
        />
        <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
          <SheetTrigger asChild>
            <Button variant="outline" className="rounded-2xl">
              <SlidersHorizontalIcon className="size-4" />
              Filtros avançados
              {activeAdvancedFiltersCount ? (
                <Badge className="ml-1 rounded-full bg-primary/15 text-primary">
                  {activeAdvancedFiltersCount}
                </Badge>
              ) : null}
            </Button>
          </SheetTrigger>
          <SheetContent className="w-full border-l border-border/60 bg-background/95 sm:max-w-xl">
            <SheetHeader>
              <SheetTitle>Filtros avançados</SheetTitle>
            </SheetHeader>
            <div className="mt-8 space-y-6">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <p className="text-sm font-medium">Ano</p>
                  <Input
                    value={draftFilters.year}
                    onChange={(event) =>
                      setDraftFilters((current) => ({
                        ...current,
                        year: event.target.value,
                      }))
                    }
                    placeholder="2026"
                  />
                </div>
                <div className="space-y-2">
                  <p className="text-sm font-medium">Agente</p>
                  <Input
                    value={draftFilters.agent}
                    onChange={(event) =>
                      setDraftFilters((current) => ({
                        ...current,
                        agent: event.target.value,
                      }))
                    }
                    placeholder="Nome do agente"
                  />
                </div>
                <div className="space-y-2">
                  <p className="text-sm font-medium">Competência inicial</p>
                  <Input
                    type="month"
                    value={draftFilters.competenciaStart}
                    onChange={(event) =>
                      setDraftFilters((current) => ({
                        ...current,
                        competenciaStart: event.target.value,
                      }))
                    }
                  />
                </div>
                <div className="space-y-2">
                  <p className="text-sm font-medium">Competência final</p>
                  <Input
                    type="month"
                    value={draftFilters.competenciaEnd}
                    onChange={(event) =>
                      setDraftFilters((current) => ({
                        ...current,
                        competenciaEnd: event.target.value,
                      }))
                    }
                  />
                </div>
              </div>

              <div className="space-y-2">
                <p className="text-sm font-medium">Status</p>
                <MultiSelect
                  options={STATUS_OPTIONS}
                  value={draftFilters.statuses}
                  onChange={(statuses) =>
                    setDraftFilters((current) => ({ ...current, statuses }))
                  }
                  placeholder="Todos os status"
                />
              </div>

              <div className="space-y-2">
                <p className="text-sm font-medium">Origem</p>
                <MultiSelect
                  options={ORIGIN_OPTIONS}
                  value={draftFilters.origins}
                  onChange={(origins) =>
                    setDraftFilters((current) => ({ ...current, origins }))
                  }
                  placeholder="Todas as origens"
                />
              </div>

              <div className="space-y-2">
                <p className="text-sm font-medium">Faixa de elegibilidade</p>
                <SearchableSelect
                  options={ELIGIBILITY_OPTIONS}
                  value={draftFilters.eligibilityBand}
                  onChange={(eligibilityBand) =>
                    setDraftFilters((current) => ({ ...current, eligibilityBand }))
                  }
                  placeholder="Todas as faixas"
                  clearValue=""
                />
              </div>
            </div>
            <SheetFooter className="mt-8 flex-row gap-3 sm:justify-between">
              <Button
                variant="outline"
                onClick={() => {
                  setDraftFilters(INITIAL_FILTERS);
                  setFilters(INITIAL_FILTERS);
                  setPage(1);
                  setSheetOpen(false);
                }}
              >
                Limpar filtros
              </Button>
              <Button
                onClick={() => {
                  setFilters(draftFilters);
                  setPage(1);
                  setSheetOpen(false);
                }}
              >
                Aplicar filtros
              </Button>
            </SheetFooter>
          </SheetContent>
        </Sheet>
      </section>

      {selectedIds.length ? (
        <section className="flex flex-col gap-3 rounded-[1.5rem] border border-primary/30 bg-primary/5 p-4 lg:flex-row lg:items-center lg:justify-between">
          <p className="text-sm text-foreground">
            {selectedIds.length} {selectedIds.length === 1 ? "linha selecionada" : "linhas selecionadas"} na página atual.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => setSelectedIds([])}>
              Limpar seleção
            </Button>
            <Button onClick={() => setBulkDialogOpen(true)}>
              Enviar em massa para tesouraria
            </Button>
          </div>
        </section>
      ) : null}

      <DataTable
        data={rows}
        columns={columns}
        currentPage={page}
        totalPages={Math.max(1, Math.ceil(totalCount / 20))}
        onPageChange={setPage}
        emptyMessage="Nenhuma solicitação pendente para coordenação."
        loading={refinanciamentoQuery.isLoading}
        skeletonRows={6}
      />

      <Dialog open={!!dialogState} onOpenChange={(open) => !open && setDialogState(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Aprovar renovação</DialogTitle>
            <DialogDescription>
              A coordenação valida os anexos do agente e envia a renovação para a tesouraria.
            </DialogDescription>
          </DialogHeader>

          <Input
            value={observacao}
            onChange={(event) => setObservacao(event.target.value)}
            placeholder="Observação da coordenação (opcional)"
          />

          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogState(null)}>
              Cancelar
            </Button>
            <Button
              onClick={() => {
                if (!dialogState) return;
                actionMutation.mutate({
                  id: dialogState.item.id,
                  body: observacao.trim() ? { observacao } : undefined,
                });
              }}
              disabled={actionMutation.isPending}
            >
              Confirmar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={bulkDialogOpen} onOpenChange={setBulkDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Enviar renovações para tesouraria</AlertDialogTitle>
            <AlertDialogDescription>
              Esta ação é sensível e valida apenas as linhas selecionadas da página atual.
              Digite <strong>CONFIRMAR</strong> para continuar.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Selecionados: {selectedIds.length}
            </p>
            <Input
              value={bulkConfirmText}
              onChange={(event) => setBulkConfirmText(event.target.value)}
              placeholder="Digite CONFIRMAR"
            />
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel
              onClick={() => {
                setBulkConfirmText("");
              }}
            >
              Cancelar
            </AlertDialogCancel>
            <AlertDialogAction
              disabled={bulkConfirmText.trim().toUpperCase() !== "CONFIRMAR" || bulkApproveMutation.isPending}
              onClick={(event) => {
                event.preventDefault();
                bulkApproveMutation.mutate(selectedIds);
              }}
            >
              Confirmar envio em massa
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <RefinanciamentoDetalhesDialog
        open={!!detailItem}
        associadoId={detailItem?.associado_id ?? null}
        refinanciamentoId={detailItem?.id ?? null}
        onOpenChange={(open) => {
          if (!open) {
            setDetailItem(null);
          }
        }}
      />
    </div>
  );
}
