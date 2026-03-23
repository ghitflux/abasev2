"use client";

import * as React from "react";
import { format } from "date-fns";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2Icon,
  Clock3Icon,
  HandCoinsIcon,
  SlidersHorizontalIcon,
  Trash2Icon,
  XCircleIcon,
} from "lucide-react";
import { toast } from "sonner";

import type {
  PaginatedResponse,
  RefinanciamentoItem,
  RefinanciamentoResumo,
} from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import { buildBackendFileUrl } from "@/lib/backend-files";
import { formatCurrency, formatDateTime, formatMonthYear } from "@/lib/formatters";
import DatePicker from "@/components/custom/date-picker";
import StatusBadge from "@/components/custom/status-badge";
import CopySnippet from "@/components/shared/copy-snippet";
import DataTable, { type DataTableColumn } from "@/components/shared/data-table";
import StatsCard from "@/components/shared/stats-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

type ListingTab = "pendentes" | "efetuadas" | "canceladas";
type DraftMap = Record<number, { associado?: File; agente?: File }>;

const TAB_STATUS_MAP: Record<ListingTab, string[]> = {
  pendentes: ["aprovado_para_renovacao"],
  efetuadas: ["efetivado"],
  canceladas: ["bloqueado", "revertido", "desativado"],
};

function toIsoDate(value?: Date) {
  if (!value) return undefined;
  return format(value, "yyyy-MM-dd");
}

function CompactUploadButton({
  id,
  label,
  existingUrl,
  existingReference,
  existingName,
  draftFile,
  onSelect,
  onClear,
  disabled = false,
}: {
  id: string;
  label: string;
  existingUrl?: string;
  existingReference?: string;
  existingName?: string;
  draftFile?: File;
  onSelect?: (file: File) => void;
  onClear?: () => void;
  disabled?: boolean;
}) {
  return (
    <div className="flex min-w-[14rem] items-center gap-2 rounded-xl border border-border/60 bg-background/40 p-2.5">
      <div className="min-w-0 flex-1">
        <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-muted-foreground">
          {label}
        </p>
        <p className="truncate text-xs text-foreground">
          {draftFile?.name ||
            existingName ||
            (existingReference ? "Arquivo legado vinculado" : "Sem anexo")}
        </p>
      </div>
      {existingUrl ? (
        <Button asChild size="sm" variant="outline">
          <a href={buildBackendFileUrl(existingUrl)} target="_blank" rel="noreferrer">
            Ver
          </a>
        </Button>
      ) : existingReference ? (
        <Badge className="rounded-full bg-amber-500/15 text-amber-200">Legado</Badge>
      ) : null}
      {onSelect ? (
        <label className="cursor-pointer">
          <input
            type="file"
            accept=".pdf,.png,.jpg,.jpeg"
            className="hidden"
            disabled={disabled}
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) {
                onSelect(file);
              }
              event.currentTarget.value = "";
            }}
            id={id}
          />
          <Button asChild size="sm" variant={draftFile || existingName ? "outline" : "secondary"}>
            <span>{draftFile || existingName || existingReference ? "Trocar" : "Anexar"}</span>
          </Button>
        </label>
      ) : null}
      {draftFile && onClear ? (
        <Button size="icon-sm" variant="ghost" onClick={onClear}>
          <Trash2Icon className="size-4" />
        </Button>
      ) : null}
    </div>
  );
}

export default function TesourariaRefinanciamentosPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = React.useState(1);
  const [search, setSearch] = React.useState("");
  const [dataInicio, setDataInicio] = React.useState<Date>();
  const [dataFim, setDataFim] = React.useState<Date>();
  const [draftDataInicio, setDraftDataInicio] = React.useState<Date>();
  const [draftDataFim, setDraftDataFim] = React.useState<Date>();
  const [filtersOpen, setFiltersOpen] = React.useState(false);
  const [tab, setTab] = React.useState<ListingTab>("pendentes");
  const [drafts, setDrafts] = React.useState<DraftMap>({});

  const statusFilter = TAB_STATUS_MAP[tab];
  const activeFiltersCount = Number(Boolean(dataInicio)) + Number(Boolean(dataFim));

  React.useEffect(() => {
    setPage(1);
  }, [search, dataInicio, dataFim, tab]);

  const refinanciamentosQuery = useQuery({
    queryKey: [
      "tesouraria-refinanciamentos",
      tab,
      page,
      search,
      dataInicio?.toISOString(),
      dataFim?.toISOString(),
    ],
    queryFn: () =>
      apiFetch<PaginatedResponse<RefinanciamentoItem>>("tesouraria/refinanciamentos", {
        query: {
          page,
          page_size: 15,
          search: search || undefined,
          data_inicio: toIsoDate(dataInicio),
          data_fim: toIsoDate(dataFim),
          status: statusFilter,
        },
      }),
  });

  const resumoQuery = useQuery({
    queryKey: [
      "tesouraria-refinanciamentos-resumo",
      tab,
      search,
      dataInicio?.toISOString(),
      dataFim?.toISOString(),
    ],
    queryFn: () =>
      apiFetch<RefinanciamentoResumo>("tesouraria/refinanciamentos/resumo", {
        query: {
          search: search || undefined,
          data_inicio: toIsoDate(dataInicio),
          data_fim: toIsoDate(dataFim),
          status: statusFilter,
        },
      }),
  });

  const efetivarMutation = useMutation({
    mutationFn: async ({
      refinanciamentoId,
      associado,
      agente,
    }: {
      refinanciamentoId: number;
      associado: File;
      agente: File;
    }) => {
      const formData = new FormData();
      formData.set("comprovante_associado", associado);
      formData.set("comprovante_agente", agente);
      return apiFetch<RefinanciamentoItem>(
        `tesouraria/refinanciamentos/${refinanciamentoId}/efetivar`,
        {
          method: "POST",
          formData,
        },
      );
    },
    onSuccess: (_, variables) => {
      setDrafts((current) => {
        const next = { ...current };
        delete next[variables.refinanciamentoId];
        return next;
      });
      toast.success("Renovação efetivada com sucesso.");
      void queryClient.invalidateQueries({ queryKey: ["tesouraria-refinanciamentos"] });
      void queryClient.invalidateQueries({ queryKey: ["tesouraria-refinanciamentos-resumo"] });
      void queryClient.invalidateQueries({ queryKey: ["agente-refinanciados"] });
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Falha ao efetivar renovação.");
    },
  });

  const rows = refinanciamentosQuery.data?.results ?? [];
  const totalCount = refinanciamentosQuery.data?.count ?? 0;
  const resumo = resumoQuery.data;
  const canceladasTotal =
    (resumo?.bloqueados ?? 0) + (resumo?.revertidos ?? 0) + (resumo?.desativados ?? 0);

  const columns = React.useMemo<DataTableColumn<RefinanciamentoItem>[]>(
    () => [
      {
        id: "associado",
        header: "Associado",
        cell: (row) => (
          <div className="space-y-2">
            <CopySnippet label="Nome" value={row.associado_nome} inline className="max-w-[17rem]" />
            <div className="flex flex-wrap gap-2">
              <CopySnippet label="CPF" value={row.cpf_cnpj} mono inline />
              <CopySnippet
                label="Matrícula"
                value={row.matricula_display || row.matricula}
                mono
                inline
              />
            </div>
          </div>
        ),
        headerClassName: "w-[24%]",
      },
      {
        id: "ciclo",
        header: "Contrato / Ciclo",
        cell: (row) => (
          <div className="space-y-1">
            <CopySnippet label="Contrato" value={row.contrato_codigo} mono inline />
            <p className="text-xs text-muted-foreground">
              Competência solicitada {formatMonthYear(row.competencia_solicitada)}
            </p>
            <p className="text-xs text-muted-foreground">
              Parcelas pagas no ciclo: {row.mensalidades_pagas}/{row.mensalidades_total}
            </p>
            <p className="text-xs text-muted-foreground">
              {row.referencias.length
                ? row.referencias.map((referencia) => formatMonthYear(referencia)).join(" · ")
                : "Sem referências detalhadas"}
            </p>
          </div>
        ),
      },
      {
        id: "financeiro",
        header: "Financeiro",
        cell: (row) => (
          <div className="space-y-1">
            <p className="font-semibold">{formatCurrency(row.valor_refinanciamento)}</p>
            <p className="text-xs text-muted-foreground">
              Repasse do agente: {formatCurrency(row.repasse_agente)}
            </p>
          </div>
        ),
      },
      {
        id: "etapa",
        header: "Etapa / Ativação",
        cell: (row) => (
          <div className="space-y-2">
            <StatusBadge status={row.etapa_operacional || row.status} />
            <StatusBadge status={row.pagamento_status} />
            <p className="text-xs text-muted-foreground">
              {row.data_ativacao_ciclo
                ? `Ativado em ${formatDateTime(row.data_ativacao_ciclo)}`
                : "Aguardando efetivação da tesouraria"}
            </p>
            {row.ativacao_inferida ? (
              <Badge className="rounded-full bg-amber-500/15 text-amber-200">
                Data inferida
              </Badge>
            ) : null}
          </div>
        ),
      },
      {
        id: "anexos",
        header: "Anexos / Ação",
        cellClassName: "min-w-[26rem]",
        cell: (row) => {
          const associado = row.comprovantes.find((item) => item.papel === "associado");
          const agente = row.comprovantes.find((item) => item.papel === "agente");
          const draft = drafts[row.id] ?? {};
          const canEfetivar = tab === "pendentes" && draft.associado && draft.agente;

          return (
            <div className="space-y-3">
              <div className="flex flex-wrap gap-2">
                <CompactUploadButton
                  id={`ref-${row.id}-associado`}
                  label="Associado"
                  existingUrl={associado?.arquivo_disponivel_localmente ? associado.arquivo : undefined}
                  existingReference={associado?.arquivo_referencia}
                  existingName={associado?.nome_original}
                  draftFile={draft.associado}
                  disabled={tab !== "pendentes"}
                  onSelect={
                    tab === "pendentes"
                      ? (file) =>
                          setDrafts((current) => ({
                            ...current,
                            [row.id]: { ...current[row.id], associado: file },
                          }))
                      : undefined
                  }
                  onClear={
                    tab === "pendentes"
                      ? () =>
                          setDrafts((current) => ({
                            ...current,
                            [row.id]: { ...current[row.id], associado: undefined },
                          }))
                      : undefined
                  }
                />
                <CompactUploadButton
                  id={`ref-${row.id}-agente`}
                  label="Agente"
                  existingUrl={agente?.arquivo_disponivel_localmente ? agente.arquivo : undefined}
                  existingReference={agente?.arquivo_referencia}
                  existingName={agente?.nome_original}
                  draftFile={draft.agente}
                  disabled={tab !== "pendentes"}
                  onSelect={
                    tab === "pendentes"
                      ? (file) =>
                          setDrafts((current) => ({
                            ...current,
                            [row.id]: { ...current[row.id], agente: file },
                          }))
                      : undefined
                  }
                  onClear={
                    tab === "pendentes"
                      ? () =>
                          setDrafts((current) => ({
                            ...current,
                            [row.id]: { ...current[row.id], agente: undefined },
                          }))
                      : undefined
                  }
                />
              </div>
              {canEfetivar ? (
                <Button
                  size="sm"
                  onClick={() =>
                    efetivarMutation.mutate({
                      refinanciamentoId: row.id,
                      associado: draft.associado!,
                      agente: draft.agente!,
                    })
                  }
                >
                  Efetivar renovação
                </Button>
              ) : tab === "pendentes" ? (
                <p className="text-xs text-muted-foreground">
                  Envie os dois anexos para efetivar a renovação.
                </p>
              ) : null}
            </div>
          );
        },
      },
    ],
    [drafts, efetivarMutation, tab],
  );

  return (
    <div className="space-y-6">
      <section className="rounded-[1.75rem] border border-border/60 bg-card/70 p-6">
        <div className="space-y-1">
          <p className="text-sm uppercase tracking-[0.28em] text-muted-foreground">
            Tesouraria
          </p>
          <h1 className="text-3xl font-semibold">Renovações</h1>
          <p className="text-sm text-muted-foreground">
            Renovações validadas pela coordenação, com efetivação e histórico financeiro por
            status.
          </p>
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatsCard
          title={
            tab === "pendentes"
              ? "Renovações Pendentes"
              : tab === "efetuadas"
                ? "Renovações Efetuadas"
                : "Renovações Canceladas"
          }
          value={String(resumo?.total ?? 0)}
          delta="Itens no recorte filtrado"
          icon={tab === "pendentes" ? Clock3Icon : tab === "efetuadas" ? CheckCircle2Icon : XCircleIcon}
          tone={tab === "canceladas" ? "warning" : tab === "efetuadas" ? "positive" : "neutral"}
        />
        <StatsCard
          title="Efetivadas"
          value={String(resumo?.efetivados ?? 0)}
          delta="Renovações concluídas pela tesouraria"
          icon={CheckCircle2Icon}
          tone="positive"
        />
        <StatsCard
          title="Canceladas"
          value={String(canceladasTotal)}
          delta="Bloqueadas, revertidas ou desativadas"
          icon={XCircleIcon}
          tone="warning"
        />
        <StatsCard
          title="Repasse Total"
          value={formatCurrency(resumo?.repasse_total ?? "0")}
          delta="Soma do repasse no filtro atual"
          icon={HandCoinsIcon}
          tone="neutral"
        />
      </section>

      <Tabs value={tab} onValueChange={(value) => setTab(value as ListingTab)} className="space-y-4">
        <TabsList variant="line" className="justify-start">
          <TabsTrigger value="pendentes">Renovações Pendentes</TabsTrigger>
          <TabsTrigger value="efetuadas">Renovações Efetuadas</TabsTrigger>
          <TabsTrigger value="canceladas">Renovações Canceladas</TabsTrigger>
        </TabsList>

        <section className="grid gap-4 rounded-[1.75rem] border border-border/60 bg-card/70 p-5 lg:grid-cols-[minmax(0,1fr)_auto]">
          <Input
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
            placeholder="Buscar por associado, CPF, matrícula ou contrato..."
            className="h-11 rounded-2xl border-border/60 bg-background/60"
          />
          <div className="flex justify-end">
            <Sheet
              open={filtersOpen}
              onOpenChange={(open) => {
                if (open) {
                  setDraftDataInicio(dataInicio);
                  setDraftDataFim(dataFim);
                }
                setFiltersOpen(open);
              }}
            >
              <SheetTrigger asChild>
                <Button variant="outline" className="h-11 rounded-2xl">
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
                    Refine o recorte da tesouraria por datas de solicitação da renovação.
                  </SheetDescription>
                </SheetHeader>

                <div className="space-y-5 overflow-y-auto px-4 pb-4">
                  <div className="space-y-2">
                    <Label>Data inicial</Label>
                    <DatePicker
                      value={draftDataInicio}
                      onChange={setDraftDataInicio}
                      placeholder="Início"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Data final</Label>
                    <DatePicker value={draftDataFim} onChange={setDraftDataFim} placeholder="Fim" />
                  </div>
                </div>

                <SheetFooter>
                  <Button
                    variant="outline"
                    onClick={() => {
                      setDraftDataInicio(undefined);
                      setDraftDataFim(undefined);
                      setDataInicio(undefined);
                      setDataFim(undefined);
                      setFiltersOpen(false);
                    }}
                  >
                    Limpar
                  </Button>
                  <Button
                    onClick={() => {
                      setDataInicio(draftDataInicio);
                      setDataFim(draftDataFim);
                      setFiltersOpen(false);
                    }}
                  >
                    Aplicar
                  </Button>
                </SheetFooter>
              </SheetContent>
            </Sheet>
          </div>
        </section>
      </Tabs>

      <DataTable
        data={rows}
        columns={columns}
        currentPage={page}
        totalPages={Math.max(1, Math.ceil(totalCount / 15))}
        onPageChange={setPage}
        emptyMessage={
          tab === "pendentes"
            ? "Nenhuma renovação pendente para a tesouraria."
            : tab === "efetuadas"
              ? "Nenhuma renovação efetuada no recorte."
              : "Nenhuma renovação cancelada no recorte."
        }
        loading={refinanciamentosQuery.isLoading}
        skeletonRows={6}
      />
    </div>
  );
}
