"use client";

import * as React from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Checkbox } from "@/components/ui/checkbox";
import { Field, FieldContent, FieldError, FieldLabel } from "@/components/ui/field";
import { Textarea } from "@/components/ui/textarea";

const schema = z.object({
  motivo: z.string().min(5, "Informe o motivo da alteração."),
  confirmacao: z.boolean().refine((value) => value, "Confirme a operação para continuar."),
});

type FormValues = z.infer<typeof schema>;

type AdminOverrideConfirmDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  summary?: React.ReactNode;
  submitLabel?: string;
  isSubmitting?: boolean;
  onConfirm: (motivo: string) => Promise<void> | void;
};

export default function AdminOverrideConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  summary,
  submitLabel = "Salvar alteração",
  isSubmitting = false,
  onConfirm,
}: AdminOverrideConfirmDialogProps) {
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      motivo: "",
      confirmacao: false,
    },
  });

  React.useEffect(() => {
    if (!open) {
      form.reset({
        motivo: "",
        confirmacao: false,
      });
    }
  }, [form, open]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-[min(96vw,42rem)] max-h-[88vh] overflow-y-auto sm:max-w-none">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description ? <DialogDescription>{description}</DialogDescription> : null}
        </DialogHeader>

        {summary ? (
          <div className="rounded-2xl border border-border/60 bg-background/60 p-4 text-sm text-muted-foreground">
            {summary}
          </div>
        ) : null}

        <form
          className="space-y-4"
          onSubmit={form.handleSubmit(async (values) => {
            await onConfirm(values.motivo);
            onOpenChange(false);
          })}
        >
          <Field>
            <FieldLabel>Motivo</FieldLabel>
            <FieldContent>
              <Textarea
                rows={4}
                placeholder="Descreva o motivo da alteração administrativa."
                {...form.register("motivo")}
              />
              {form.formState.errors.motivo ? (
                <FieldError>{form.formState.errors.motivo.message}</FieldError>
              ) : null}
            </FieldContent>
          </Field>

          <Field>
            <FieldContent>
              <label className="flex items-start gap-3 rounded-2xl border border-border/60 bg-background/60 p-4 text-sm">
                <Checkbox
                  checked={form.watch("confirmacao")}
                  onCheckedChange={(checked) =>
                    form.setValue("confirmacao", checked === true, { shouldValidate: true })
                  }
                />
                <span>
                  Confirmo que esta alteração grava imediatamente no banco e ficará registrada no
                  histórico do associado.
                </span>
              </label>
              {form.formState.errors.confirmacao ? (
                <FieldError>{form.formState.errors.confirmacao.message}</FieldError>
              ) : null}
            </FieldContent>
          </Field>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {submitLabel}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
