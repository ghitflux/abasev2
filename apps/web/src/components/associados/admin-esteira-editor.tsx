"use client";

import * as React from "react";
import { CircleHelpIcon } from "lucide-react";

import type { EsteiraResumo } from "@/lib/api/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import StatusBadge from "@/components/custom/status-badge";

const etapaOptions = ["cadastro", "analise", "coordenacao", "tesouraria", "concluido"];
const situacaoOptions = ["aguardando", "em_andamento", "pendenciado", "aprovado", "rejeitado"];

type Props = {
  esteira: EsteiraResumo | null | undefined;
  onDirtyChange?: (dirty: boolean) => void;
};

export type AdminEsteiraPendingChanges = {
  updated_at: string | null;
  etapa_atual: string;
  status: string;
  prioridade: number;
  observacao: string;
};

export type AdminEsteiraEditorHandle = {
  getPendingChanges: () => AdminEsteiraPendingChanges | null;
  hasPendingChanges: () => boolean;
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

function buildEsteiraPayload(
  draft: {
    etapa_atual: string;
    status: string;
    prioridade: string;
    observacao: string;
  },
  updatedAt?: string | null,
): AdminEsteiraPendingChanges {
  return {
    updated_at: updatedAt ?? null,
    etapa_atual: draft.etapa_atual,
    status: draft.status,
    prioridade: Number(draft.prioridade || 3),
    observacao: draft.observacao,
  };
}

const AdminEsteiraEditor = React.forwardRef<AdminEsteiraEditorHandle, Props>(function AdminEsteiraEditor({
  esteira,
  onDirtyChange,
}: Props, ref) {
  const onDirtyChangeEvent = React.useEffectEvent((dirty: boolean) => {
    onDirtyChange?.(dirty);
  });
  const resolvedEtapa = esteira?.etapa_atual || "analise";
  const resolvedStatus = esteira?.status || "aguardando";
  const resolvedPrioridade = String(esteira?.prioridade ?? 3);
  const [draft, setDraft] = React.useState({
    etapa_atual: resolvedEtapa,
    status: resolvedStatus,
    prioridade: resolvedPrioridade,
    observacao: esteira?.observacao || "",
  });

  React.useEffect(() => {
    setDraft({
      etapa_atual: resolvedEtapa,
      status: resolvedStatus,
      prioridade: resolvedPrioridade,
      observacao: esteira?.observacao || "",
    });
  }, [esteira?.observacao, resolvedEtapa, resolvedPrioridade, resolvedStatus]);

  const initialPayload = React.useMemo(
    () =>
      buildEsteiraPayload(
        {
          etapa_atual: resolvedEtapa,
          status: resolvedStatus,
          prioridade: resolvedPrioridade,
          observacao: esteira?.observacao || "",
        },
        esteira?.updated_at,
      ),
    [esteira?.observacao, esteira?.updated_at, resolvedEtapa, resolvedPrioridade, resolvedStatus],
  );
  const currentPayload = React.useMemo(
    () => buildEsteiraPayload(draft, esteira?.updated_at),
    [draft, esteira?.updated_at],
  );
  const isDirty = React.useMemo(
    () => JSON.stringify(initialPayload) !== JSON.stringify(currentPayload),
    [currentPayload, initialPayload],
  );

  React.useEffect(() => {
    onDirtyChangeEvent?.(isDirty);
  }, [isDirty]);

  React.useImperativeHandle(
    ref,
    () => ({
      getPendingChanges() {
        return isDirty ? currentPayload : null;
      },
      hasPendingChanges() {
        return isDirty;
      },
    }),
    [currentPayload, isDirty],
  );

  if (!esteira) {
    return null;
  }

  return (
    <TooltipProvider delayDuration={120}>
      <Card className="mb-4 rounded-[1.5rem] border-primary/20 bg-primary/5">
      <CardHeader className="flex flex-row items-center justify-between gap-3">
        <CardTitle className="text-base">Override da Esteira</CardTitle>
        {isDirty ? <StatusBadge status="pendente" label="Esteira pendente" /> : <StatusBadge status="ativo" label="Sem alterações" />}
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
      </Card>
    </TooltipProvider>
  );
});

AdminEsteiraEditor.displayName = "AdminEsteiraEditor";

export default AdminEsteiraEditor;
