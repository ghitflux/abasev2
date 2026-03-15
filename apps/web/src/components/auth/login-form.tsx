"use client";

import * as React from "react";
import Image from "next/image";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";
import { ArrowRightIcon, LockKeyholeIcon, MailIcon } from "lucide-react";

import { resolvePostLoginPath } from "@/lib/navigation";
import { useRouteTransition } from "@/providers/route-transition-provider";
import { useAuthStore } from "@/store/auth-store";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldContent, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { H1, Lead } from "@/components/ui/typography";

const loginSchema = z.object({
  email: z.string().email("Informe um email válido."),
  password: z.string().min(6, "A senha precisa ter pelo menos 6 caracteres."),
});

type LoginValues = z.infer<typeof loginSchema>;

type LoginFormProps = {
  next: string;
};

export default function LoginForm({ next }: LoginFormProps) {
  const { startRouteTransition } = useRouteTransition();
  const clear = useAuthStore((state) => state.clear);
  const setLoading = useAuthStore((state) => state.setLoading);
  const setUser = useAuthStore((state) => state.setUser);
  const [isPending, setIsPending] = React.useState(false);

  const form = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: "",
      password: "",
    },
  });

  React.useEffect(() => {
    clear();
  }, [clear]);

  const onSubmit = form.handleSubmit((values) => {
    setIsPending(true);
    clear();
    setLoading();

    void (async () => {
      try {
        await fetch("/api/auth/logout", {
          method: "POST",
          cache: "no-store",
          credentials: "include",
        }).catch(() => null);

        const response = await fetch("/api/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          cache: "no-store",
          credentials: "include",
          body: JSON.stringify(values),
        });

        const payload = await response.json().catch(() => null);
        if (!response.ok) {
          clear();
          toast.error(payload?.message ?? "Falha ao autenticar.");
          setIsPending(false);
          return;
        }

        setUser(payload.user);
        toast.success("Sessão iniciada.");
        const nextHref = resolvePostLoginPath(
          next,
          payload.user.roles,
          payload.user.primary_role,
        );
        startRouteTransition(nextHref);
        window.location.replace(nextHref);
      } catch {
        clear();
        toast.error("Falha ao autenticar.");
        setIsPending(false);
      }
    })();
  });

  return (
    <main className="grid min-h-screen lg:grid-cols-[1.15fr_0.85fr]">
      <section className="dashboard-grid relative hidden overflow-hidden border-r border-border/60 lg:flex">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_left,hsl(24_95%_55%/0.18),transparent_26%),radial-gradient(circle_at_60%_60%,hsl(150_55%_30%/0.12),transparent_32%)]" />
        <div className="relative flex w-full flex-col justify-between p-10">
          <div />
          <div className="flex flex-col items-start gap-8">
            <Image
              src="/abase-logo-white.png"
              alt="ABASE"
              width={280}
              height={80}
              className="object-contain"
            />
            <div className="max-w-xl space-y-4">
              <H1 className="text-5xl leading-tight">Gestão operacional e financeira do associado em uma única esteira.</H1>
              <Lead className="max-w-lg">
                Cadastro, análise, coordenação, tesouraria e importação do arquivo retorno
                no mesmo fluxo, com autenticação por papel e base pronta para expansão.
              </Lead>
            </div>
          </div>
          <div />
        </div>
      </section>
      <section className="flex items-center justify-center px-6 py-10 sm:px-8">
        <Card className="glass-panel w-full max-w-md rounded-4xl border-border/60 shadow-2xl shadow-black/30">
          <CardHeader className="space-y-3">
            <div className="flex size-12 items-center justify-center rounded-2xl bg-primary/15 text-primary">
              <LockKeyholeIcon className="size-5" />
            </div>
            <div>
              <CardTitle className="text-2xl">Entrar no ABASE v2</CardTitle>
              <CardDescription>
                Use sua credencial do backend para iniciar a sessão no dashboard.
              </CardDescription>
            </div>
          </CardHeader>
          <CardContent>
            <form className="space-y-6" onSubmit={onSubmit}>
              <FieldGroup>
                <Field>
                  <FieldLabel>Email</FieldLabel>
                  <FieldContent>
                    <div className="relative">
                      <MailIcon className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
                      <Input className="pl-10" placeholder="voce@abase.com.br" {...form.register("email")} />
                    </div>
                    <FieldError errors={[form.formState.errors.email]} />
                  </FieldContent>
                </Field>
                <Field>
                  <FieldLabel>Senha</FieldLabel>
                  <FieldContent>
                    <Input type="password" placeholder="••••••••" {...form.register("password")} />
                    <FieldDescription>JWT com access de 15 min e refresh de 7 dias.</FieldDescription>
                    <FieldError errors={[form.formState.errors.password]} />
                  </FieldContent>
                </Field>
              </FieldGroup>
              <Button className="h-11 w-full rounded-2xl" disabled={isPending}>
                {isPending ? "Entrando..." : "Entrar"}
                <ArrowRightIcon className="size-4" />
              </Button>
            </form>
          </CardContent>
        </Card>
      </section>
    </main>
  );
}
