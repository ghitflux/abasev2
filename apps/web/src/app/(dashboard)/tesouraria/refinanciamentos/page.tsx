"use client";

import * as React from "react";
import { format } from "date-fns";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileDownIcon, ListIcon, PrinterIcon, Trash2Icon } from "lucide-react";
import { toast } from "sonner";

import type { PaginatedResponse, RefinanciamentoItem } from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import { buildBackendFileUrl } from "@/lib/backend-files";
import { formatCurrency, formatDateTime, formatMonthYear } from "@/lib/formatters";
import DatePicker from "@/components/custom/date-picker";
import FileUploadDropzone from "@/components/custom/file-upload-dropzone";
import StatusBadge from "@/components/custom/status-badge";
import CopySnippet from "@/components/shared/copy-snippet";
import DataTable, { type DataTableColumn } from "@/components/shared/data-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";

const comprovanteAccept = {
  "application/pdf": [".pdf"],
  "image/png": [".png"],
  "image/jpeg": [".jpg", ".jpeg"],
};

function toIsoDate(value?: Date) {
  if (!value) return undefined;
  return format(value, "yyyy-MM-dd");
}

type DraftMap = Record<number, { associado?: File; agente?: File }>;

export default function TesourariaRefinanciamentosPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = React.useState(1);
  const [search, setSearch] = React.useState("");
  const [dataInicio, setDataInicio] = React.useState<Date>();
  const [dataFim, setDataFim] = React.useState<Date>();
  const [drafts, setDrafts] = React.useState<DraftMap>({});
  const [itemsTarget, setItemsTarget] = React.useState<RefinanciamentoItem | null>(null);

  const refinanciamentosQuery = useQuery({
    queryKey: [
      "tesouraria-refinanciamentos",
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
      toast.success("Refinanciamento efetivado.");
      void queryClient.invalidateQueries({ queryKey: ["tesouraria-refinanciamentos"] });
      void queryClient.invalidateQueries({ queryKey: ["agente-refinanciados"] });
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Falha ao efetivar refinanciamento.");
    },
  });

  const rows = refinanciamentosQuery.data?.results ?? [];
  const totalCount = refinanciamentosQuery.data?.count ?? 0;

  const columns = React.useMemo<DataTableColumn<RefinanciamentoItem>[]>(
    () => [
      {
        id: "valor",
        header: "Valor Refinanciamento",
        cell: (row) => (
          <div>
            <p className="font-semibold">{formatCurrency(row.valor_refinanciamento)}</p>
            <p className="text-xs text-muted-foreground">{row.associado_nome}</p>
          </div>
        ),
      },
      {
        id: "repasse",
        header: "Agente (Repasse)",
        cell: (row) => (
          <div>
            <p>{formatCurrency(row.repasse_agente)}</p>
            <p className="text-xs text-muted-foreground">10% do valor</p>
          </div>
        ),
      },
      {
        id: "pagamento",
        header: "Ativação do ciclo",
        cell: (row) => (
          <div className="space-y-1">
            <StatusBadge status={row.pagamento_status} />
            <p className="text-xs text-muted-foreground">
              {row.data_ativacao_ciclo
                ? `Ativado em: ${formatDateTime(row.data_ativacao_ciclo)}`
                : "Aguardando anexação / conferência"}
            </p>
            {row.ativacao_inferida ? (
              <Badge className="rounded-full bg-amber-500/15 text-amber-200">
                Data inferida pela tesouraria
              </Badge>
            ) : null}
          </div>
        ),
      },
      {
        id: "itens",
        header: "Itens",
        cell: (row) => (
          <Button size="sm" variant="outline" onClick={() => setItemsTarget(row)}>
            <ListIcon className="size-4" />
            Itens ({row.itens.length})
          </Button>
        ),
      },
      {
        id: "solicitacao",
        header: "Etapa da renovação",
        cell: (row) => (
          <div className="space-y-1">
            <StatusBadge status={row.etapa_operacional || row.status} />
            <p className="text-xs text-muted-foreground">
              Solicitado em: {formatDateTime(row.data_solicitacao_renovacao ?? row.created_at)}
            </p>
            <CopySnippet label="CPF" value={row.cpf_cnpj} mono inline />
          </div>
        ),
      },
      {
        id: "comprovantes",
        header: "Comprovantes",
        cell: (row) => {
          const associado = row.comprovantes.find((item) => item.papel === "associado");
          const agente = row.comprovantes.find((item) => item.papel === "agente");
          const draft = drafts[row.id] ?? {};

          return (
            <div className="grid min-w-72 gap-3">
              <UploadTile
                label="Associado"
                existingUrl={associado?.arquivo_disponivel_localmente ? associado.arquivo : undefined}
                existingReference={associado?.arquivo_referencia}
                existingName={associado?.nome_original}
                draftFile={draft.associado}
                onSelect={(file) =>
                  setDrafts((current) => ({
                    ...current,
                    [row.id]: { ...current[row.id], associado: file },
                  }))
                }
                onClear={() =>
                  setDrafts((current) => ({
                    ...current,
                    [row.id]: { ...current[row.id], associado: undefined },
                  }))
                }
              />
              <UploadTile
                label="Agente"
                existingUrl={agente?.arquivo_disponivel_localmente ? agente.arquivo : undefined}
                existingReference={agente?.arquivo_referencia}
                existingName={agente?.nome_original}
                draftFile={draft.agente}
                onSelect={(file) =>
                  setDrafts((current) => ({
                    ...current,
                    [row.id]: { ...current[row.id], agente: file },
                  }))
                }
                onClear={() =>
                  setDrafts((current) => ({
                    ...current,
                    [row.id]: { ...current[row.id], agente: undefined },
                  }))
                }
              />
              {row.status !== "efetivado" && draft.associado && draft.agente ? (
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
                  Efetivar refinanciamento
                </Button>
              ) : null}
            </div>
          );
        },
      },
    ],
    [drafts, efetivarMutation],
  );

  return (
    <div className="space-y-6">
      <section className="rounded-[1.75rem] border border-border/60 bg-card/70 p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-sm uppercase tracking-[0.28em] text-muted-foreground">
              Tesouraria
            </p>
            <h1 className="text-3xl font-semibold">Renovações aprovadas</h1>
            <p className="text-sm text-muted-foreground">
              Conferência final, anexação de comprovantes e materialização do próximo ciclo.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Button variant="outline" onClick={() => window.print()}>
              <FileDownIcon className="size-4" />
              PDF do dia
            </Button>
            <Button variant="outline" onClick={() => window.print()}>
              <PrinterIcon className="size-4" />
              Impressão digitada
            </Button>
          </div>
        </div>
      </section>

      <section className="grid gap-3 rounded-[1.75rem] border border-border/60 bg-card/50 p-4 xl:grid-cols-[180px_minmax(0,1fr)_180px_180px_auto]">
        <Input
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
            setPage(1);
          }}
          placeholder="CPF ou nome..."
          className="rounded-2xl border-border/60 bg-card/60"
        />
        <div />
        <DatePicker value={dataInicio} onChange={setDataInicio} placeholder="Início" />
        <DatePicker value={dataFim} onChange={setDataFim} placeholder="Fim" />
        <Button onClick={() => setPage(1)}>Aplicar</Button>
      </section>

      <DataTable
        data={rows}
        columns={columns}
        currentPage={page}
        totalPages={Math.max(1, Math.ceil(totalCount / 15))}
        onPageChange={setPage}
        emptyMessage="Nenhum refinanciamento disponível para tesouraria."
        loading={refinanciamentosQuery.isLoading}
        skeletonRows={6}
      />

      <Dialog open={!!itemsTarget} onOpenChange={(open) => !open && setItemsTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Itens do refinanciamento</DialogTitle>
            <DialogDescription>
              Parcelas geradas para o ciclo {itemsTarget?.ciclo_key || "N/I"}.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            {itemsTarget?.itens.map((item) => (
              <div
                key={item.id}
                className="flex items-center justify-between rounded-2xl border border-border/60 bg-card/60 p-4"
              >
                <div>
                  <p className="font-medium">Parcela {item.numero}</p>
                  <p className="text-sm text-muted-foreground">
                    {formatMonthYear(item.referencia_mes)}
                  </p>
                </div>
                <div className="text-right">
                  <p className="font-medium">{formatCurrency(item.valor)}</p>
                  <StatusBadge status={item.status} />
                </div>
              </div>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function UploadTile({
  label,
  existingUrl,
  existingReference,
  existingName,
  draftFile,
  onSelect,
  onClear,
}: {
  label: string;
  existingUrl?: string;
  existingReference?: string;
  existingName?: string;
  draftFile?: File;
  onSelect: (file: File) => void;
  onClear: () => void;
}) {
  return (
    <div className="rounded-2xl border border-border/60 bg-background/40 p-3">
      <div className="mb-2 flex items-center justify-between gap-3">
        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-muted-foreground">
          {label}
        </p>
        {draftFile ? (
          <Button size="icon-sm" variant="ghost" onClick={onClear}>
            <Trash2Icon className="size-4" />
          </Button>
        ) : null}
      </div>
      {existingUrl ? (
        <a
          href={buildBackendFileUrl(existingUrl)}
          target="_blank"
          rel="noreferrer"
          className="text-sm text-primary underline-offset-4 hover:underline"
        >
          Ver comprovante {existingName ? `(${existingName})` : ""}
        </a>
      ) : existingReference ? (
        <div className="space-y-1 text-sm">
          <p className="font-medium">{existingName || label}</p>
          <p className="text-xs text-muted-foreground break-all">{existingReference}</p>
          <p className="text-[11px] text-amber-200">Referência de arquivo legado</p>
        </div>
      ) : draftFile ? (
        <div className="space-y-1 text-sm">
          <p className="font-medium">{draftFile.name}</p>
          <p className="text-xs text-muted-foreground">
            {(draftFile.size / 1024 / 1024).toFixed(2)} MB pronto para envio.
          </p>
        </div>
      ) : (
        <FileUploadDropzone
          accept={comprovanteAccept}
          maxSize={5 * 1024 * 1024}
          onUpload={onSelect}
          className="rounded-2xl px-3 py-5"
          emptyTitle={`Enviar comprovante do ${label.toLowerCase()}`}
          emptyDescription="PDF, JPG ou PNG até 5 MB"
        />
      )}
    </div>
  );
}
