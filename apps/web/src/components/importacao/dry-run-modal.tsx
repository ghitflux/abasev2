"use client";

import * as React from "react";
import {
  AlertTriangleIcon,
  ArrowRightIcon,
  CheckCircle2Icon,
  ChevronRightIcon,
  CircleXIcon,
  HelpCircleIcon,
  RefreshCwIcon,
  SearchXIcon,
  TrendingUpIcon,
  UsersIcon,
} from "lucide-react";

import type { DryRunItem } from "@/gen/models/DryRunItem";
import type { DryRunMudancaStatus } from "@/gen/models/DryRunMudancaStatus";
import type { DryRunResultado } from "@/gen/models/DryRunResultado";
import StatusBadge from "@/components/custom/status-badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import { formatCurrency } from "@/lib/formatters";
import DryRunDetailDialog from "./dry-run-detail-dialog";

// ---------------------------------------------------------------------------
// Tipos internos
// ---------------------------------------------------------------------------

type DetailKey =
  | "descontados"
  | "nao_descontados"
  | "nao_encontrados"
  | "pendencias"
  | "ciclo_aberto"
  | "aptos_renovar"
  | "v3050_descontaram"
  | "v3050_nao_descontaram"
  | { mudanca: "assoc"; antes: string; depois: string }
  | { mudanca: "ciclo"; antes: string; depois: string };

type DryRunModalProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  arquivoNome: string;
  competenciaDisplay: string;
  dryRunData: DryRunResultado;
  onConfirm: () => void;
  onCancel: () => void;
  isConfirming: boolean;
  isCanceling: boolean;
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function filterItems(items: DryRunItem[], key: DetailKey): DryRunItem[] {
  if (typeof key === "string") {
    if (key === "descontados") return items.filter((i) => i.resultado === "baixa_efetuada");
    if (key === "nao_descontados") return items.filter((i) => i.resultado === "nao_descontado");
    if (key === "nao_encontrados") return items.filter((i) => i.resultado === "nao_encontrado");
    if (key === "pendencias") return items.filter((i) => i.resultado === "pendencia_manual");
    if (key === "ciclo_aberto") return items.filter((i) => i.resultado === "ciclo_aberto");
    if (key === "aptos_renovar") return items.filter((i) => i.ficara_apto_renovar);
    if (key === "v3050_descontaram")
      return items.filter((i) => i.categoria === "valores_30_50" && i.resultado === "baixa_efetuada");
    if (key === "v3050_nao_descontaram")
      return items.filter((i) => i.categoria === "valores_30_50" && i.resultado === "nao_descontado");
  }
  if (typeof key === "object") {
    if (key.mudanca === "assoc")
      return items.filter(
        (i) => i.associado_status_antes === key.antes && i.associado_status_depois === key.depois
      );
    if (key.mudanca === "ciclo")
      return items.filter(
        (i) => i.ciclo_status_antes === key.antes && i.ciclo_status_depois === key.depois
      );
  }
  return [];
}

function detailTitle(key: DetailKey): string {
  if (typeof key === "string") {
    const map: Record<string, string> = {
      descontados: "Descontados (baixa efetuada)",
      nao_descontados: "Não descontados",
      nao_encontrados: "CPFs não encontrados no cadastro",
      pendencias: "Pendências manuais",
      ciclo_aberto: "Sem parcela elegível (ciclo aberto)",
      aptos_renovar: "Ficarão aptos a renovar",
      v3050_descontaram: "Parcelas R$30/R$50 — descontadas",
      v3050_nao_descontaram: "Parcelas R$30/R$50 — não descontadas",
    };
    return map[key] ?? key;
  }
  if (key.mudanca === "assoc") return `Associados: ${key.antes} → ${key.depois}`;
  if (key.mudanca === "ciclo") return `Ciclos: ${key.antes} → ${key.depois}`;
  return "";
}

// ---------------------------------------------------------------------------
// KPI Card
// ---------------------------------------------------------------------------

