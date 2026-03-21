"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import { LoaderCircleIcon } from "lucide-react";

import type { ArquivoEvidencia, ParcelaDetail } from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import { buildBackendFileUrl } from "@/lib/backend-files";
import {
  formatCurrency,
  formatDate,
  formatDateTime,
  formatMonthYear,
} from "@/lib/formatters";
import { usePermissions } from "@/hooks/use-permissions";
import StatusBadge from "@/components/custom/status-badge";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

export type ParcelaDetailTarget = {
  contratoId: number;
  referenciaMes: string;
  kind: "cycle" | "unpaid";
};

function resolveReferenceLabel(tipoReferencia: string) {
  if (tipoReferencia === "relatorio_competencia") {
    return "Relatório mensal";
  }
  if (tipoReferencia === "placeholder_recebido") {
    return "Pagamento recebido";
  }
  if (tipoReferencia === "sem_arquivo") {
    return "Sem anexo";
  }
  if (tipoReferencia === "legado_sem_arquivo") {
    return "Referência legado";
  }
  return "Arquivo local";
}

function DetailItem({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="min-w-0 overflow-hidden rounded-2xl border border-border/60 bg-background/50 p-4">
      <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
        {label}
      </p>
      <p className="mt-2 break-words text-sm font-medium text-foreground">
        {value}
      </p>
    </div>
  );
}

function EvidenceCard({
  evidence,
}: {
  evidence: ArquivoEvidencia;
}) {
  const title = evidence.arquivo_referencia || evidence.nome;
  if (evidence.arquivo_disponivel_localmente && evidence.url) {
    return (
      <a
        href={buildBackendFileUrl(evidence.url)}
        target="_blank"
        rel="noreferrer"
        className="block min-w-0 overflow-hidden rounded-2xl border border-border/60 bg-background/60 p-4 transition hover:border-primary/50"
      >
        <div className="flex min-w-0 flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <p className="min-w-0 break-words text-sm font-medium text-foreground">
            {evidence.nome}
          </p>
          <Badge
            variant="secondary"
            className="shrink-0 self-start rounded-full whitespace-normal text-center"
          >
            {resolveReferenceLabel(evidence.tipo_referencia)}
          </Badge>
        </div>
        <p className="mt-2 break-all text-xs text-muted-foreground">{title}</p>
        {evidence.created_at ? (
          <p className="mt-2 text-[11px] text-muted-foreground">
            Registrado em {formatDateTime(evidence.created_at)}
          </p>
        ) : null}
      </a>
    );
  }

  return (
    <div className="min-w-0 overflow-hidden rounded-2xl border border-dashed border-border/60 bg-background/40 p-4">
      <div className="flex min-w-0 flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <p className="min-w-0 break-words text-sm font-medium text-foreground">
          {evidence.nome}
        </p>
        <Badge
          variant="outline"
          className="shrink-0 self-start rounded-full whitespace-normal text-center"
        >
          {resolveReferenceLabel(evidence.tipo_referencia)}
        </Badge>
      </div>
      <p className="mt-2 break-all text-xs text-muted-foreground">
        {title || "Sem referência."}
      </p>
      {evidence.created_at ? (
        <p className="mt-2 text-[11px] text-muted-foreground">
          Registrado em {formatDateTime(evidence.created_at)}
        </p>
      ) : null}
    </div>
  );
}

function EvidenceSection({
  title,
  evidences,
  emptyLabel,
}: {
  title: string;
  evidences: ArquivoEvidencia[];
  emptyLabel: string;
}) {
  return (
    <section className="space-y-3">
      <p className="text-sm font-medium text-foreground">{title}</p>
      {evidences.length ? (
        <div className="grid gap-3 2xl:grid-cols-2">
          {evidences.map((evidence) => (
            <EvidenceCard key={evidence.id} evidence={evidence} />
          ))}
        </div>
      ) : (
        <div className="rounded-2xl border border-dashed border-border/60 bg-background/40 p-4 text-sm text-muted-foreground">
          {emptyLabel}
        </div>
      )}
    </section>
  );
}

