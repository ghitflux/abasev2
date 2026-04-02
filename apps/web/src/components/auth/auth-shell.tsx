"use client";

import type * as React from "react";
import Image from "next/image";

import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";

type AuthShellProps = {
  heroBadge?: string;
  heroTitle?: React.ReactNode;
  heroDescription?: React.ReactNode;
  heroImageSrc?: string;
  heroImageAlt?: string;
  heroImagePosition?: string;
  heroAlign?: "start" | "center" | "end";
  heroTextAlign?: "start" | "center" | "end";
  cardBadge?: string;
  cardTitle?: string;
  cardDescription?: string;
  showCardLogo?: boolean;
  children: React.ReactNode;
  footer?: React.ReactNode;
};

export default function AuthShell({
  heroBadge,
  heroTitle,
  heroDescription,
  heroImageSrc,
  heroImageAlt = "Destaque ABASE",
  heroImagePosition = "62% center",
  heroAlign = "start",
  heroTextAlign,
  cardBadge,
  cardTitle,
  cardDescription,
  showCardLogo = false,
  children,
  footer,
}: AuthShellProps) {
  const heroIsRightAligned = heroAlign === "end";
  const heroIsCentered = heroAlign === "center";
  const resolvedHeroTextAlign = heroTextAlign ?? heroAlign;
  const heroTextIsRightAligned = resolvedHeroTextAlign === "end";
  const heroTextIsCentered = resolvedHeroTextAlign === "center";
  const heroWrapperAlignment = heroIsCentered
    ? "justify-center"
    : heroIsRightAligned
      ? "justify-end"
      : "justify-start";
  const heroBlockAlignment = heroIsCentered
    ? heroTextIsCentered
      ? "mx-auto items-center text-center"
      : heroTextIsRightAligned
        ? "mx-auto items-end text-right"
        : "mx-auto items-start text-left"
    : heroIsRightAligned
      ? "ml-auto items-end text-right"
      : "items-start text-left";

  return (
    <main className="grid min-h-screen overflow-hidden bg-[linear-gradient(180deg,hsl(228_18%_10%),hsl(228_18%_7%))] lg:grid-cols-[1.16fr_0.84fr]">
      <section className="relative hidden min-h-screen overflow-hidden border-r border-border/60 lg:flex">
        {heroImageSrc ? (
          <div className="absolute inset-0">
            <Image
              src={heroImageSrc}
              alt={heroImageAlt}
              fill
              priority
              className="object-cover opacity-55"
              style={{ objectPosition: heroImagePosition }}
            />
          </div>
        ) : null}
        <div className="absolute inset-0 bg-[linear-gradient(90deg,hsl(228_18%_8%/0.96)_0%,hsl(228_18%_8%/0.78)_44%,hsl(228_18%_8%/0.7)_100%),radial-gradient(circle_at_top_left,hsl(22_95%_56%/0.35),transparent_24%),radial-gradient(circle_at_72%_48%,hsl(160_48%_28%/0.18),transparent_34%)]" />
        <div className="absolute inset-0 bg-[linear-gradient(hsl(0_0%_100%/0.04)_1px,transparent_1px),linear-gradient(90deg,hsl(0_0%_100%/0.04)_1px,transparent_1px)] bg-[size:24px_24px] opacity-40" />

        <div className="relative z-10 grid h-full w-full grid-rows-[1fr_auto] p-12 xl:p-16">
          <div className={`flex items-center ${heroWrapperAlignment}`}>
            <div className="space-y-8">
              {heroBadge ? (
                <div className="inline-flex w-fit items-center rounded-full border border-primary/30 bg-black/20 px-4 py-2 text-[11px] font-medium tracking-[0.34em] text-primary uppercase backdrop-blur-sm">
                  {heroBadge}
                </div>
              ) : null}

              <div className={`flex max-w-[34rem] flex-col space-y-8 ${heroBlockAlignment}`}>
                <Image
                  src="/abase-logo-white.png"
                  alt="ABASE"
                  width={420}
                  height={122}
                  priority
                  className="h-auto w-auto object-contain drop-shadow-[0_18px_48px_rgba(0,0,0,0.45)]"
                />

                {heroTitle ? (
                  <div className="max-w-[32rem] text-6xl leading-[0.94] font-semibold tracking-[-0.06em] text-white text-balance">
                    {heroTitle}
                  </div>
                ) : null}

                {heroDescription ? (
                  <div className="max-w-[30rem] text-lg leading-8 text-white/74">{heroDescription}</div>
                ) : null}
              </div>
            </div>
          </div>

          <div
            className={`max-w-[18rem] text-xs leading-6 tracking-[0.28em] text-white/42 uppercase ${
              heroIsCentered
                ? heroTextIsCentered
                  ? "mx-auto text-center"
                  : heroTextIsRightAligned
                    ? "mx-auto text-right"
                    : "mx-auto text-left"
                : heroIsRightAligned
                  ? "ml-auto text-right"
                  : ""
            }`}
          >
            Associação beneficente e assistencial dos servidores públicos
          </div>
        </div>
      </section>

      <section className="relative flex items-center justify-center px-6 py-10 sm:px-8 lg:px-10">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,hsl(22_95%_56%/0.16),transparent_26%),radial-gradient(circle_at_bottom,hsl(165_48%_28%/0.12),transparent_28%),linear-gradient(180deg,hsl(228_18%_10%),hsl(228_18%_8%))]" />
        <Card className="glass-panel relative z-10 w-full max-w-xl rounded-[2.1rem] border-white/10 bg-[linear-gradient(180deg,hsl(224_16%_12%/0.98),hsl(224_16%_10%/0.98))] py-8 shadow-[0_28px_90px_rgba(0,0,0,0.45)] backdrop-blur-xl">
          {(cardBadge || cardTitle || cardDescription || showCardLogo) ? (
            <CardHeader className="space-y-6 px-8 pb-6">
              <div className="space-y-4">
                {cardBadge ? (
                  <div className="inline-flex w-fit items-center rounded-full border border-primary/25 bg-primary/10 px-3 py-1 text-[11px] font-medium tracking-[0.28em] text-primary uppercase">
                    {cardBadge}
                  </div>
                ) : null}
                {showCardLogo ? (
                  <Image
                    src="/abase-logo-white.png"
                    alt="ABASE"
                    width={220}
                    height={64}
                    className="h-auto w-auto object-contain"
                    priority
                  />
                ) : null}
              </div>

              {(cardTitle || cardDescription) ? (
                <div className="space-y-3">
                  {cardTitle ? <CardTitle className="text-4xl leading-none tracking-[-0.04em]">{cardTitle}</CardTitle> : null}
                  {cardDescription ? (
                    <CardDescription className="max-w-lg text-base leading-7 text-white/64">
                      {cardDescription}
                    </CardDescription>
                  ) : null}
                </div>
              ) : null}
            </CardHeader>
          ) : null}

          <CardContent className="px-8">{children}</CardContent>
          {footer ? <CardFooter className="px-8 pt-2">{footer}</CardFooter> : null}
        </Card>
      </section>
    </main>
  );
}
