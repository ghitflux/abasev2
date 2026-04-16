"use client";

import * as React from "react";

import type { PagamentoAgenteItem, PagamentoAgenteResumo } from "@/lib/api/types";
import { buildBackendFileUrl } from "@/lib/backend-files";
import { formatCurrency, formatDate, formatDateTime, formatMonthYear } from "@/lib/formatters";
import { maskCPFCNPJ } from "@/lib/masks";
import StatusBadge from "@/components/custom/status-badge";
import DataTable, { type DataTableColumn } from "@/components/shared/data-table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export const EMPTY_RESUMO: PagamentoAgenteResumo = {
  total: 0,
  efetivados: 0,
  com_anexos: 0,
  parcelas_pagas: 0,
  parcelas_total: 0,
};

export const STATUS_OPTIONS = [
  { value: "todos", label: "Todos status" },
  { value: "ativo", label: "Ativo" },
  { value: "em_analise", label: "Em análise" },
  { value: "encerrado", label: "Encerrado" },
  { value: "cancelado", label: "Cancelado" },
];

export const ASSOCIADO_STATUS_OPTIONS = [
  { value: "todos", label: "Todos associados" },
  { value: "ativo", label: "Associado ativo" },
  { value: "em_analise", label: "Em análise" },
  { value: "inativo", label: "Inativo" },
];

export const PAGAMENTO_INICIAL_OPTIONS = [
  { value: "todos", label: "Todos pagamentos iniciais" },
  { value: "pago", label: "Pago" },
  { value: "pendente", label: "Pendente" },
  { value: "cancelado", label: "Cancelado" },
  { value: "sem_pagamento_inicial", label: "Sem pagamento inicial" },
];

export const PRESET_OPTIONS = [
  { value: "todos", label: "Todas as filas" },
  { value: "novos_contratos", label: "Novos contratos" },
  { value: "cancelados", label: "Cancelados" },
  { value: "congelados", label: "Congelados" },
  { value: "pendentes", label: "Pendentes" },
];

export const NUMERO_CICLOS_OPTIONS = [
  { value: "todos", label: "Todos ciclos" },
  { value: "1", label: "1 ciclo" },
  { value: "2", label: "2 ciclos" },
  { value: "3", label: "3 ciclos" },
  { value: "4", label: "4 ciclos" },
  { value: "5", label: "5 ciclos" },
];