export function ParcelaDetalheDialog({
  associadoId,
  target,
  onOpenChange,
}: {
  associadoId: number;
  target: ParcelaDetailTarget | null;
  onOpenChange: (open: boolean) => void;
}) {
  const { hasRole } = usePermissions();
  const isAgent = hasRole("AGENTE") && !hasRole("ADMIN");
  const detalheQuery = useQuery({
    queryKey: [
      "parcela-detalhe",
      associadoId,
      target?.contratoId,
      target?.referenciaMes,
      target?.kind,
    ],
    queryFn: () =>
      apiFetch<ParcelaDetail>(`associados/${associadoId}/parcela-detalhe`, {
        query: {
          contrato_id: target?.contratoId,
          referencia_mes: target?.referenciaMes,
          kind: target?.kind,
        },
      }),
    enabled: Boolean(target),
  });

  const detail = detalheQuery.data;
  const documentosCiclo = detail
    ? detail.termo_antecipacao
      ? [detail.termo_antecipacao, ...detail.documentos_ciclo]
      : detail.documentos_ciclo
    : [];

  return (
    <Dialog open={Boolean(target)} onOpenChange={onOpenChange}>
      <DialogContent className="w-[min(96vw,72rem)] max-h-[88vh] overflow-hidden p-0 sm:max-w-none xl:w-[min(96vw,78rem)]">
        <div className="overflow-y-auto overflow-x-hidden px-5 pb-5 pt-6 sm:px-6 sm:pb-6">
          <DialogHeader className="pr-12">
            <DialogTitle className="break-words pr-10">
              {detail?.numero_parcela
                ? `Parcela ${detail.numero_parcela} • ${formatMonthYear(detail?.referencia_mes)}`
                : `Competência ${formatMonthYear(detail?.referencia_mes ?? target?.referenciaMes)}`}
            </DialogTitle>
            <DialogDescription className="break-all pr-10">
              {detail
                ? `${detail.contrato_codigo}${detail.cycle_number ? ` · Ciclo ${detail.cycle_number}` : ""}`
                : "Carregando detalhes da competência."}
            </DialogDescription>
          </DialogHeader>

          {detalheQuery.isLoading ? (
            <div className="flex min-h-56 items-center justify-center">
              <LoaderCircleIcon className="size-6 animate-spin text-primary" />
            </div>
          ) : detalheQuery.isError ? (
            <div className="rounded-2xl border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
              {detalheQuery.error instanceof Error
                ? detalheQuery.error.message
                : "Falha ao carregar o detalhe da parcela."}
            </div>
          ) : detail ? (
            <div className="space-y-6">
              <section className="overflow-hidden rounded-2xl border border-border/60 bg-card/60 p-4">
                <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                  <div className="min-w-0">
                    <p className="break-all text-sm font-medium text-foreground">
                      {detail.contrato_codigo}
                    </p>
                <p className="mt-1 break-words text-sm text-muted-foreground">
                  {formatMonthYear(detail.referencia_mes)} · {formatCurrency(detail.valor)}
                </p>
              </div>
                  <div className="flex flex-wrap items-center gap-2 xl:max-w-[45%] xl:justify-end">
                    <StatusBadge
                      status={detail.status}
                      className="max-w-full whitespace-normal text-center"
                    />
                  </div>
                </div>
              </section>

              <section className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-4">
                <DetailItem
                  label="Data de pagamento"
                  value={formatDate(detail.data_pagamento)}
                />
                <DetailItem
                  label="Importação do arquivo"
                  value={formatDateTime(detail.data_importacao_arquivo)}
                />
                <DetailItem
                  label="Baixa manual"
                  value={formatDate(detail.data_baixa_manual)}
                />
                <DetailItem
                  label="Pagamento da tesouraria"
                  value={formatDateTime(detail.data_pagamento_tesouraria)}
                />
              </section>

              <section className="overflow-hidden rounded-2xl border border-border/60 bg-background/50 p-4">
                <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
                  Observação
                </p>
                <p className="mt-2 break-words text-sm text-foreground">
                  {detail.observacao || "Sem observação para esta competência."}
                </p>
              </section>

              {isAgent && !detail.competencia_evidencias.length ? null : (
                <EvidenceSection
                  title="Anexos da competência"
                  evidences={detail.competencia_evidencias}
                  emptyLabel="Nenhuma evidência anexada para esta competência."
                />
              )}

              <EvidenceSection
                title={isAgent ? "Comprovantes do agente" : "Documentos do ciclo"}
                evidences={documentosCiclo}
                emptyLabel="Nenhum documento de tesouraria ou renovação vinculado a este ciclo."
              />
            </div>
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}
