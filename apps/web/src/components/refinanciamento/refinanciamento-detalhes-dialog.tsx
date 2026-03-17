"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { LoaderCircleIcon } from "lucide-react";

import type { AssociadoDetail, RefinanciamentoItem } from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import { formatDateTime, formatMonthYear } from "@/lib/formatters";
import {
  AssociadoContractsOverview,
  AssociadoSnapshotSummary,
} from "@/components/associados/associado-contracts-overview";
import {
  ParcelaDetalheDialog,
  type ParcelaDetailTarget,
} from "@/components/contratos/parcela-detalhe-dialog";
import StatusBadge from "@/components/custom/status-badge";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

type RefinanciamentoDetalhesDialogProps = {
  open: boolean;
  associadoId: number | null;
  refinanciamentoId: number | null;
  onOpenChange: (open: boolean) => void;
};

function SummaryItem({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-2xl border border-border/60 bg-background/50 p-4">
      <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
        {label}
      </p>
      <p className="mt-2 text-sm font-medium text-foreground">{value}</p>
    </div>
  );
}

export function RefinanciamentoDetalhesDialog({
  open,
  associadoId,
  refinanciamentoId,
  onOpenChange,
}: RefinanciamentoDetalhesDialogProps) {
  const [selectedTarget, setSelectedTarget] =
    React.useState<ParcelaDetailTarget | null>(null);

  const associadoQuery = useQuery({
    queryKey: ["refinanciamento-associado-detalhe", associadoId],
    queryFn: () => apiFetch<AssociadoDetail>(`associados/${associadoId}`),
    enabled: open && Boolean(associadoId),
  });

  const refinanciamentoQuery = useQuery({
    queryKey: ["refinanciamento-detalhe-modal", refinanciamentoId],
    queryFn: () => apiFetch<RefinanciamentoItem>(`refinanciamentos/${refinanciamentoId}`),
    enabled: open && Boolean(refinanciamentoId),
  });

  React.useEffect(() => {
    if (!open) {
      setSelectedTarget(null);
    }
  }, [open]);

  const associado = associadoQuery.data;
  const refinanciamento = refinanciamentoQuery.data;

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="flex h-[min(92dvh,64rem)] w-[min(96vw,88rem)] max-h-[92dvh] flex-col overflow-hidden p-0 sm:max-w-none">
          <DialogHeader className="sticky top-0 z-10 border-b border-border/60 bg-background/95 px-5 pb-4 pt-6 pr-14 backdrop-blur sm:px-6">
            <DialogTitle className="break-words">
              {associado?.nome_completo || "Detalhes do associado"}
            </DialogTitle>
            <DialogDescription className="break-words">
              {associado
                ? `${associado.cpf_cnpj} · ${associado.matricula_display || associado.matricula}`
                : "Carregando dados completos do associado, contratos e ciclos."}
            </DialogDescription>
          </DialogHeader>

          <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden px-5 pb-6 pt-5 sm:px-6">
            
            {associadoQuery.isLoading || refinanciamentoQuery.isLoading ? (
              <div className="flex min-h-64 items-center justify-center">
                <LoaderCircleIcon className="size-6 animate-spin text-primary" />
              </div>
            ) : associadoQuery.isError || refinanciamentoQuery.isError ? (
              <div className="rounded-2xl border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
                {associadoQuery.error instanceof Error
                  ? associadoQuery.error.message
                  : refinanciamentoQuery.error instanceof Error
                    ? refinanciamentoQuery.error.message
                    : "Falha ao carregar os detalhes da renovação."}
              </div>
            ) : associado && refinanciamento ? (
              <div className="space-y-6">
                <AssociadoSnapshotSummary associado={associado} />

                <section className="rounded-[1.5rem] border border-border/60 bg-card/60 p-5">
                  <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                    <div className="space-y-2">
                      <p className="text-sm font-medium text-foreground">
                        {refinanciamento.contrato_codigo}
                      </p>
                      <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                        {refinanciamento.referencias.map((referencia) => (
                          <Badge
                            key={referencia}
                            variant="outline"
                            className="rounded-full border-border/60"
                          >
                            {formatMonthYear(referencia)}
                          </Badge>
                        ))}
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {refinanciamento.motivo_apto_renovacao}
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <StatusBadge status={refinanciamento.status} />
                    </div>
                  </div>
                  <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                    <SummaryItem
                      label="Etapa operacional"
                      value={refinanciamento.etapa_operacional.replaceAll("_", " ")}
                    />
                    <SummaryItem
                      label="Mensalidades"
                      value={`${refinanciamento.mensalidades_pagas}/${refinanciamento.mensalidades_total}`}
                    />
                    <SummaryItem
                      label="Renovação ativada em"
                      value={formatDateTime(refinanciamento.data_solicitacao_renovacao)}
                    />
                    <SummaryItem
                      label="Origem"
                      value={refinanciamento.origem.replaceAll("_", " ")}
                    />
                  </div>
                </section>

                <AssociadoContractsOverview
                  associado={associado}
                  onParcelaClick={setSelectedTarget}
                  defaultOpenContractId={refinanciamento.contrato_id}
                />
              </div>
            ) : null}
          </div>
        </DialogContent>
      </Dialog>

      {associadoId ? (
        <ParcelaDetalheDialog
          associadoId={associadoId}
          target={selectedTarget}
          onOpenChange={(nextOpen) => {
            if (!nextOpen) {
              setSelectedTarget(null);
            }
          }}
        />
      ) : null}
    </>
  );
}
