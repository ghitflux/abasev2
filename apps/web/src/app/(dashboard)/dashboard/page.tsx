"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRightIcon,
  BellRingIcon,
  FileBarChart2Icon,
  ShieldCheckIcon,
  Users2Icon,
  WalletIcon,
} from "lucide-react";
import type { Role } from "@abase/shared-types";

import type {
  ContratoResumoCards,
  EsteiraItem,
  PaginatedResponse,
  PendenciaItem,
  RelatorioResumo,
  TesourariaContratoItem,
} from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import { formatCurrency, formatDateTime } from "@/lib/formatters";
import { getNavigationForRole } from "@/lib/navigation";
import { usePermissions } from "@/hooks/use-permissions";
import DataTable, { type DataTableColumn } from "@/components/shared/data-table";
import EmptyState from "@/components/shared/empty-state";
import StatsCard from "@/components/shared/stats-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";

function flattenQuickLinks(role?: Role) {
  return getNavigationForRole(role)
    .flatMap((section) =>
      section.items.flatMap((item) =>
        item.children?.length
          ? item.children.map((child) => ({
              title: child.title,
              href: child.href ?? "#",
              icon: child.icon,
              section: section.title,
            }))
          : item.href
            ? [
                {
                  title: item.title,
                  href: item.href,
                  icon: item.icon,
                  section: section.title,
                },
              ]
            : [],
      ),
    )
    .filter((item) => item.href !== "/dashboard")
    .slice(0, 6);
}

