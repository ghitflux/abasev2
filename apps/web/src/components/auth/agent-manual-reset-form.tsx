"use client";

import * as React from "react";
import Link from "next/link";
import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowRightIcon, MailIcon } from "lucide-react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import AuthShell from "@/components/auth/auth-shell";
import { Button } from "@/components/ui/button";
import { Field, FieldContent, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";

const manualResetSchema = z
  .object({
    email: z.string().email("Informe um email válido."),
    password: z.string().min(8, "A senha precisa ter pelo menos 8 caracteres."),
    passwordConfirmation: z.string().min(8, "Confirme a nova senha."),
  })
  .refine((values) => values.password === values.passwordConfirmation, {
    message: "A confirmação da senha não confere.",
    path: ["passwordConfirmation"],
  });

type ManualResetValues = z.infer<typeof manualResetSchema>;

export default function AgentManualResetForm() {
  const [isPending, setIsPending] = React.useState(false);
  const form = useForm<ManualResetValues>({
    resolver: zodResolver(manualResetSchema),
    defaultValues: {
      email: "",
      password: "",
      passwordConfirmation: "",
    },
  });

  const onSubmit = form.handleSubmit((values) => {
    setIsPending(true);

    void (async () => {
      try {
        const response = await fetch("/api/auth/agent-manual-reset", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          cache: "no-store",
          body: JSON.stringify(values),
        });

        const payload = await response.json().catch(() => null);
        if (!response.ok) {
          toast.error(payload?.message ?? "Falha ao atualizar a senha.");
          setIsPending(false);
          return;
        }

        toast.success(payload?.message ?? "Senha atualizada.");
        window.setTimeout(() => {
          window.location.replace("/login");
        }, 500);
      } catch {
        toast.error("Falha ao atualizar a senha.");
        setIsPending(false);
      }
    })();
  });

  return (
    <AuthShell
      badge="Recuperação Manual"
      title="Redefinir senha do agente"
      description="Informe o email cadastrado e a nova senha. O fluxo é local ao sistema e não depende de envio de código externo."
      footer={
        <Button asChild className="h-auto px-0 text-sm" variant="link">
          <Link href="/login">Voltar para o login</Link>
        </Button>
      }
    >
      <form className="space-y-6" onSubmit={onSubmit}>
        <FieldGroup>
          <Field>
            <FieldLabel>Email do agente</FieldLabel>
            <FieldContent>
              <div className="relative">
                <MailIcon className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input className="h-12 rounded-2xl pl-10" placeholder="agente@abase.com.br" {...form.register("email")} />
              </div>
              <FieldDescription>
                O reset manual público é restrito a usuários ativos com papel de agente.
              </FieldDescription>
              <FieldError errors={[form.formState.errors.email]} />
            </FieldContent>
          </Field>
          <Field>
            <FieldLabel>Nova senha</FieldLabel>
            <FieldContent>
              <Input className="h-12 rounded-2xl" type="password" placeholder="Nova senha" {...form.register("password")} />
              <FieldError errors={[form.formState.errors.password]} />
            </FieldContent>
          </Field>
          <Field>
            <FieldLabel>Confirmar nova senha</FieldLabel>
            <FieldContent>
              <Input
                className="h-12 rounded-2xl"
                type="password"
                placeholder="Confirme a nova senha"
                {...form.register("passwordConfirmation")}
              />
              <FieldError errors={[form.formState.errors.passwordConfirmation]} />
            </FieldContent>
          </Field>
        </FieldGroup>
        <Button className="h-12 w-full rounded-2xl text-sm font-semibold" disabled={isPending}>
          {isPending ? "Atualizando..." : "Atualizar senha"}
          <ArrowRightIcon className="size-4" />
        </Button>
      </form>
    </AuthShell>
  );
}
