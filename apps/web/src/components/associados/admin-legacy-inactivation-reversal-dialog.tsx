"use client";

import * as React from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldContent, FieldError, FieldLabel } from "@/components/ui/field";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

const STATUS_OPTIONS = [
  { value: "cadastrado", label: "Cadastrado" },
  { value: "importado", label: "Importado" },
  { value: "em_analise", label: "Em análise" },
  { value: "ativo", label: "Ativo" },
  { value: "pendente", label: "Pendente" },
  { value: "apto_a_renovar", label: "Apto a renovar" },
] as const;

const ETAPA_OPTIONS = [
  { value: "cadastro", label: "Cadastro" },
  { value: "analise", label: "Análise" },
  { value: "coordenacao", label: "Coordenação" },
  { value: "tesouraria", label: "Tesouraria" },
] as const;

const SITUACAO_OPTIONS = [
  { value: "aguardando", label: "Aguardando" },
  { value: "em_andamento", label: "Em andamento" },
  { value: "pendenciado", label: "Pendenciado" },
  { value: "aprovado", label: "Aprovado" },
] as const;

type LegacyInactivationReversalPayload = {
  motivo: string;
  status_retorno: string;
  etapa_esteira: string;
  status_esteira: string;
  observacao_esteira: string;
};

type AdminLegacyInactivationReversalDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  currentStatus?: string | null;
  defaultStatus?: string | null;
  defaultStage?: string | null;
  defaultQueueStatus?: string | null;
  isSubmitting?: boolean;
  onConfirm: (payload: LegacyInactivationReversalPayload) => Promise<void> | void;
};

export default function AdminLegacyInactivationReversalDialog({
  open,
  onOpenChange,
  currentStatus,
  defaultStatus,
  defaultStage,
  defaultQueueStatus,
  isSubmitting = false,
  onConfirm,
}: AdminLegacyInactivationReversalDialogProps) {
  const [motivo, setMotivo] = React.useState("");
  const [statusRetorno, setStatusRetorno] = React.useState(defaultStatus || "ativo");
  const [etapaEsteira, setEtapaEsteira] = React.useState(defaultStage || "analise");
  const [statusEsteira, setStatusEsteira] = React.useState(
    defaultQueueStatus || "aguardando",
  );
  const [observacaoEsteira, setObservacaoEsteira] = React.useState("");
  const [confirmado, setConfirmado] = React.useState(false);

  React.useEffect(() => {
    if (!open) {
      setMotivo("");
      setStatusRetorno(defaultStatus || "ativo");
      setEtapaEsteira(defaultStage || "analise");
      setStatusEsteira(defaultQueueStatus || "aguardando");
      setObservacaoEsteira("");
      setConfirmado(false);
    }
  }, [defaultQueueStatus, defaultStage, defaultStatus, open]);

  const motivoError =
    motivo.trim().length >= 5 ? "" : "Informe o motivo da reversão assistida.";
  const confirmacaoError = confirmado ? "" : "Confirme a operação para continuar.";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-[min(96vw,44rem)] max-h-[88vh] overflow-y-auto sm:max-w-none">
        <DialogHeader>
          <DialogTitle>Reverter inativação legada</DialogTitle>
          <DialogDescription>
            Use esta ação quando a inativação foi feita antes da gravação automática
            de snapshots e precisa ser reaberta manualmente.
          </DialogDescription>
        </DialogHeader>

        <div className="rounded-2xl border border-border/60 bg-background/60 p-4 text-sm text-muted-foreground">
          <p>
            Status atual do associado:{" "}
            <span className="font-medium text-foreground">
              {currentStatus?.replaceAll("_", " ") || "inativo"}
            </span>
          </p>
          <p className="mt-2">
            A reversão assistida cria um registro administrativo novo e reabre a
            esteira com os valores informados abaixo.
          </p>
        </div>

        <div className="space-y-4">
          <Field>
            <FieldLabel>Status de retorno</FieldLabel>
            <FieldContent>
              <Select value={statusRetorno} onValueChange={setStatusRetorno}>
                <SelectTrigger>
                  <SelectValue placeholder="Selecione o status de retorno" />
                </SelectTrigger>
                <SelectContent>
                  {STATUS_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FieldContent>
          </Field>

          <div className="grid gap-4 md:grid-cols-2">
            <Field>
              <FieldLabel>Etapa da esteira</FieldLabel>
              <FieldContent>
                <Select value={etapaEsteira} onValueChange={setEtapaEsteira}>
                  <SelectTrigger>
                    <SelectValue placeholder="Selecione a etapa" />
                  </SelectTrigger>
                  <SelectContent>
                    {ETAPA_OPTIONS.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </FieldContent>
            </Field>

            <Field>
              <FieldLabel>Situação da esteira</FieldLabel>
              <FieldContent>
                <Select value={statusEsteira} onValueChange={setStatusEsteira}>
                  <SelectTrigger>
                    <SelectValue placeholder="Selecione a situação" />
                  </SelectTrigger>
                  <SelectContent>
                    {SITUACAO_OPTIONS.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </FieldContent>
            </Field>
          </div>

          <Field>
            <FieldLabel>Observação da esteira</FieldLabel>
            <FieldContent>
              <Textarea
                rows={3}
                placeholder="Observação operacional opcional para a fila reaberta."
                value={observacaoEsteira}
                onChange={(event) => setObservacaoEsteira(event.target.value)}
              />
            </FieldContent>
          </Field>

          <Field>
            <FieldLabel>Motivo</FieldLabel>
            <FieldContent>
              <Textarea
                rows={4}
                placeholder="Descreva por que a inativação histórica precisa ser revertida."
                value={motivo}
                onChange={(event) => setMotivo(event.target.value)}
              />
              {motivoError ? <FieldError>{motivoError}</FieldError> : null}
            </FieldContent>
          </Field>

          <Field>
            <FieldContent>
              <label className="flex items-start gap-3 rounded-2xl border border-border/60 bg-background/60 p-4 text-sm">
                <Checkbox
                  checked={confirmado}
                  onCheckedChange={(checked) => setConfirmado(checked === true)}
                />
                <span>
                  Confirmo que a reversão assistida reabre o associado sem usar o
                  fluxo padrão de reativação e ficará registrada no histórico.
                </span>
              </label>
              {confirmacaoError ? <FieldError>{confirmacaoError}</FieldError> : null}
            </FieldContent>
          </Field>
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Cancelar
          </Button>
          <Button
            type="button"
            disabled={isSubmitting || Boolean(motivoError) || Boolean(confirmacaoError)}
            onClick={() =>
              onConfirm({
                motivo: motivo.trim(),
                status_retorno: statusRetorno,
                etapa_esteira: etapaEsteira,
                status_esteira: statusEsteira,
                observacao_esteira: observacaoEsteira.trim(),
              })
            }
          >
            Reverter inativação legada
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
