"use client";

import * as React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PercentIcon, Settings2Icon, UsersIcon } from "lucide-react";
import { toast } from "sonner";

import type { ComissaoConfiguracaoPayload } from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import MultiSelect from "@/components/custom/multi-select";
import DataTable, { type DataTableColumn } from "@/components/shared/data-table";
import StatsCard from "@/components/shared/stats-card";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

function formatPercentual(value?: string | null) {
  return `${Number.parseFloat(value || "0").toFixed(2)}%`;
}

export default function ConfiguracoesComissoesPage() {
  const queryClient = useQueryClient();
  const [globalPercentual, setGlobalPercentual] = React.useState("");
  const [globalMotivo, setGlobalMotivo] = React.useState("");
  const [selectedAgentes, setSelectedAgentes] = React.useState<string[]>([]);
  const [overridePercentual, setOverridePercentual] = React.useState("");
  const [overrideMotivo, setOverrideMotivo] = React.useState("");
  const [resetMotivos, setResetMotivos] = React.useState<Record<number, string>>({});
  const [search, setSearch] = React.useState("");

  const query = useQuery({
    queryKey: ["configuracoes-comissoes"],
    queryFn: () => apiFetch<ComissaoConfiguracaoPayload>("configuracoes/comissoes"),
  });

  React.useEffect(() => {
    if (!query.data) return;
    setGlobalPercentual(query.data.global_config.percentual);
  }, [query.data]);

  const invalidate = React.useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ["configuracoes-comissoes"] });
  }, [queryClient]);

  const globalMutation = useMutation({
    mutationFn: () =>
      apiFetch<ComissaoConfiguracaoPayload>("configuracoes/comissoes/global", {
        method: "POST",
        body: {
          percentual: globalPercentual,
          motivo: globalMotivo,
        },
      }),
    onSuccess: () => {
      toast.success("Comissão global atualizada.");
      setGlobalMotivo("");
      invalidate();
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Falha ao atualizar comissão global.");
    },
  });

  const agentesMutation = useMutation({
    mutationFn: () =>
      apiFetch<ComissaoConfiguracaoPayload>("configuracoes/comissoes/agentes", {
        method: "POST",
        body: {
          agentes: selectedAgentes.map((item) => Number.parseInt(item, 10)),
          percentual: overridePercentual,
          motivo: overrideMotivo,
        },
      }),
    onSuccess: () => {
      toast.success("Override aplicado aos agentes selecionados.");
      setSelectedAgentes([]);
      setOverridePercentual("");
      setOverrideMotivo("");
      invalidate();
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Falha ao aplicar override.");
    },
  });

  const resetMutation = useMutation({
    mutationFn: ({ agenteId, motivo }: { agenteId: number; motivo: string }) =>
      apiFetch<ComissaoConfiguracaoPayload>(
        `configuracoes/comissoes/${agenteId}/remover-override`,
        {
          method: "POST",
          body: { motivo },
        },
      ),
    onSuccess: () => {
      toast.success("Override removido.");
      invalidate();
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Falha ao remover override.");
    },
  });

  const agentes = query.data?.agentes ?? [];
  const tableRows = React.useMemo(
    () => agentes.map((item) => ({ ...item, id: item.agente_id })),
    [agentes],
  );
  const filteredAgentes = agentes.filter((item) => {
    if (!search.trim()) return true;
    const normalized = search.toLowerCase();
    return (
      item.agente_nome.toLowerCase().includes(normalized) ||
      item.agente_email.toLowerCase().includes(normalized)
    );
  });

  const columns = React.useMemo<DataTableColumn<(typeof tableRows)[number]>[]>(
    () => [
      {
        id: "agente",
        header: "Agente",
        cell: (row) => (
          <div>
            <p className="font-medium">{row.agente_nome}</p>
            <p className="text-xs text-muted-foreground">{row.agente_email}</p>
          </div>
        ),
      },
      {
        id: "efetivo",
        header: "Comissão efetiva",
        cell: (row) => formatPercentual(row.percentual_efetivo),
      },
      {
        id: "override",
        header: "Override",
        cell: (row) => row.percentual_override ? formatPercentual(row.percentual_override) : "Global",
      },
      {
        id: "acoes",
        header: "Ações",
        cellClassName: "w-[320px]",
        cell: (row) =>
          row.possui_override ? (
            <div className="flex flex-col gap-2">
              <Input
                value={resetMotivos[row.agente_id] ?? ""}
                onChange={(event) =>
                  setResetMotivos((current) => ({
                    ...current,
                    [row.agente_id]: event.target.value,
                  }))
                }
                placeholder="Motivo para remover override"
                className="h-10 rounded-xl border-border/60 bg-card/60"
              />
              <Button
                variant="outline"
                disabled={resetMutation.isPending}
                onClick={() =>
                  resetMutation.mutate({
                    agenteId: row.agente_id,
                    motivo: resetMotivos[row.agente_id] ?? "",
                  })
                }
              >
                Remover override
              </Button>
            </div>
          ) : (
            <span className="text-sm text-muted-foreground">Sem override ativo.</span>
          ),
      },
    ],
    [resetMotivos, resetMutation, tableRows],
  );

  return (
    <div className="space-y-6">
      <section className="rounded-[1.75rem] border border-border/60 bg-card/70 p-6">
        <div className="space-y-1">
          <h1 className="text-3xl font-semibold">Comissões</h1>
          <p className="text-sm text-muted-foreground">
            Ajuste o percentual global da operação e aplique overrides individuais por agente.
          </p>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        <StatsCard
          title="Comissão global"
          value={formatPercentual(query.data?.global_config.percentual)}
          delta="Percentual padrão vigente"
          icon={PercentIcon}
          tone="neutral"
        />
        <StatsCard
          title="Agentes ativos"
          value={String(agentes.length)}
          delta="Elegíveis a regra global ou override"
          icon={UsersIcon}
          tone="neutral"
        />
        <StatsCard
          title="Overrides ativos"
          value={String(agentes.filter((item) => item.possui_override).length)}
          delta="Sobrescrevendo o percentual global"
          icon={Settings2Icon}
          tone="warning"
        />
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <Card className="rounded-[1.75rem] border-border/60 bg-card/70">
          <CardHeader>
            <CardTitle>Regra global</CardTitle>
            <CardDescription>
              Aplica prospectivamente a novos cadastros, contratos e renovações sem override individual.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="percentual-global">Percentual global</Label>
              <Input
                id="percentual-global"
                value={globalPercentual}
                onChange={(event) => setGlobalPercentual(event.target.value)}
                className="h-11 rounded-xl border-border/60 bg-card/60"
                placeholder="10.00"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="motivo-global">Motivo</Label>
              <Textarea
                id="motivo-global"
                value={globalMotivo}
                onChange={(event) => setGlobalMotivo(event.target.value)}
                className="min-h-24 rounded-2xl border-border/60 bg-card/60"
                placeholder="Motivo da alteração global"
              />
            </div>
            <Button
              onClick={() => globalMutation.mutate()}
              disabled={!globalPercentual.trim() || globalMutation.isPending}
            >
              Aplicar regra global
            </Button>
          </CardContent>
        </Card>

        <Card className="rounded-[1.75rem] border-border/60 bg-card/70">
          <CardHeader>
            <CardTitle>Override por agente</CardTitle>
            <CardDescription>
              O override individual prevalece sobre a regra global enquanto estiver ativo.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Agentes</Label>
              <MultiSelect
                options={agentes.map((item) => ({
                  value: String(item.agente_id),
                  label: item.agente_nome,
                }))}
                value={selectedAgentes}
                onChange={setSelectedAgentes}
                placeholder="Selecione um ou mais agentes"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="percentual-override">Percentual override</Label>
              <Input
                id="percentual-override"
                value={overridePercentual}
                onChange={(event) => setOverridePercentual(event.target.value)}
                className="h-11 rounded-xl border-border/60 bg-card/60"
                placeholder="12.50"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="motivo-override">Motivo</Label>
              <Textarea
                id="motivo-override"
                value={overrideMotivo}
                onChange={(event) => setOverrideMotivo(event.target.value)}
                className="min-h-24 rounded-2xl border-border/60 bg-card/60"
                placeholder="Motivo do override"
              />
            </div>
            <Button
              onClick={() => agentesMutation.mutate()}
              disabled={
                !selectedAgentes.length || !overridePercentual.trim() || agentesMutation.isPending
              }
            >
              Aplicar override
            </Button>
          </CardContent>
        </Card>
      </section>

      <Card className="rounded-[1.75rem] border-border/60 bg-card/70">
        <CardHeader>
          <CardTitle>Agentes e comissão efetiva</CardTitle>
          <CardDescription>
            Consulte o percentual efetivo, busque agentes e remova overrides quando necessário.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Buscar por nome ou e-mail"
            className="h-11 rounded-xl border-border/60 bg-card/60"
          />
          <DataTable
            data={filteredAgentes.map((item) => ({ ...item, id: item.agente_id }))}
            columns={columns}
            emptyMessage="Nenhum agente encontrado para o filtro informado."
            loading={query.isLoading}
          />
        </CardContent>
      </Card>
    </div>
  );
}