export default function DashboardPage() {
  const { role, roles, user, status, hasAnyRole, hasRole } = usePermissions();
  const quickLinks = React.useMemo(() => flattenQuickLinks(role), [role]);
  const roleLabel = React.useMemo(
    () => roles.join(" · ") || user?.primary_role || "SEM PAPEL",
    [roles, user?.primary_role],
  );
  const competenciaAtual = React.useMemo(() => {
    const now = new Date();
    const month = String(now.getMonth() + 1).padStart(2, "0");
    return `${now.getFullYear()}-${month}`;
  }, []);

  const relatoriosResumoQuery = useQuery({
    queryKey: ["dashboard-relatorios-resumo"],
    queryFn: () => apiFetch<RelatorioResumo>("relatorios/resumo"),
    enabled: hasRole("ADMIN"),
  });

  const contratosResumoQuery = useQuery({
    queryKey: ["dashboard-contratos-resumo"],
    queryFn: () => apiFetch<ContratoResumoCards>("contratos/resumo"),
    enabled: hasAnyRole(["AGENTE", "ADMIN"]),
  });

  const pendenciasAgenteQuery = useQuery({
    queryKey: ["dashboard-pendencias-agente"],
    queryFn: () =>
      apiFetch<PaginatedResponse<PendenciaItem>>("esteira/pendencias", {
        query: { page_size: 5 },
      }),
    enabled: hasAnyRole(["AGENTE", "ADMIN"]),
  });

  const esteiraQuery = useQuery({
    queryKey: ["dashboard-esteira"],
    queryFn: () =>
      apiFetch<PaginatedResponse<EsteiraItem>>("esteira", {
        query: { page_size: 5 },
      }),
    enabled: hasAnyRole(["ANALISTA", "COORDENADOR", "ADMIN"]),
  });

  const tesourariaQuery = useQuery({
    queryKey: ["dashboard-tesouraria", competenciaAtual],
    queryFn: () =>
      apiFetch<PaginatedResponse<TesourariaContratoItem>>("tesouraria/contratos", {
        query: {
          competencia: competenciaAtual,
          pagamento: "pendente",
          page_size: 5,
        },
      }),
    enabled: hasAnyRole(["TESOUREIRO", "ADMIN"]),
  });

  const esteiraColumns = React.useMemo<DataTableColumn<EsteiraItem>[]>(
    () => [
      {
        id: "contrato",
        header: "Contrato",
        cell: (row) => (
          <div>
            <p className="font-medium text-foreground">{row.contrato?.codigo ?? "-"}</p>
            <p className="text-xs text-muted-foreground">{row.contrato?.associado_nome ?? "-"}</p>
          </div>
        ),
      },
      {
        id: "agente",
        header: "Agente",
        cell: (row) => row.agente?.full_name ?? "-",
      },
      {
        id: "status",
        header: "Status",
        cell: (row) => (
          <Badge variant="outline">
            {row.etapa_atual} / {row.status}
          </Badge>
        ),
      },
    ],
    [],
  );

  const tesourariaColumns = React.useMemo<DataTableColumn<TesourariaContratoItem>[]>(
    () => [
      {
        id: "associado",
        header: "Associado",
        cell: (row) => (
          <div>
            <p className="font-medium text-foreground">{row.nome}</p>
            <p className="text-xs text-muted-foreground">{row.codigo}</p>
          </div>
        ),
      },
      {
        id: "agente",
        header: "Agente",
        cell: (row) => row.agente_nome,
      },
      {
        id: "margem",
        header: "Margem",
        cell: (row) => formatCurrency(row.margem_disponivel),
      },
    ],
    [],
  );

  const pendenciaColumns = React.useMemo<DataTableColumn<PendenciaItem>[]>(
    () => [
      {
        id: "associado",
        header: "Associado",
        cell: (row) => (
          <div>
            <p className="font-medium text-foreground">{row.associado_nome}</p>
            <p className="text-xs text-muted-foreground">{row.contrato_codigo ?? row.matricula}</p>
          </div>
        ),
      },
      {
        id: "tipo",
        header: "Tipo",
        cell: (row) => row.tipo || "pendencia",
      },
      {
        id: "created_at",
        header: "Aberta em",
        cell: (row) => formatDateTime(row.created_at),
      },
    ],
    [],
  );

  if (status !== "authenticated") {
    return (
      <div className="flex min-h-[40vh] items-center justify-center gap-3 rounded-[1.75rem] border border-border/60 bg-card/60 px-6 py-8 text-sm text-muted-foreground">
        <Spinner />
        Carregando painel operacional...
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <section className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div className="space-y-2">
          <p className="text-sm uppercase tracking-[0.2em] text-muted-foreground">{roleLabel}</p>
          <h1 className="text-3xl font-semibold text-foreground">Painel operacional</h1>
          <p className="max-w-3xl text-sm text-muted-foreground">
            Entrada unica por role, sem mock e sem fallback fantasma. O dashboard agora mostra o
            que realmente esta em fila para {user?.full_name}.
          </p>
        </div>
        <div className="rounded-[1.5rem] border border-border/60 bg-card/60 px-4 py-3 text-sm text-muted-foreground">
          {quickLinks.length} atalhos operacionais disponiveis
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {quickLinks.map((item) => (
          <Card key={item.href} className="rounded-[1.75rem] border-border/60 bg-card/70 shadow-xl shadow-black/20">
            <CardHeader>
              <div className="flex items-center justify-between gap-3">
                <div className="flex size-11 items-center justify-center rounded-2xl bg-primary/12 text-primary">
                  <item.icon className="size-5" />
                </div>
                <Badge variant="outline">{item.section}</Badge>
              </div>
              <CardTitle>{item.title}</CardTitle>
              <CardDescription>{item.href}</CardDescription>
            </CardHeader>
            <CardContent>
              <Button asChild variant="outline">
                <Link href={item.href}>
                  Abrir modulo
                  <ArrowRightIcon className="size-4" />
                </Link>
              </Button>
            </CardContent>
          </Card>
        ))}
      </section>

      {hasRole("ADMIN") && relatoriosResumoQuery.data ? (
        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <StatsCard
            title="Associados ativos"
            value={String(relatoriosResumoQuery.data.associados_ativos)}
            delta={`${relatoriosResumoQuery.data.associados_em_analise} em analise`}
            tone="positive"
            icon={Users2Icon}
          />
          <StatsCard
            title="Pendencias abertas"
            value={String(relatoriosResumoQuery.data.pendencias_abertas)}
            delta={`${relatoriosResumoQuery.data.esteira_aguardando} aguardando esteira`}
            tone="warning"
            icon={ShieldCheckIcon}
          />
          <StatsCard
            title="Refinanciamentos"
            value={String(relatoriosResumoQuery.data.refinanciamentos_efetivados)}
            delta={`${relatoriosResumoQuery.data.refinanciamentos_pendentes} pendentes`}
            tone="neutral"
            icon={BellRingIcon}
          />
          <StatsCard
            title="Baixas do mes"
            value={formatCurrency(relatoriosResumoQuery.data.valor_baixado_mes)}
            delta={`${relatoriosResumoQuery.data.importacoes_concluidas} importacoes concluidas`}
            tone="positive"
            icon={FileBarChart2Icon}
          />
        </section>
      ) : null}

      {hasAnyRole(["AGENTE", "ADMIN"]) && contratosResumoQuery.data ? (
        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <StatsCard
            title="Contratos cadastrados"
            value={String(contratosResumoQuery.data.total)}
            delta="Base operacional do agente"
            tone="neutral"
            icon={Users2Icon}
          />
          <StatsCard
            title="Concluidos"
            value={String(contratosResumoQuery.data.concluidos)}
            delta="Contratos aptos para acompanhamento"
            tone="positive"
            icon={WalletIcon}
          />
          <StatsCard
            title="Pendentes"
            value={String(contratosResumoQuery.data.pendentes)}
            delta="Ainda em esteira ou tesouraria"
            tone="warning"
            icon={BellRingIcon}
          />
          <StatsCard
            title="Pendencias abertas"
            value={String(pendenciasAgenteQuery.data?.count ?? 0)}
            delta="Demandas devolvidas ao agente"
            tone="warning"
            icon={ShieldCheckIcon}
          />
        </section>
      ) : null}

      <section className="grid gap-6 xl:grid-cols-2">
        {hasAnyRole(["AGENTE", "ADMIN"]) ? (
          <Card className="rounded-[1.75rem] border-border/60 bg-card/70 shadow-xl shadow-black/20">
            <CardHeader>
              <CardTitle>Pendencias do agente</CardTitle>
              <CardDescription>Itens devolvidos para ajuste e acompanhamento imediato.</CardDescription>
            </CardHeader>
            <CardContent>
              {pendenciasAgenteQuery.isLoading ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Spinner />
                  Carregando pendencias...
                </div>
              ) : (
                <DataTable
                  columns={pendenciaColumns}
                  data={pendenciasAgenteQuery.data?.results ?? []}
                  emptyMessage="Nenhuma pendencia aberta para o agente."
                />
              )}
            </CardContent>
          </Card>
        ) : null}

        {hasAnyRole(["ANALISTA", "COORDENADOR", "ADMIN"]) ? (
          <Card className="rounded-[1.75rem] border-border/60 bg-card/70 shadow-xl shadow-black/20">
            <CardHeader>
              <CardTitle>Fila da esteira</CardTitle>
              <CardDescription>
                {esteiraQuery.data?.count ?? 0} itens disponiveis para analise ou coordenacao.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {esteiraQuery.isLoading ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Spinner />
                  Carregando fila da esteira...
                </div>
              ) : (
                <DataTable
                  columns={esteiraColumns}
                  data={esteiraQuery.data?.results ?? []}
                  emptyMessage="Nenhum item aguardando tratamento na esteira."
                />
              )}
            </CardContent>
          </Card>
        ) : null}

        {hasAnyRole(["TESOUREIRO", "ADMIN"]) ? (
          <Card className="rounded-[1.75rem] border-border/60 bg-card/70 shadow-xl shadow-black/20">
            <CardHeader>
              <CardTitle>Tesouraria pendente</CardTitle>
              <CardDescription>
                {tesourariaQuery.data?.count ?? 0} contratos aguardando efetivacao na competencia atual.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {tesourariaQuery.isLoading ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Spinner />
                  Carregando contratos da tesouraria...
                </div>
              ) : (
                <DataTable
                  columns={tesourariaColumns}
                  data={tesourariaQuery.data?.results ?? []}
                  emptyMessage="Nenhum contrato pendente na tesouraria."
                />
              )}
            </CardContent>
          </Card>
        ) : null}
      </section>

      {!quickLinks.length ? (
        <EmptyState
          title="Nenhum modulo disponivel"
          description="A sessao autenticada nao possui atalhos de navegacao habilitados."
        />
      ) : null}
    </div>
  );
}
