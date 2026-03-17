"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { EyeIcon, FileTextIcon, PlayIcon, SlidersHorizontalIcon } from "lucide-react";
import { toast } from "sonner";

import type { PaginatedResponse, RefinanciamentoItem } from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import { formatMonthYear } from "@/lib/formatters";
import { RefinanciamentoDetalhesDialog } from "@/components/refinanciamento/refinanciamento-detalhes-dialog";
import FileUploadDropzone from "@/components/custom/file-upload-dropzone";
import MultiSelect from "@/components/custom/multi-select";
import SearchableSelect, { type SelectOption } from "@/components/custom/searchable-select";
import StatusBadge from "@/components/custom/status-badge";
import CopySnippet from "@/components/shared/copy-snippet";
import DataTable, { type DataTableColumn } from "@/components/shared/data-table";
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
import {
  Sheet,
  SheetContent,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";

const termoAccept = {
  "application/pdf": [".pdf"],
  "image/png": [".png"],
  "image/jpeg": [".jpg", ".jpeg"],
};

type AnaliseAdvancedFilters = {
  competenciaStart: string;
  competenciaEnd: string;
  agent: string;
  statuses: string[];
  origins: string[];
  assignment: string;
};

const STATUS_OPTIONS: SelectOption[] = [
  { value: "em_analise_renovacao", label: "Em análise para renovação" },
  { value: "aprovado_para_renovacao", label: "Aprovado para renovação" },
];

const ORIGIN_OPTIONS: SelectOption[] = [
  { value: "legado", label: "Legado" },
  { value: "operacional", label: "Operacional" },
];

const ASSIGNMENT_OPTIONS: SelectOption[] = [
  { value: "todas", label: "Todas" },
  { value: "minhas", label: "Minhas" },
  { value: "nao_assumidas", label: "Não assumidas" },
];

const INITIAL_FILTERS: AnaliseAdvancedFilters = {
  competenciaStart: "",
  competenciaEnd: "",
  agent: "",
  statuses: [],
  origins: [],
  assignment: "todas",
};

function countActiveFilters(filters: AnaliseAdvancedFilters) {
  return [
    filters.competenciaStart,
    filters.competenciaEnd,
    filters.agent,
    filters.statuses.length ? "status" : "",
    filters.origins.length ? "origem" : "",
    filters.assignment !== "todas" ? filters.assignment : "",
  ].filter(Boolean).length;
}

function toCompetenciaDate(value: string) {
  return value ? `${value}-01` : undefined;
}

export default function AnaliseAptosPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = React.useState(1);
  const [search, setSearch] = React.useState("");
  const [sheetOpen, setSheetOpen] = React.useState(false);
  const [filters, setFilters] = React.useState<AnaliseAdvancedFilters>(INITIAL_FILTERS);
  const [draftFilters, setDraftFilters] = React.useState<AnaliseAdvancedFilters>(INITIAL_FILTERS);
  const [selected, setSelected] = React.useState<RefinanciamentoItem | null>(null);
  const [detailItem, setDetailItem] = React.useState<RefinanciamentoItem | null>(null);
  const [termo, setTermo] = React.useState<File | null>(null);
  const [observacao, setObservacao] = React.useState("");

  const refinanciamentosQuery = useQuery({
    queryKey: [
      "analise-refinanciamentos",
      page,
      search,
      filters.competenciaStart,
      filters.competenciaEnd,
      filters.agent,
      filters.statuses.join(","),
      filters.origins.join(","),
      filters.assignment,
    ],
    queryFn: () =>
      apiFetch<PaginatedResponse<RefinanciamentoItem>>("analise/refinanciamentos", {
        query: {
          page,
          page_size: 20,
          search: search || undefined,
          competencia_start: toCompetenciaDate(filters.competenciaStart),
          competencia_end: toCompetenciaDate(filters.competenciaEnd),
          agent: filters.agent || undefined,
          status: filters.statuses,
          origem: filters.origins,
          assignment: filters.assignment !== "todas" ? filters.assignment : undefined,
        },
      }),
  });

  const assumirMutation = useMutation({
    mutationFn: async (id: number) =>
      apiFetch<RefinanciamentoItem>(`refinanciamentos/${id}/assumir_analise`, {
        method: "POST",
      }),
    onSuccess: () => {
      toast.success("Renovação assumida na análise.");
      void queryClient.invalidateQueries({ queryKey: ["analise-refinanciamentos"] });
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Falha ao assumir renovação.");
    },
  });

  const aprovarMutation = useMutation({
    mutationFn: async ({
      id,
      file,
      note,
    }: {
      id: number;
      file: File;
      note: string;
    }) => {
      const formData = new FormData();
      formData.set("termo_antecipacao", file);
      formData.set("observacao", note);
      return apiFetch<RefinanciamentoItem>(`refinanciamentos/${id}/aprovar_analise`, {
        method: "POST",
        formData,
      });
    },
    onSuccess: () => {
      toast.success("Renovação aprovada pela análise.");
      setSelected(null);
      setTermo(null);
      setObservacao("");
      void queryClient.invalidateQueries({ queryKey: ["analise-refinanciamentos"] });
      void queryClient.invalidateQueries({ queryKey: ["tesouraria-refinanciamentos"] });
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Falha ao aprovar renovação.");
    },
  });

  const rows = refinanciamentosQuery.data?.results ?? [];
  const totalCount = refinanciamentosQuery.data?.count ?? 0;
  const activeAdvancedFiltersCount = countActiveFilters(filters);

  const columns = React.useMemo<DataTableColumn<RefinanciamentoItem>[]>(
    () => [
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
        id: "contrato",
        header: "Contrato",
        cell: (row) => (
          <div className="space-y-1">
            <p>{row.contrato_codigo}</p>
            <p className="text-xs text-muted-foreground">
              {row.referencias.map((item) => formatMonthYear(item)).join(", ")}
            </p>
          </div>
        ),
      },
      {
        id: "status",
        header: "Status",
        cell: (row) => (
          <div className="space-y-1">
            <StatusBadge status={row.status} />
            <p className="text-xs text-muted-foreground">
              {row.mensalidades_pagas}/{row.mensalidades_total} parcelas quitadas
            </p>
          </div>
        ),
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
        id: "origem",
        header: "Origem",
        cell: (row) => (
          <Badge variant="outline" className="rounded-full border-border/60">
            {row.origem.replaceAll("_", " ")}
          </Badge>
        ),
      },
      {
        id: "acoes",
        header: "Ações",
        cell: (row) => (
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="outline" onClick={() => setDetailItem(row)}>
              <EyeIcon className="size-4" />
              Detalhes
            </Button>
            {row.status === "em_analise_renovacao" ? (
              <Button
                size="sm"
                variant="outline"
                onClick={() => assumirMutation.mutate(row.id)}
              >
                <PlayIcon className="size-4" />
                Assumir
              </Button>
            ) : null}
            <Button size="sm" onClick={() => setSelected(row)}>
              <FileTextIcon className="size-4" />
              Anexar termo
            </Button>
          </div>
        ),
      },
    ],
    [assumirMutation],
  );

  return (
    <div className="space-y-6">
      <section className="rounded-[1.75rem] border border-border/60 bg-card/70 p-6">
        <div className="space-y-2">
          <p className="text-sm uppercase tracking-[0.28em] text-muted-foreground">
            Análise
          </p>
          <h1 className="text-3xl font-semibold">Aptos para renovação</h1>
          <p className="text-sm text-muted-foreground">
            Fila do analista para revisar dados, detalhar contratos e anexar o termo de antecipação.
            Total: {totalCount}
          </p>
        </div>
      </section>

      <section className="grid gap-3 rounded-[1.75rem] border border-border/60 bg-card/50 p-4 lg:grid-cols-[minmax(0,1fr)_auto]">
        <Input
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
            setPage(1);
          }}
          placeholder="Buscar por associado, CPF ou contrato"
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
                <div className="space-y-2 md:col-span-2">
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
                <p className="text-sm font-medium">Atribuição</p>
                <SearchableSelect
                  options={ASSIGNMENT_OPTIONS}
                  value={draftFilters.assignment}
                  onChange={(assignment) =>
                    setDraftFilters((current) => ({
                      ...current,
                      assignment: assignment || "todas",
                    }))
                  }
                  placeholder="Todas"
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

      <DataTable
        data={rows}
        columns={columns}
        currentPage={page}
        totalPages={Math.max(1, Math.ceil(totalCount / 20))}
        onPageChange={setPage}
        emptyMessage="Nenhuma renovação disponível para análise."
        loading={refinanciamentosQuery.isLoading}
        skeletonRows={6}
      />

      <Dialog open={!!selected} onOpenChange={(open) => !open && setSelected(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Anexar termo de antecipação</DialogTitle>
            <DialogDescription>
              O termo fica catalogado no ciclo de origem da renovação e não substitui anexos antigos.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <FileUploadDropzone
              accept={termoAccept}
              file={termo}
              onUpload={setTermo}
              emptyTitle="Selecione o termo de antecipação"
            />
            <Textarea
              value={observacao}
              onChange={(event) => setObservacao(event.target.value)}
              placeholder="Observação do analista"
              className="min-h-28"
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setSelected(null)}>
              Cancelar
            </Button>
            <Button
              disabled={!selected || !termo || aprovarMutation.isPending}
              onClick={() => {
                if (!selected || !termo) return;
                aprovarMutation.mutate({
                  id: selected.id,
                  file: termo,
                  note: observacao,
                });
              }}
            >
              Aprovar para tesouraria
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

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
