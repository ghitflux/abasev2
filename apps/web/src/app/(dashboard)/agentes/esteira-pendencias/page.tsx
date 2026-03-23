"use client";

import Link from "next/link";
import * as React from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeftIcon,
  ClipboardListIcon,
  RotateCcwIcon,
  SearchIcon,
  ShieldAlertIcon,
  UsersIcon,
} from "lucide-react";
import { toast } from "sonner";

import type {
  AssociadoDetail,
  PaginatedResponse,
  PendenciaItem,
  PendenciaResumo,
} from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import { getDefaultRouteForRole } from "@/lib/navigation";
import { formatDate } from "@/lib/formatters";
import { maskCPFCNPJ } from "@/lib/masks";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { usePermissions } from "@/hooks/use-permissions";
import AssociadoForm from "@/components/associados/associado-form";
import StatusBadge from "@/components/custom/status-badge";
import DataTable, {
  type DataTableColumn,
} from "@/components/shared/data-table";
import EmptyState from "@/components/shared/empty-state";
import { DialogFormSkeleton, MetricCardSkeleton } from "@/components/shared/page-skeletons";
import StatsCard from "@/components/shared/stats-card";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";

export default function EsteiraPendenciasPage() {
  const queryClient = useQueryClient();
  const { hasRole, role } = usePermissions();
  const isAdmin = hasRole("ADMIN");
  const fallbackHref = getDefaultRouteForRole(role);
  const [search, setSearch] = React.useState("");
  const [page, setPage] = React.useState(1);
  const [selectedPendencia, setSelectedPendencia] =
    React.useState<PendenciaItem | null>(null);
  const debouncedSearch = useDebouncedValue(search, 300);

  const pendenciasQuery = useQuery({
    queryKey: ["pendencias-agente", page, debouncedSearch],
    queryFn: () =>
      apiFetch<PaginatedResponse<PendenciaItem>>("esteira/pendencias", {
        query: {
          page,
          page_size: 5,
          search: debouncedSearch,
        },
      }),
  });
  const pendenciasResumoQuery = useQuery({
    queryKey: ["pendencias-agente-resumo", debouncedSearch],
    queryFn: () =>
      apiFetch<PendenciaResumo>("esteira/pendencias-resumo", {
        query: {
          search: debouncedSearch || undefined,
        },
      }),
  });

  const rows = pendenciasQuery.data?.results ?? [];
  const totalPages = Math.max(
    1,
    Math.ceil((pendenciasQuery.data?.count ?? 0) / 5),
  );
  const resumo = pendenciasResumoQuery.data ?? {
    total: 0,
    retornadas_agente: 0,
    internas: 0,
    associados_impactados: 0,
  };
  const selectedEsteiraItemId = selectedPendencia?.esteira_item_id;
  const associadoQuery = useQuery({
    queryKey: ["pendencias-agente-correcao", selectedEsteiraItemId],
    enabled: selectedEsteiraItemId !== undefined,
    queryFn: () =>
      apiFetch<AssociadoDetail>(`esteira/${selectedEsteiraItemId!}/correcao`),
  });

  const handleCorrectionSuccess = React.useCallback(
    async (associado: AssociadoDetail) => {
      const esteiraId = selectedPendencia?.esteira_item_id;
      if (!esteiraId) {
        throw new Error(
          "Este associado não possui item de esteira para reenvio.",
        );
      }

      await apiFetch(`esteira/${esteiraId}/validar-documento`, {
        method: "POST",
      });

      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["pendencias-agente"] }),
        queryClient.invalidateQueries({ queryKey: ["pendencias-agente-resumo"] }),
        queryClient.invalidateQueries({
          queryKey: ["pendencias-agente-resumo-sidebar"],
        }),
        queryClient.invalidateQueries({
          queryKey: ["dashboard-pendencias-agente"],
        }),
        queryClient.invalidateQueries({ queryKey: ["esteira"] }),
        queryClient.invalidateQueries({ queryKey: ["esteira-detalhe"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard-esteira"] }),
        queryClient.invalidateQueries({
          queryKey: ["associado", associado.id],
        }),
        queryClient.invalidateQueries({
          queryKey: ["pendencias-agente-correcao", esteiraId],
        }),
        queryClient.invalidateQueries({ queryKey: ["contratos-lista"] }),
        queryClient.invalidateQueries({ queryKey: ["contratos-resumo"] }),
      ]);

      toast.success("Cadastro corrigido e reenviado para nova análise.");
      setSelectedPendencia(null);
    },
    [queryClient, selectedPendencia],
  );

  const columns = React.useMemo<DataTableColumn<PendenciaItem>[]>(
    () => [
      {
        id: "associado",
        header: "Associado",
        cell: (row) => row.associado_nome,
      },
      {
        id: "matricula_servidor",
        header: "Matrícula do Servidor",
        cell: (row) => row.matricula_display || row.matricula || "—",
      },
      {
        id: "cpf",
        header: "CPF",
        cell: (row) => maskCPFCNPJ(row.cpf_cnpj),
      },
      {
        id: "tipo",
        header: "Tipo de Pendência",
        cell: (row) => row.tipo || "pendência",
      },
      {
        id: "descricao",
        header: "Descrição",
        cell: (row) => row.descricao,
      },
      {
        id: "data",
        header: "Data do cadastro",
        cell: (row) => formatDate(row.associado_created_at || row.created_at),
      },
      {
        id: "acoes",
        header: "Ações",
        cell: (row) => (
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge status={row.status} />
            {isAdmin ? (
              <Button variant="outline" size="sm" asChild>
                <Link href={`/associados/${row.associado_id}`}>Abrir</Link>
              </Button>
            ) : null}
            {row.retornado_para_agente && (
              <Button
                size="sm"
                variant="default"
                onClick={() => setSelectedPendencia(row)}
              >
                Corrigir cadastro
              </Button>
            )}
          </div>
        ),
      },
    ],
    [isAdmin],
  );

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {pendenciasResumoQuery.isLoading && !pendenciasResumoQuery.data ? (
          Array.from({ length: 4 }).map((_, index) => <MetricCardSkeleton key={index} />)
        ) : (
          <>
            <StatsCard
              title="Pendências abertas"
              value={String(resumo.total)}
              delta={`${resumo.associados_impactados} cadastro(s) no recorte`}
              icon={ShieldAlertIcon}
              tone="warning"
            />
            <StatsCard
              title="Retornadas ao agente"
              value={String(resumo.retornadas_agente)}
              delta="Demandam correção e novo envio"
              icon={RotateCcwIcon}
              tone="warning"
            />
            <StatsCard
              title="Tratamento interno"
              value={String(resumo.internas)}
              delta="Aguardando ação das áreas internas"
              icon={ClipboardListIcon}
              tone="neutral"
            />
            <StatsCard
              title="Associados impactados"
              value={String(resumo.associados_impactados)}
              delta={`${resumo.total} pendência(s) aberta(s)`}
              icon={UsersIcon}
              tone="neutral"
            />
          </>
        )}
      </section>

      <section className="flex flex-col gap-3 lg:flex-row lg:items-center">
        <div className="relative flex-1">
          <SearchIcon className="pointer-events-none absolute top-1/2 left-4 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
            placeholder="Nome / Código do contrato / CPF"
            className="rounded-2xl border-border/60 bg-card/60 pl-11"
          />
        </div>
        <Button onClick={() => setPage(1)}>Filtrar</Button>
        <Button
          variant="outline"
          onClick={() => {
            setSearch("");
            setPage(1);
          }}
        >
          Limpar
        </Button>
        <Button variant="outline" asChild>
          <Link href={fallbackHref}>
            <ArrowLeftIcon className="size-4" />
            Voltar
          </Link>
        </Button>
      </section>

      {rows.length || pendenciasQuery.isLoading ? (
        <DataTable
          data={rows}
          columns={columns}
          currentPage={page}
          totalPages={totalPages}
          onPageChange={setPage}
          loading={pendenciasQuery.isLoading}
          skeletonRows={5}
        />
      ) : (
        <EmptyState
          title="Nenhuma pendência aberta no momento."
          description="Quando uma análise for devolvida para correção, ela aparecerá aqui."
        />
      )}

      <Dialog
        open={Boolean(selectedPendencia)}
        onOpenChange={(open) => {
          if (!open) {
            setSelectedPendencia(null);
          }
        }}
      >
        <DialogContent
          className="flex h-[94vh] w-[96vw] max-w-[1680px] overflow-hidden rounded-[2rem] p-0 sm:max-w-[96vw] 2xl:w-[1680px] 2xl:max-w-[1680px]"
          showCloseButton
        >
          <div className="flex min-h-0 flex-1 flex-col">
            <DialogHeader className="shrink-0 border-b border-border/60 px-6 py-5 pr-14">
              <DialogTitle>Corrigir cadastro e reenviar</DialogTitle>
              <DialogDescription>
                {selectedPendencia
                  ? `Revise todos os dados e anexos de ${selectedPendencia.associado_nome} antes de devolver o cadastro para nova análise.`
                  : "Revise o cadastro completo antes de reenviar para o analista."}
              </DialogDescription>
            </DialogHeader>

            <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
              {selectedPendencia ? (
                <div className="mb-6 rounded-3xl border border-amber-500/20 bg-amber-500/5 p-4">
                  <div className="flex flex-wrap items-center gap-3">
                    <StatusBadge status={selectedPendencia.status} />
                    <p className="text-sm font-medium">
                      {selectedPendencia.tipo || "pendência"}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      Aberta em {formatDate(selectedPendencia.created_at)}
                    </p>
                  </div>
                  <p className="mt-3 text-sm text-muted-foreground">
                    {selectedPendencia.descricao}
                  </p>
                </div>
              ) : null}

              {associadoQuery.isLoading ? (
                <DialogFormSkeleton />
              ) : associadoQuery.isError ? (
                <div className="rounded-3xl border border-destructive/30 bg-destructive/5 px-6 py-5 text-sm text-destructive">
                  Não foi possível carregar o cadastro do associado para
                  correção.
                </div>
              ) : associadoQuery.data ? (
                <AssociadoForm
                  mode="edit"
                  associadoId={associadoQuery.data.id}
                  initialData={associadoQuery.data}
                  hideBackButton
                  title="Correção de cadastro"
                  description="Ajuste qualquer dado do associado, substitua anexos quando necessário e finalize com o reenvio para o analista."
                  submitLabel="Salvar e reenviar para análise"
                  onSuccess={handleCorrectionSuccess}
                />
              ) : null}
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
