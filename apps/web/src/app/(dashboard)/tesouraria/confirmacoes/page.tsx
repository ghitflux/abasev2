"use client";

import * as React from "react";
import { format } from "date-fns";
import { CheckIcon, ExternalLinkIcon, SearchIcon } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import type { ConfirmacaoItem, PaginatedResponse } from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import { maskCPFCNPJ } from "@/lib/masks";
import CalendarCompetencia from "@/components/custom/calendar-competencia";
import StatusBadge from "@/components/custom/status-badge";
import DataTable, { type DataTableColumn } from "@/components/shared/data-table";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";

export default function ConfirmacoesPage() {
  const queryClient = useQueryClient();
  const [competencia, setCompetencia] = React.useState(() => new Date());
  const [search, setSearch] = React.useState("");
  const [page, setPage] = React.useState(1);
  const [draftLinks, setDraftLinks] = React.useState<Record<number, string>>({});

  const confirmacoesQuery = useQuery({
    queryKey: ["tesouraria-confirmacoes", competencia.toISOString(), search, page],
    queryFn: () =>
      apiFetch<PaginatedResponse<ConfirmacaoItem>>("tesouraria/confirmacoes", {
        query: {
          page,
          page_size: 15,
          competencia: format(competencia, "yyyy-MM"),
          search: search || undefined,
        },
      }),
  });

  const actionMutation = useMutation({
    mutationFn: async ({
      id,
      action,
      body,
    }: {
      id: number;
      action: "link" | "confirmar-ligacao" | "confirmar-averbacao";
      body?: Record<string, string>;
    }) =>
      apiFetch<ConfirmacaoItem>(`tesouraria/confirmacoes/${id}/${action}`, {
        method: "POST",
        body,
      }),
    onSuccess: (_, variables) => {
      if (variables.action === "link") {
        setDraftLinks((current) => ({
          ...current,
          [variables.id]: "",
        }));
      }
      toast.success("Confirmação atualizada.");
      void queryClient.invalidateQueries({ queryKey: ["tesouraria-confirmacoes"] });
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Falha ao atualizar confirmação.");
    },
  });

  const rows = confirmacoesQuery.data?.results ?? [];
  const totalPages = Math.max(1, Math.ceil((confirmacoesQuery.data?.count ?? 0) / 15));

  const columns = React.useMemo<DataTableColumn<ConfirmacaoItem>[]>(
    () => [
      {
        id: "nome",
        header: "Nome",
        cell: (row) => (
          <div>
            <p className="font-semibold tracking-[0.1em]">{row.nome.toUpperCase()}</p>
            <p className="text-xs text-muted-foreground">{maskCPFCNPJ(row.cpf_cnpj)}</p>
          </div>
        ),
      },
      {
        id: "link",
        header: "Link de chamada",
        cell: (row) => {
          const linkValue = draftLinks[row.id] ?? row.link_chamada;
          const hasLink = Boolean(row.link_chamada);
          const ligacaoRecebida = row.ligacao_confirmada;

          return (
            <div className="min-w-80 space-y-3">
              <div className="flex gap-2">
                <Input
                  value={linkValue}
                  onChange={(event) =>
                    setDraftLinks((current) => ({ ...current, [row.id]: event.target.value }))
                  }
                  placeholder="Inserir link (texto livre)"
                  className="rounded-2xl border-border/60 bg-card/60"
                />
                <Button
                  size="icon-sm"
                  onClick={() =>
                    actionMutation.mutate({
                      id: row.id,
                      action: "link",
                      body: { link: linkValue },
                    })
                  }
                  disabled={!linkValue || actionMutation.isPending}
                >
                  <CheckIcon className="size-4" />
                </Button>
                <Button
                  size="icon-sm"
                  variant="outline"
                  disabled={!hasLink}
                  onClick={() => window.open(row.link_chamada, "_blank", "noopener,noreferrer")}
                >
                  <ExternalLinkIcon className="size-4" />
                </Button>
              </div>
              <div className="flex items-center gap-2 text-sm">
                <span
                  className={`size-2 rounded-full ${
                    ligacaoRecebida ? "bg-emerald-400" : hasLink ? "bg-amber-400" : "bg-rose-400"
                  }`}
                />
                <span className="text-muted-foreground">
                  {ligacaoRecebida
                    ? "Ligação recebida"
                    : hasLink
                      ? "Link salvo, pendente de confirmação"
                      : "Sem link ainda"}
                </span>
              </div>
            </div>
          );
        },
      },
      {
        id: "averbacao",
        header: "Averbação",
        cell: (row) => (
          <div className="space-y-3">
            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                variant="outline"
                disabled={!row.link_chamada || row.ligacao_confirmada}
                onClick={() => actionMutation.mutate({ id: row.id, action: "confirmar-ligacao" })}
              >
                Confirmar ligação
              </Button>
              <Button
                size="sm"
                variant={row.averbacao_confirmada ? "outline" : "default"}
                disabled={!row.ligacao_confirmada || row.averbacao_confirmada}
                onClick={() => actionMutation.mutate({ id: row.id, action: "confirmar-averbacao" })}
              >
                Confirmar averbação
              </Button>
            </div>
            <StatusBadge status={row.status_visual} />
          </div>
        ),
      },
    ],
    [actionMutation, draftLinks],
  );

  return (
    <div className="space-y-6">
      <section className="rounded-[1.75rem] border border-border/60 bg-card/70 p-6">
        <p className="text-sm uppercase tracking-[0.28em] text-muted-foreground">
          Tesouraria
        </p>
        <h1 className="text-3xl font-semibold">Confirmações — Ligação & Averbação</h1>
        <p className="text-sm text-muted-foreground">
          Cole o link de atendimento, confirme ligação e finalize a averbação na competência.
        </p>
      </section>

      <section className="grid gap-3 rounded-[1.75rem] border border-border/60 bg-card/50 p-4 lg:grid-cols-[220px_minmax(0,1fr)_auto]">
        <CalendarCompetencia
          value={competencia}
          onChange={(value) => {
            setCompetencia(value);
            setPage(1);
          }}
          className="rounded-2xl bg-card/60"
        />
        <div className="relative">
          <SearchIcon className="pointer-events-none absolute top-1/2 left-4 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
            placeholder="Buscar por nome"
            className="rounded-2xl border-border/60 bg-card/60 pl-11"
          />
        </div>
        <Button onClick={() => void queryClient.invalidateQueries({ queryKey: ["tesouraria-confirmacoes"] })}>
          Buscar
        </Button>
      </section>

      {confirmacoesQuery.isLoading ? (
        <div className="flex items-center gap-3 rounded-[1.75rem] border border-border/60 bg-card/60 px-6 py-8 text-sm text-muted-foreground">
          <Spinner />
          Carregando confirmações...
        </div>
      ) : (
        <DataTable
          data={rows}
          columns={columns}
          currentPage={page}
          totalPages={totalPages}
          onPageChange={setPage}
          emptyMessage="Nenhuma confirmação encontrada para a competência."
        />
      )}
    </div>
  );
}
