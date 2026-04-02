"use client";

import type * as React from "react";
import Image from "next/image";

import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { H1, Lead } from "@/components/ui/typography";

type AuthShellProps = {
  badge: string;
  title: string;
  description: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
};

export default function AuthShell({
  badge,
  title,
  description,
  children,
  footer,
}: AuthShellProps) {
  return (
    <main className="grid min-h-screen bg-[radial-gradient(circle_at_top_left,hsl(24_95%_55%/0.16),transparent_22%),radial-gradient(circle_at_85%_15%,hsl(180_55%_35%/0.16),transparent_28%),linear-gradient(180deg,hsl(230_18%_10%),hsl(228_18%_7%))] lg:grid-cols-[1.2fr_0.8fr]">
      <section className="dashboard-grid relative hidden overflow-hidden border-r border-border/60 lg:flex">
        <div className="absolute inset-0 bg-[linear-gradient(180deg,hsl(0_0%_100%/0.02),transparent_32%),radial-gradient(circle_at_top_left,hsl(28_100%_60%/0.18),transparent_24%),radial-gradient(circle_at_72%_28%,hsl(165_60%_35%/0.14),transparent_30%)]" />
        <div className="relative flex w-full flex-col justify-between p-12">
          <div className="inline-flex w-fit items-center rounded-full border border-primary/30 bg-primary/10 px-4 py-2 text-xs font-medium tracking-[0.28em] text-primary uppercase">
            {badge}
          </div>
          <div className="flex max-w-2xl flex-col items-start gap-8">
            <Image
              src="/abase-logo-white.png"
              alt="ABASE"
              width={360}
              height={104}
              className="h-auto w-auto object-contain"
              priority
            />
            <div className="space-y-5">
              <H1 className="max-w-3xl text-5xl leading-tight xl:text-6xl">
                Operação, análise e financeiro do associado no mesmo fluxo.
              </H1>
              <Lead className="max-w-xl text-base text-muted-foreground/90 xl:text-lg">
                Acompanhe a esteira completa, aprove contratos, valide documentos e mantenha a
                sessão operacional ativa sem depender de integrações externas para o acesso do
                agente.
              </Lead>
            </div>
          </div>
          <div className="text-sm text-muted-foreground">
            Portal interno para times de operação, coordenação, tesouraria e agentes.
          </div>
        </div>
      </section>

      <section className="relative flex items-center justify-center px-6 py-10 sm:px-8 lg:px-10">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,hsl(28_100%_60%/0.14),transparent_26%),linear-gradient(180deg,hsl(228_18%_10%),hsl(228_18%_8%))] lg:hidden" />
        <Card className="glass-panel relative w-full max-w-lg rounded-[2rem] border-border/60 bg-card/92 py-8 shadow-2xl shadow-black/35 backdrop-blur-xl">
          <CardHeader className="space-y-5 px-8">
            <div className="space-y-4">
              <div className="inline-flex w-fit items-center rounded-full border border-primary/25 bg-primary/10 px-3 py-1 text-[11px] font-medium tracking-[0.22em] text-primary uppercase">
                {badge}
              </div>
              <Image
                src="/abase-logo-white.png"
                alt="ABASE"
                width={220}
                height={64}
                className="h-auto w-auto object-contain"
                priority
              />
            </div>
            <div className="space-y-2">
              <CardTitle className="text-3xl leading-tight">{title}</CardTitle>
              <CardDescription className="max-w-md text-sm leading-6 text-muted-foreground">
                {description}
              </CardDescription>
            </div>
          </CardHeader>
          <CardContent className="px-8">{children}</CardContent>
          {footer ? <CardFooter className="px-8">{footer}</CardFooter> : null}
        </Card>
      </section>
    </main>
  );
}
