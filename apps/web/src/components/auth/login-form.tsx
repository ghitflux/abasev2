"use client";

import * as React from "react";
import Link from "next/link";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";
import { ArrowRightIcon, EyeIcon, EyeOffIcon, MailIcon } from "lucide-react";

import { resolvePostLoginPath } from "@/lib/navigation";
import { useRouteTransition } from "@/providers/route-transition-provider";
import { useAuthStore } from "@/store/auth-store";
import AuthShell from "@/components/auth/auth-shell";
import { Button } from "@/components/ui/button";
import { Field, FieldContent, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";

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
  const [showPassword, setShowPassword] = React.useState(false);

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
    <AuthShell
      heroTitle={
        <>
          Unindo forças
          <br />
          em prol de quem serve.
        </>
      }
      heroImageSrc="/auth-hero-woman.webp"
      heroImageAlt="Representacao institucional de atendimento ao associado"
      heroImagePosition="62% 26%"
      heroAlign="end"
      cardTitle="Acesse sua conta"
    >
      <form className="space-y-7" onSubmit={onSubmit}>
        <FieldGroup>
          <Field>
            <FieldLabel className="text-[0.95rem]">Email</FieldLabel>
            <FieldContent>
              <div className="relative">
                <MailIcon className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  className="h-[54px] rounded-2xl border-white/10 bg-black/14 pl-10 text-base"
                  placeholder="voce@abase.com.br"
                  {...form.register("email")}
                />
              </div>
              <FieldError errors={[form.formState.errors.email]} />
            </FieldContent>
          </Field>
          <Field>
            <FieldLabel className="text-[0.95rem]">Senha</FieldLabel>
            <FieldContent>
              <div className="relative">
                <Input
                  className="h-[54px] rounded-2xl border-white/10 bg-black/14 pr-12 text-base"
                  type={showPassword ? "text" : "password"}
                  placeholder="••••••••"
                  {...form.register("password")}
                />
                <button
                  type="button"
                  aria-label={showPassword ? "Ocultar senha" : "Mostrar senha"}
                  className="absolute top-1/2 right-3 -translate-y-1/2 text-muted-foreground transition-colors hover:text-foreground"
                  onClick={() => setShowPassword((current) => !current)}
                >
                  {showPassword ? <EyeOffIcon className="size-4" /> : <EyeIcon className="size-4" />}
                </button>
              </div>
              <FieldError errors={[form.formState.errors.password]} />
            </FieldContent>
          </Field>
        </FieldGroup>
        <Button className="h-[54px] w-full rounded-2xl text-sm font-semibold" disabled={isPending}>
          {isPending ? "Entrando..." : "Entrar"}
          <ArrowRightIcon className="size-4" />
        </Button>
        <div className="flex justify-center">
          <Button asChild className="h-auto px-0 text-sm" variant="link">
            <Link href="/login/recuperar-senha">Recuperar senha</Link>
          </Button>
        </div>
      </form>
    </AuthShell>
  );
}