type KpiCardProps = {
  label: string;
  value: React.ReactNode;
  sub?: React.ReactNode;
  icon: React.ReactNode;
  colorClass?: string;
  onClick?: () => void;
  clickable?: boolean;
};

function KpiCard({ label, value, sub, icon, colorClass = "text-muted-foreground", onClick, clickable }: KpiCardProps) {
  const Tag = clickable ? "button" : "div";
  return (
    <Tag
      onClick={onClick}
      className={[
        "flex min-h-[11.5rem] flex-col gap-3 rounded-3xl border border-border/60 bg-card/70 p-4 text-left shadow-lg shadow-black/10",
        clickable
          ? "cursor-pointer transition-colors hover:border-primary/40 hover:bg-primary/[0.08]"
          : "",
      ].join(" ")}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="max-w-[14rem] text-[11px] uppercase tracking-[0.24em] text-muted-foreground">
          {label}
        </span>
        <span className={colorClass}>{icon}</span>
      </div>
      <div className="space-y-2">
        <p className={cn("text-2xl font-semibold leading-tight sm:text-[2rem]", colorClass)}>
          {value}
        </p>
        {sub && <p className="max-w-[18rem] text-xs leading-relaxed text-muted-foreground">{sub}</p>}
      </div>
      {clickable && (
        <span className="mt-auto inline-flex items-center gap-1 text-[11px] font-medium text-primary/80">
          Ver detalhes <ChevronRightIcon className="size-3" />
        </span>
      )}
    </Tag>
  );
}

// ---------------------------------------------------------------------------
// Linha de mudança de status (clicável)
// ---------------------------------------------------------------------------

type MudancaRowProps = {
  mudanca: DryRunMudancaStatus;
  onClick: () => void;
};

function MudancaRow({ mudanca, onClick }: MudancaRowProps) {
  return (
    <button
      onClick={onClick}
      className="flex w-full items-center justify-between gap-3 rounded-2xl border border-border/40 bg-card/70 px-4 py-3 text-left text-sm transition-colors hover:border-primary/30 hover:bg-primary/[0.08]"
    >
      <span className="flex items-center gap-2">
        <span className="text-xl font-semibold tabular-nums">{mudanca.count}</span>
        <span className="flex items-center gap-1.5">
          <StatusBadge status={mudanca.antes} />
          <ArrowRightIcon className="size-3 shrink-0 text-muted-foreground" />
          <StatusBadge status={mudanca.depois} />
        </span>
      </span>
      <ChevronRightIcon className="size-4 shrink-0 text-muted-foreground" />
    </button>
  );
}

// ---------------------------------------------------------------------------
// Modal principal
// ---------------------------------------------------------------------------

