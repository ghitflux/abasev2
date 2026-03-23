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
import FileUploadDropzone from "@/components/custom/file-upload-dropzone";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

const schema = z.object({
  motivo: z.string().min(5, "Informe o motivo da alteração."),
  confirmacao: z.boolean().refine((value) => value, "Confirme a operação para continuar."),
  status: z.string().optional(),
  status_validacao: z.string().optional(),
});

type FormValues = z.infer<typeof schema>;

type FileDialogTarget = {
  kind: "documento" | "comprovante";
  title: string;
  description?: string;
  currentStatus?: string | null;
  currentReference?: string | null;
};

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  target: FileDialogTarget | null;
  isSubmitting?: boolean;
  onSubmit: (payload: {
    motivo: string;
    status?: string;
    status_validacao?: string;
    file?: File | null;
  }) => Promise<void> | void;
};

const documentStatusOptions = ["pendente", "aprovado", "rejeitado", "arquivado"];
const comprovanteStatusOptions = ["pendente", "aprovado", "rejeitado", "arquivado"];

export default function AdminFileVersionDialog({
  open,
  onOpenChange,
  target,
  isSubmitting = false,
  onSubmit,
}: Props) {
  const [file, setFile] = React.useState<File | null>(null);
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      motivo: "",
      confirmacao: false,
      status: undefined,
      status_validacao: undefined,
    },
  });

  React.useEffect(() => {
    if (!open || !target) {
      form.reset({
        motivo: "",
        confirmacao: false,
        status: undefined,
        status_validacao: undefined,
      });
      setFile(null);
      return;
    }
    form.reset({
      motivo: "",
      confirmacao: false,
      status: target.kind === "documento" ? target.currentStatus || undefined : undefined,
      status_validacao:
        target.kind === "comprovante" ? target.currentStatus || undefined : undefined,
    });
    setFile(null);
  }, [form, open, target]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-[min(96vw,42rem)] max-h-[88vh] overflow-y-auto sm:max-w-none">
        <DialogHeader>
          <DialogTitle>{target?.title || "Versionar arquivo"}</DialogTitle>
          {target?.description ? (
            <DialogDescription>{target.description}</DialogDescription>
          ) : null}
        </DialogHeader>

        {target?.currentReference ? (
          <div className="rounded-2xl border border-border/60 bg-background/60 p-4 text-sm text-muted-foreground">
            Arquivo atual: <span className="font-medium text-foreground">{target.currentReference}</span>
          </div>
        ) : null}

        <form
          className="space-y-4"
          onSubmit={form.handleSubmit(async (values) => {
            await onSubmit({
              motivo: values.motivo,
              status: values.status,
              status_validacao: values.status_validacao,
              file,
            });
            onOpenChange(false);
          })}
        >
          <Field>
            <FieldLabel>Novo arquivo</FieldLabel>
            <FieldContent>
              <FileUploadDropzone
                accept={{
                  "application/pdf": [".pdf"],
                  "image/jpeg": [".jpg", ".jpeg"],
                  "image/png": [".png"],
                }}
                maxSize={10 * 1024 * 1024}
                onUpload={(uploaded) => setFile(uploaded)}
              />
            </FieldContent>
          </Field>

          {target?.kind === "documento" ? (
            <Field>
              <FieldLabel>Status do documento</FieldLabel>
              <FieldContent>
                <Select
                  value={form.watch("status")}
                  onValueChange={(value) => form.setValue("status", value, { shouldValidate: true })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Selecione o status" />
                  </SelectTrigger>
                  <SelectContent>
                    {documentStatusOptions.map((status) => (
                      <SelectItem key={status} value={status}>
                        {status.replaceAll("_", " ")}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </FieldContent>
            </Field>
          ) : null}

          {target?.kind === "comprovante" ? (
            <Field>
              <FieldLabel>Status do comprovante</FieldLabel>
              <FieldContent>
                <Select
                  value={form.watch("status_validacao")}
                  onValueChange={(value) =>
                    form.setValue("status_validacao", value, { shouldValidate: true })
                  }
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Selecione o status" />
                  </SelectTrigger>
                  <SelectContent>
                    {comprovanteStatusOptions.map((status) => (
                      <SelectItem key={status} value={status}>
                        {status.replaceAll("_", " ")}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </FieldContent>
            </Field>
          ) : null}

          <Field>
            <FieldLabel>Motivo</FieldLabel>
            <FieldContent>
              <Textarea
                rows={4}
                placeholder="Descreva o motivo da nova versão ou da mudança de status."
                {...form.register("motivo")}
              />
              {form.formState.errors.motivo ? (
                <FieldError>{form.formState.errors.motivo.message}</FieldError>
              ) : null}
            </FieldContent>
          </Field>

          <label className="flex items-start gap-3 rounded-2xl border border-border/60 bg-background/60 p-4 text-sm">
            <Checkbox
              checked={form.watch("confirmacao")}
              onCheckedChange={(checked) =>
                form.setValue("confirmacao", checked === true, { shouldValidate: true })
              }
            />
            <span>Confirmo que a versão anterior deve permanecer no histórico administrativo.</span>
          </label>
          {form.formState.errors.confirmacao ? (
            <FieldError>{form.formState.errors.confirmacao.message}</FieldError>
          ) : null}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              Salvar versão
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