export function resolveCount(value?: number | null) {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

export function buildPagamentoColumns(options?: {
  onExcluir?: (row: PagamentoAgenteItem) => void;
  canRemoverFila?: boolean;
}): DataTableColumn<PagamentoAgenteItem>[] {
  const { onExcluir, canRemoverFila } = options ?? {};
  return [
    {
      id: "associado",
      header: "Associado",
      cell: (row) => (
        <div className="space-y-1">
          <p className="font-medium">{row.nome}</p>
          <p className="font-mono text-xs text-muted-foreground">{maskCPFCNPJ(row.cpf_cnpj)}</p>
          <p className="text-xs text-muted-foreground">Clique na linha para ver anexos e ciclos.</p>
        </div>
      ),
    },
    {
      id: "contrato",
      header: "Contrato",
      cell: (row) => (
        <div className="space-y-1">
          <p className="font-mono text-xs">{row.contrato_codigo}</p>
          <p className="text-xs text-muted-foreground">Assinado em {formatDate(row.data_contrato)}</p>
          <p className="text-xs text-muted-foreground">
            Solicitação em {formatDate(row.data_solicitacao)}
          </p>
        </div>
      ),
    },
    {
      id: "agente",
      header: "Agente",
      cell: (row) => <p className="text-sm text-muted-foreground">{row.agente_nome || "—"}</p>,
    },
    {
      id: "status",
      header: "Status",
      cell: (row) => (
        <div className="space-y-1">
          <StatusBadge status={row.status_visual_slug} label={row.status_visual_label} />
          {row.possui_meses_nao_descontados ? (
            <p className="text-xs text-amber-200">
              {row.meses_nao_descontados_count} mês(es) não descontado(s)
            </p>
          ) : null}
          {row.cancelamento_tipo ? (
            <Badge className="rounded-full bg-rose-500/15 text-rose-200">
              {row.cancelamento_tipo === "desistente" ? "Desistente" : "Cancelado"}
            </Badge>
          ) : null}
        </div>
      ),
    },
    {
      id: "pagamento_inicial",
      header: "Pagamento inicial",
      cell: (row) => (
        <div className="space-y-2">
          <StatusBadge
            status={row.pagamento_inicial_status}
            label={row.pagamento_inicial_status_label}
          />
          <p className="text-xs text-muted-foreground">
            {row.pagamento_inicial_paid_at
              ? formatDateTime(row.pagamento_inicial_paid_at)
              : "Aguardando tesouraria"}
          </p>
        </div>
      ),
    },
    {
      id: "valor_pago",
      header: "Valor pago",
      cell: (row) => (
        <div className="space-y-1">
          <p className="font-medium">
            {row.pagamento_inicial_valor ? formatCurrency(row.pagamento_inicial_valor) : "—"}
          </p>
          <p className="text-xs text-emerald-400">Comissão {formatCurrency(row.comissao_agente)}</p>
        </div>
      ),
    },
    {
      id: "parcelas",
      header: "Parcelas",
      cell: (row) => (
        <div className="space-y-1">
          <p className="font-medium">
            {row.parcelas_pagas}/{row.parcelas_total}
          </p>
          <p className="text-xs text-muted-foreground">Parcelas pagas no recorte</p>
        </div>
      ),
    },
    {
      id: "anexos",
      header: "Efetivação",
      cell: (row) => (
        <div className="space-y-1">
          <Badge className="rounded-full bg-sky-500/15 text-sky-200">
            {row.pagamento_inicial_evidencias.length} evidência(s)
          </Badge>
          <p className="text-xs text-muted-foreground">
            {row.auxilio_liberado_em
              ? `Liberado em ${formatDate(row.auxilio_liberado_em)}`
              : "Aguardando efetivação"}
          </p>
        </div>
      ),
    },
    ...(canRemoverFila && onExcluir
      ? [
          {
            id: "remover_fila",
            header: "Ação",
            cell: (row: PagamentoAgenteItem) => (
              <Button
                size="sm"
                variant="outline"
                className="w-fit border-red-500/40 text-red-400"
                onClick={(e) => {
                  e.stopPropagation();
                  onExcluir(row);
                }}
              >
                Remover da fila
              </Button>
            ),
          } satisfies DataTableColumn<PagamentoAgenteItem>,
        ]
      : []),
  ];
}

function ComprovanteChip({
  comprovante,
}: {
  comprovante: {
    id: string;
    nome: string;
    url: string;
    arquivo_referencia: string;
    arquivo_disponivel_localmente: boolean;
    tipo_referencia: string;
    origem: string;
    papel: string;
  };
}) {
  const label =
    resolvePapelLabel(comprovante.papel) ||
    resolveComprovanteLabel(comprovante.nome, comprovante.origem);
  const description = comprovante.arquivo_referencia || comprovante.nome;

  if (comprovante.arquivo_disponivel_localmente && comprovante.url) {
    return (
      <Button size="sm" variant="outline" asChild>
        <a href={buildBackendFileUrl(comprovante.url)} target="_blank" rel="noreferrer">
          {label}
        </a>
      </Button>
    );
  }

  return (
    <div className="rounded-2xl border border-dashed border-border/60 bg-background/40 px-3 py-2">
      <p className="text-sm font-medium">{label}</p>
      <p className="mt-1 max-w-[22rem] truncate text-xs text-muted-foreground">{description}</p>
      <p className="mt-1 text-[11px] text-amber-200">
        {resolveReferenceLabel(comprovante.tipo_referencia)}
      </p>
    </div>
  );
}

export function PagamentoExpandido({ row }: { row: PagamentoAgenteItem }) {
  return (
    <div className="space-y-5">
      <section className="grid gap-4 md:grid-cols-3">
        <InfoCard label="Contrato" value={row.contrato_codigo} />
        <InfoCard label="Mensalidade" value={formatCurrency(row.valor_mensalidade)} />
        <InfoCard
          label="Liberação"
          value={row.auxilio_liberado_em ? formatDate(row.auxilio_liberado_em) : "Pendente"}
        />
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        <InfoCard label="Pagamento inicial" value={row.pagamento_inicial_status_label} />
        <InfoCard
          label="Valor pago"
          value={
            row.pagamento_inicial_valor
              ? formatCurrency(row.pagamento_inicial_valor)
              : "Não informado"
          }
        />
        <InfoCard
          label="Recebido em"
          value={
            row.pagamento_inicial_paid_at
              ? formatDateTime(row.pagamento_inicial_paid_at)
              : "Aguardando tesouraria"
          }
        />
      </section>

      <Card className="rounded-[1.5rem] border-border/60 bg-background/50">
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Pagamento inicial da efetivação</CardTitle>
        </CardHeader>
        <CardContent>
          {row.pagamento_inicial_evidencias.length ? (
            <div className="flex flex-wrap gap-2">
              {row.pagamento_inicial_evidencias.map((comprovante) => (
                <ComprovanteChip key={comprovante.id} comprovante={comprovante} />
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              Nenhuma evidência de pagamento inicial disponível.
            </p>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4 xl:grid-cols-2">
        {row.ciclos.length ? (
          row.ciclos.map((ciclo) => (
            <Card key={ciclo.id} className="rounded-[1.5rem] border-border/60 bg-background/50">
              <CardHeader className="pb-3">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <CardTitle className="text-base">Ciclo {ciclo.numero}</CardTitle>
                  <StatusBadge
                    status={ciclo.status_visual_slug}
                    label={ciclo.status_visual_label}
                  />
                </div>
                <p className="text-sm text-muted-foreground">
                  {formatMonthYear(ciclo.data_inicio)} até {formatMonthYear(ciclo.data_fim)}
                </p>
              </CardHeader>
              <CardContent className="space-y-3">
                {ciclo.parcelas.length ? (
                  ciclo.parcelas.map((parcela) => (
                    <div
                      key={parcela.id}
                      className="rounded-2xl border border-border/60 bg-card/60 p-4"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <p className="font-medium">
                            Parcela {parcela.numero} · {formatMonthYear(parcela.referencia_mes)}
                          </p>
                          <p className="text-sm text-muted-foreground">
                            {formatCurrency(parcela.valor)} · vencimento{" "}
                            {formatDate(parcela.data_vencimento)}
                          </p>
                        </div>
                        <StatusBadge status={parcela.status} />
                      </div>

                      <div className="mt-3 flex flex-wrap gap-2">
                        {parcela.comprovantes.length ? (
                          parcela.comprovantes.map((comprovante) => (
                            <ComprovanteChip key={comprovante.id} comprovante={comprovante} />
                          ))
                        ) : (
                          <span className="text-sm text-muted-foreground">
                            Sem comprovante anexado para esta parcela.
                          </span>
                        )}
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-muted-foreground">
                    Nenhuma parcela encontrada para o filtro selecionado.
                  </p>
                )}
              </CardContent>
            </Card>
          ))
        ) : (
          <Card className="rounded-[1.5rem] border-border/60 bg-background/50">
            <CardContent className="p-6 text-sm text-muted-foreground">
              Nenhum ciclo encontrado para este contrato.
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}

function resolveComprovanteLabel(nome: string, origem: string) {
  if (origem === "arquivo_retorno") {
    return "Arquivo retorno";
  }
  if (origem === "relatorio_competencia") {
    return "Relatório mensal";
  }
  if (origem === "manual") {
    return nome || "Comprovante manual";
  }
  if (origem === "baixa_manual") {
    return "Baixa manual";
  }
  return nome || "Abrir comprovante";
}

function resolvePapelLabel(papel: string) {
  if (papel === "associado") {
    return "Comprovante associada";
  }
  if (papel === "agente") {
    return "Comprovante agente";
  }
  return "";
}

function resolveReferenceLabel(tipoReferencia: string) {
  if (tipoReferencia === "relatorio_competencia") {
    return "Relatório mensal da competência";
  }
  if (tipoReferencia === "placeholder_recebido") {
    return "Pagamento recebido e aguardando acervo";
  }
  if (tipoReferencia === "legado_sem_arquivo") {
    return "Referência de arquivo legado";
  }
  if (tipoReferencia === "sem_arquivo") {
    return "Sem arquivo individual";
  }
  return "Referência de arquivo";
}

function InfoCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border/60 bg-background/50 p-4">
      <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">{label}</p>
      <p className="mt-2 text-sm font-medium">{value}</p>
    </div>
  );
}