export default function DryRunModal({
  open,
  onOpenChange,
  arquivoNome,
  competenciaDisplay,
  dryRunData,
  onConfirm,
  onCancel,
  isConfirming,
  isCanceling,
}: DryRunModalProps) {
  const [activeDetail, setActiveDetail] = React.useState<DetailKey | null>(null);

  const { kpis, items } = dryRunData;
  const isBusy = isConfirming || isCanceling;

  const detailItems = activeDetail ? filterItems(items, activeDetail) : [];
  const detailTitleStr = activeDetail ? detailTitle(activeDetail) : "";

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent
          className="grid max-h-[calc(100vh-2rem)] w-[96vw] max-w-[96vw] grid-rows-[auto_minmax(0,1fr)_auto] overflow-hidden border-border/60 bg-background/95 p-0 sm:max-w-none 2xl:max-w-[110rem]"
          onEscapeKeyDown={(event) => {
            if (isBusy) event.preventDefault();
          }}
          onInteractOutside={(event) => {
            if (isBusy) event.preventDefault();
          }}
        >
          <DialogHeader className="shrink-0 border-b border-border/60 px-6 py-5">
            <DialogTitle className="flex items-center gap-2 text-lg">
              <RefreshCwIcon className="size-5 text-primary" />
              Prévia da importação
            </DialogTitle>
            <DialogDescription className="max-w-4xl text-sm leading-relaxed">
              <span className="font-medium text-foreground">{arquivoNome}</span>
              {" · "}Competência{" "}
              <span className="font-medium text-foreground">{competenciaDisplay}</span>
              {" · "}Revise o impacto operacional e financeiro antes de confirmar a importação.
            </DialogDescription>
          </DialogHeader>

          <div className="min-h-0 overflow-y-auto px-6 py-5">
            <div className="space-y-6 pb-2">

              {/* KPI grid principal */}
              <div>
                <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Resumo do arquivo
                </h3>
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
                  <KpiCard
                    label="Total no arquivo"
                    value={kpis.total_no_arquivo}
                    icon={<UsersIcon className="size-4" />}
                  />
                  <KpiCard
                    label="Descontados"
                    value={kpis.baixa_efetuada}
                    icon={<CheckCircle2Icon className="size-4" />}
                    colorClass="text-emerald-300"
                    clickable={kpis.baixa_efetuada > 0}
                    onClick={() => setActiveDetail("descontados")}
                  />
                  <KpiCard
                    label="Não descontados"
                    value={kpis.nao_descontado}
                    icon={<CircleXIcon className="size-4" />}
                    colorClass={kpis.nao_descontado > 0 ? "text-rose-300" : "text-muted-foreground"}
                    clickable={kpis.nao_descontado > 0}
                    onClick={() => setActiveDetail("nao_descontados")}
                  />
                  <KpiCard
                    label="CPFs não encontrados"
                    value={kpis.associados_importados}
                    icon={<SearchXIcon className="size-4" />}
                    sub="CPFs no arquivo sem correspondência no cadastro de associados."
                    colorClass={
                      kpis.associados_importados > 0 ? "text-amber-300" : "text-muted-foreground"
                    }
                    clickable={kpis.associados_importados > 0}
                    onClick={() => setActiveDetail("nao_encontrados")}
                  />
                </div>
              </div>

              {/* KPI financeiro */}
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
                <KpiCard
                  label="Valor previsto"
                  value={formatCurrency(kpis.valor_previsto)}
                  sub="Soma de todos os valores do arquivo"
                  icon={<TrendingUpIcon className="size-4" />}
                />
                <KpiCard
                  label="Valor real recebido"
                  value={formatCurrency(kpis.valor_real)}
                  sub="Soma dos itens efetivados"
                  icon={<TrendingUpIcon className="size-4" />}
                  colorClass="text-emerald-300"
                />
                {kpis.pendencia_manual > 0 && (
                  <KpiCard
                    label="Pendências manuais"
                    value={kpis.pendencia_manual}
                    icon={<HelpCircleIcon className="size-4" />}
                    colorClass="text-amber-300"
                    clickable
                    onClick={() => setActiveDetail("pendencias")}
                  />
                )}
              </div>

              {/* KPI 30/50 */}
              {(kpis.valores_30_50.descontaram.count > 0 ||
                kpis.valores_30_50.nao_descontaram.count > 0) && (
                <div>
                  <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Parcelas R$30 / R$50
                  </h3>
                  <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                    <KpiCard
                      label="Descontaram"
                      value={kpis.valores_30_50.descontaram.count}
                      sub={formatCurrency(kpis.valores_30_50.descontaram.valor_total)}
                      icon={<CheckCircle2Icon className="size-4" />}
                      colorClass="text-emerald-300"
                      clickable={kpis.valores_30_50.descontaram.count > 0}
                      onClick={() => setActiveDetail("v3050_descontaram")}
                    />
                    <KpiCard
                      label="Não descontaram"
                      value={kpis.valores_30_50.nao_descontaram.count}
                      sub={formatCurrency(kpis.valores_30_50.nao_descontaram.valor_total)}
                      icon={<CircleXIcon className="size-4" />}
                      colorClass={
                        kpis.valores_30_50.nao_descontaram.count > 0
                          ? "text-rose-300"
                          : "text-muted-foreground"
                      }
                      clickable={kpis.valores_30_50.nao_descontaram.count > 0}
                      onClick={() => setActiveDetail("v3050_nao_descontaram")}
                    />
                  </div>
                </div>
              )}

              <Separator className="bg-border/60" />

              {/* Impacto pós-confirmação */}
              <div>
                <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Impacto após confirmação
                </h3>
                <div className="space-y-3">
                  <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
                    <KpiCard
                      label="Ficarão aptos a renovar"
                      value={kpis.aptos_a_renovar}
                      sub="Associados que entrarão em Aptos a renovar após confirmar este retorno."
                      icon={<CheckCircle2Icon className="size-4" />}
                      colorClass={
                        kpis.aptos_a_renovar > 0
                          ? "text-emerald-300"
                          : "text-muted-foreground"
                      }
                      clickable={kpis.aptos_a_renovar > 0}
                      onClick={() => setActiveDetail("aptos_renovar")}
                    />
                  </div>

                  {/* Mudanças de status de associados */}
                  {kpis.mudancas_status_associado.length > 0 && (
                    <div>
                      <p className="mb-2 text-xs text-muted-foreground">Status de associados:</p>
                      <div className="space-y-1.5">
                        {kpis.mudancas_status_associado.map((m, i) => (
                          <MudancaRow
                            key={i}
                            mudanca={m}
                            onClick={() =>
                              setActiveDetail({ mudanca: "assoc", antes: m.antes, depois: m.depois })
                            }
                          />
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Mudanças de status de ciclos */}
                  {kpis.mudancas_status_ciclo.length > 0 && (
                    <div>
                      <p className="mb-2 text-xs text-muted-foreground">Status de ciclos:</p>
                      <div className="space-y-1.5">
                        {kpis.mudancas_status_ciclo.map((m, i) => (
                          <MudancaRow
                            key={i}
                            mudanca={m}
                            onClick={() =>
                              setActiveDetail({ mudanca: "ciclo", antes: m.antes, depois: m.depois })
                            }
                          />
                        ))}
                      </div>
                    </div>
                  )}

                  {kpis.aptos_a_renovar === 0 &&
                    kpis.mudancas_status_associado.length === 0 &&
                    kpis.mudancas_status_ciclo.length === 0 && (
                      <p className="text-sm text-muted-foreground">
                        Nenhuma mudança de status será realizada por esta importação.
                      </p>
                    )}
                </div>
              </div>

              {/* Aviso se houver itens sem correspondência */}
              {kpis.associados_importados > 0 && (
                <div className="flex items-start gap-2 rounded-2xl border border-amber-400/25 bg-amber-400/5 px-4 py-3 text-sm text-amber-200">
                  <AlertTriangleIcon className="mt-0.5 size-4 shrink-0" />
                  <span>
                    <strong>{kpis.associados_importados}</strong> CPF
                    {kpis.associados_importados !== 1 ? "s" : ""} do arquivo não têm correspondência
                    no cadastro e serão ignorados na importação.
                  </span>
                </div>
              )}
            </div>
          </div>

          <DialogFooter className="shrink-0 border-t border-border/60 px-6 py-4">
            <Button
              variant="outline"
              onClick={onCancel}
              disabled={isCanceling || isConfirming}
            >
              {isCanceling ? "Cancelando..." : "Cancelar"}
            </Button>
            <Button
              variant="success"
              onClick={onConfirm}
              disabled={isConfirming || isCanceling}
            >
              {isConfirming ? "Confirmando..." : "Confirmar importação"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Sub-dialog de detalhe */}
      <DryRunDetailDialog
        open={activeDetail !== null}
        onOpenChange={(v) => { if (!v) setActiveDetail(null); }}
        title={detailTitleStr}
        items={detailItems}
      />
    </>
  );
}
