"use client";

import * as React from "react";
import { RotateCcwIcon } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import type { AdminOverrideHistoryEvent } from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import { formatDateTime, formatMonthYear } from "@/lib/formatters";
import StatusBadge from "@/components/custom/status-badge";
import { Button } from "@/components/ui/button";
import AdminOverrideConfirmDialog from "@/components/associados/admin-override-confirm-dialog";

type AdminOverrideHistoryProps = {
  associadoId: number;
  events: AdminOverrideHistoryEvent[];
};

export default function AdminOverrideHistory({
  associadoId,
  events,
}: AdminOverrideHistoryProps) {
  const [pendingEvent, setPendingEvent] = React.useState<AdminOverrideHistoryEvent | null>(null);
  const queryClient = useQueryClient();

  const revertMutation = useMutation({
    mutationFn: async ({
      eventId,
      motivo,
    }: {
      eventId: number;
      motivo: string;
    }) =>
      apiFetch(`admin-overrides/events/${eventId}/reverter/`, {
        method: "POST",
        body: { motivo_reversao: motivo },
      }),
    onSuccess: async () => {
      toast.success("Operação revertida.");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["associado", associadoId] }),
        queryClient.invalidateQueries({ queryKey: ["admin-associado-editor", associadoId] }),
        queryClient.invalidateQueries({ queryKey: ["admin-associado-history", associadoId] }),
      ]);
      setPendingEvent(null);
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Falha ao reverter a operação.");
    },
  });

  if (!events.length) {
    return <p className="text-sm text-muted-foreground">Nenhuma alteração administrativa registrada.</p>;
  }

  return (
    <div className="space-y-4">
      {events.map((event) => (
        <div
          key={event.id}
          className="rounded-[1.5rem] border border-border/60 bg-background/50 p-4"
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="font-medium">{event.resumo}</p>
              <p className="mt-1 text-sm text-muted-foreground">
                {event.realizado_por?.full_name || "Sistema"} · {formatDateTime(event.created_at)}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge
                status={event.revertida_em ? "revertido" : "concluido"}
                label={event.revertida_em ? "Revertido" : "Ativo"}
              />
              {!event.revertida_em ? (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setPendingEvent(event)}
                >
                  <RotateCcwIcon className="mr-2 size-4" />
                  Reverter
                </Button>
              ) : null}
            </div>
          </div>

          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <div className="rounded-2xl border border-border/60 bg-background/60 p-4 text-sm">
              <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Motivo</p>
              <p className="mt-2 text-foreground">{event.motivo}</p>
            </div>
            <div className="rounded-2xl border border-border/60 bg-background/60 p-4 text-sm">
              <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">Escopo</p>
              <p className="mt-2 text-foreground capitalize">{event.escopo.replaceAll("_", " ")}</p>
              {event.revertida_em ? (
                <p className="mt-2 text-muted-foreground">
                  Revertida em {formatDateTime(event.revertida_em)}
                  {event.revertida_por?.full_name ? ` por ${event.revertida_por.full_name}` : ""}.
                </p>
              ) : null}
            </div>
          </div>

          {event.changes.length ? (
            <div className="mt-4 space-y-2">
              <p className="text-sm font-medium text-foreground">Alterações</p>
              <div className="grid gap-3">
                {event.changes.map((change) => (
                  <div
                    key={change.id}
                    className="rounded-2xl border border-border/60 bg-background/60 p-4 text-sm"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <p className="font-medium">{change.resumo}</p>
                      {change.competencia_referencia ? (
                        <span className="text-xs text-muted-foreground">
                          {formatMonthYear(change.competencia_referencia)}
                        </span>
                      ) : null}
                    </div>
                    <p className="mt-1 text-xs uppercase tracking-[0.16em] text-muted-foreground">
                      {change.entity_type.replaceAll("_", " ")} #{change.entity_id}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      ))}

      <AdminOverrideConfirmDialog
        open={Boolean(pendingEvent)}
        onOpenChange={(open) => {
          if (!open) {
            setPendingEvent(null);
          }
        }}
        title="Reverter operação administrativa"
        description="A reversão tenta restaurar o snapshot anterior e também ficará registrada no histórico."
        summary={
          pendingEvent ? (
            <div className="space-y-2">
              <p className="font-medium text-foreground">{pendingEvent.resumo}</p>
              <p>{pendingEvent.motivo}</p>
            </div>
          ) : null
        }
        submitLabel="Reverter operação"
        isSubmitting={revertMutation.isPending}
        onConfirm={async (motivo) => {
          if (!pendingEvent) {
            return;
          }
          await revertMutation.mutateAsync({ eventId: pendingEvent.id, motivo });
        }}
      />
    </div>
  );
}
