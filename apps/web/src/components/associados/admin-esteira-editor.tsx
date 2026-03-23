"use client";

import * as React from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CircleHelpIcon } from "lucide-react";
import { toast } from "sonner";

import type { EsteiraResumo } from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import AdminOverrideConfirmDialog from "@/components/associados/admin-override-confirm-dialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

const etapaOptions = ["cadastro", "analise", "coordenacao", "tesouraria", "concluido"];
const situacaoOptions = ["aguardando", "em_andamento", "pendenciado", "aprovado", "rejeitado"];

type Props = {
  associadoId: number;
  esteira: EsteiraResumo | null | undefined;
};

function AdminEsteiraLabel({
  label,
  tooltip,
}: {
  label: string;
  tooltip: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">{label}</p>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            className="inline-flex size-4 items-center justify-center rounded-full text-muted-foreground transition hover:text-foreground"
            aria-label={`Ajuda sobre ${label}`}
          >
            <CircleHelpIcon className="size-3.5" />
          </button>
        </TooltipTrigger>
        <TooltipContent side="top" sideOffset={8} className="max-w-xs rounded-xl">
          {tooltip}
        </TooltipContent>
      </Tooltip>
    </div>
  );
}

export default function AdminEsteiraEditor({ associadoId, esteira }: Props) {
  const queryClient = useQueryClient();
  const [open, setOpen] = React.useState(false);
  const [draft, setDraft] = React.useState({
    etapa_atual: esteira?.etapa_atual || "analise",
    status: esteira?.status || "aguardando",
    prioridade: String(esteira?.prioridade ?? 3),
    observacao: "",
  });

  React.useEffect(() => {
    setDraft({
      etapa_atual: esteira?.etapa_atual || "analise",
      status: esteira?.status || "aguardando",
      prioridade: String(esteira?.prioridade ?? 3),
      observacao: "",
    });
  }, [esteira]);

  const mutation = useMutation({
    mutationFn: async (motivo: string) =>
      apiFetch(`admin-overrides/associados/${associadoId}/esteira/status/`, {
        method: "POST",
        body: {
          updated_at: esteira?.updated_at ?? null,
          motivo,
          etapa_atual: draft.etapa_atual,
          status: draft.status,
          prioridade: Number(draft.prioridade || 3),
          observacao: draft.observacao,
        },
      }),
    onSuccess: async () => {
      toast.success("Esteira atualizada.");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["associado", associadoId] }),
        queryClient.invalidateQueries({ queryKey: ["admin-associado-editor", associadoId] }),
        queryClient.invalidateQueries({ queryKey: ["admin-associado-history", associadoId] }),
      ]);
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Falha ao atualizar a esteira.");
    },
  });

  if (!esteira) {
    return null;
  }

  return (
    <TooltipProvider delayDuration={120}>
      <Card className="mb-4 rounded-[1.5rem] border-primary/20 bg-primary/5">
      <CardHeader className="flex flex-row items-center justify-between gap-3">
        <CardTitle className="text-base">Override da Esteira</CardTitle>
        <Button type="button" variant="outline" onClick={() => setOpen(true)}>
          Salvar etapa
        </Button>
      </CardHeader>
      <CardContent className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div className="space-y-2">
          <AdminEsteiraLabel
            label="Etapa"
            tooltip="Fase atual do fluxo operacional do associado na esteira."
          />
          <Select value={draft.etapa_atual} onValueChange={(value) => setDraft((current) => ({ ...current, etapa_atual: value }))}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              {etapaOptions.map((item) => (
                <SelectItem key={item} value={item}>{item.replaceAll("_", " ")}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <AdminEsteiraLabel
            label="Situação"
            tooltip="Situação de andamento da etapa atual na esteira."
          />
          <Select value={draft.status} onValueChange={(value) => setDraft((current) => ({ ...current, status: value }))}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              {situacaoOptions.map((item) => (
                <SelectItem key={item} value={item}>{item.replaceAll("_", " ")}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <AdminEsteiraLabel
            label="Prioridade"
            tooltip="Peso operacional para ordenar o atendimento deste associado na fila."
          />
          <Input
            type="number"
            min={1}
            value={draft.prioridade}
            onChange={(event) => setDraft((current) => ({ ...current, prioridade: event.target.value }))}
          />
        </div>
        <div className="space-y-2 md:col-span-2 xl:col-span-1">
          <AdminEsteiraLabel
            label="Observação"
            tooltip="Contexto livre para registrar exceções e decisões sobre a esteira."
          />
          <Textarea
            rows={3}
            value={draft.observacao}
            onChange={(event) => setDraft((current) => ({ ...current, observacao: event.target.value }))}
          />
        </div>
      </CardContent>

      <AdminOverrideConfirmDialog
        open={open}
        onOpenChange={setOpen}
        title="Salvar override da esteira"
        description="A etapa e a situação do associado serão ajustadas manualmente."
        summary={
          <div className="grid gap-2 text-sm">
            <p>Etapa: <span className="font-medium text-foreground">{draft.etapa_atual}</span></p>
            <p>Situação: <span className="font-medium text-foreground">{draft.status}</span></p>
            <p>Prioridade: <span className="font-medium text-foreground">{draft.prioridade}</span></p>
          </div>
        }
        submitLabel="Salvar esteira"
        isSubmitting={mutation.isPending}
        onConfirm={async (motivo) => {
          await mutation.mutateAsync(motivo);
        }}
      />
      </Card>
    </TooltipProvider>
  );
}
