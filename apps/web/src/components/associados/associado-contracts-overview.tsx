"use client";

import * as React from "react";

import type { AssociadoDetail } from "@/lib/api/types";
import { buildBackendFileUrl } from "@/lib/backend-files";
import {
  formatCurrency,
  formatDate,
  formatDateTime,
  formatMonthYear,
} from "@/lib/formatters";
import { ParcelaDetailTarget } from "@/components/contratos/parcela-detalhe-dialog";
import StatusBadge from "@/components/custom/status-badge";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type AssociadoSnapshot = Pick<
  AssociadoDetail,
  | "id"
  | "matricula"
  | "matricula_display"
  | "cpf_cnpj"
  | "status_visual_slug"
  | "status_visual_label"
  | "possui_meses_nao_descontados"
  | "meses_nao_descontados_count"
  | "agente"
  | "contratos"
  | "documentos"
>;

type ContractsOverviewProps = {
  associado: AssociadoSnapshot;
  onParcelaClick?: (target: ParcelaDetailTarget) => void;
  defaultOpenContractId?: number | null;
  showDocuments?: boolean;
  agentRestricted?: boolean;
};

function DetailItem({
  label,
  value,
}: {
  label: string;
  value?: string | null;
}) {
  return (
    <div className="rounded-2xl border border-border/60 bg-background/50 p-4">
      <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
        {label}
      </p>
      <p className="mt-2 text-sm font-medium text-foreground">{value || "—"}</p>
    </div>
  );
}

function CycleDocumentLink({
  label,
  arquivo,
}: {
  label: string;
  arquivo: {
    arquivo: string;
    arquivo_referencia: string;
    arquivo_disponivel_localmente: boolean;
    nome_original: string;
  };
}) {
  const title = arquivo.nome_original || arquivo.arquivo_referencia || label;
  if (arquivo.arquivo_disponivel_localmente) {
    return (
      <a
        href={buildBackendFileUrl(arquivo.arquivo)}
        target="_blank"
        rel="noreferrer"
        className="rounded-2xl border border-border/60 bg-background/60 p-3 transition hover:border-primary/50"
      >
        <p className="text-sm font-medium">{label}</p>
        <p className="mt-1 text-xs text-muted-foreground">{title}</p>
      </a>
    );
  }

  return (
    <div className="rounded-2xl border border-dashed border-border/60 bg-background/40 p-3">
      <p className="text-sm font-medium">{label}</p>
      <p className="mt-1 text-xs text-muted-foreground">{title}</p>
      <p className="mt-1 text-[11px] text-amber-200">Referência de arquivo legado</p>
    </div>
  );
}

function InitialPaymentEvidenceCard({
  arquivo,
}: {
  arquivo: {
    nome: string;
    url: string;
    arquivo_referencia: string;
    arquivo_disponivel_localmente: boolean;
    tipo_referencia: string;
  };
}) {
  const title = arquivo.arquivo_referencia || arquivo.nome;
  if (arquivo.arquivo_disponivel_localmente && arquivo.url) {
    return (
      <a
        href={buildBackendFileUrl(arquivo.url)}
        target="_blank"
        rel="noreferrer"
        className="rounded-2xl border border-border/60 bg-background/60 p-3 transition hover:border-primary/50"
      >
        <p className="text-sm font-medium">{arquivo.nome}</p>
        <p className="mt-1 text-xs text-muted-foreground">{title}</p>
      </a>
    );
  }

  return (
    <div className="rounded-2xl border border-dashed border-border/60 bg-background/40 p-3">
      <p className="text-sm font-medium">{arquivo.nome}</p>
      <p className="mt-1 text-xs text-muted-foreground">{title}</p>
      <p className="mt-1 text-[11px] text-amber-200">
        {arquivo.tipo_referencia === "placeholder_recebido"
          ? "Pagamento recebido e aguardando acervo"
          : "Referência de arquivo legado"}
      </p>
    </div>
  );
}

function LiquidacaoEvidenceCard({
  arquivo,
}: {
  arquivo: {
    nome: string;
    url: string;
    arquivo_referencia: string;
    arquivo_disponivel_localmente: boolean;
    tipo_referencia: string;
  };
}) {
  const title = arquivo.arquivo_referencia || arquivo.nome;
  if (arquivo.arquivo_disponivel_localmente && arquivo.url) {
    return (
      <a
        href={buildBackendFileUrl(arquivo.url)}
        target="_blank"
        rel="noreferrer"
        className="rounded-2xl border border-border/60 bg-background/60 p-3 transition hover:border-primary/50"
      >
        <p className="text-sm font-medium">{arquivo.nome}</p>
        <p className="mt-1 text-xs text-muted-foreground">{title}</p>
      </a>
    );
  }

  return (
    <div className="rounded-2xl border border-dashed border-border/60 bg-background/40 p-3">
      <p className="text-sm font-medium">{arquivo.nome}</p>
      <p className="mt-1 text-xs text-muted-foreground">{title}</p>
      <p className="mt-1 text-[11px] text-amber-200">
        {arquivo.tipo_referencia === "local"
          ? "Arquivo local"
          : "Referência de arquivo legado"}
      </p>
    </div>
  );
}

function DevolucaoEvidenceCard({
  arquivo,
}: {
  arquivo: {
    nome: string;
    url: string;
    arquivo_referencia: string;
    arquivo_disponivel_localmente: boolean;
    tipo_referencia: string;
  };
}) {
  const title = arquivo.arquivo_referencia || arquivo.nome;
  if (arquivo.arquivo_disponivel_localmente && arquivo.url) {
    return (
      <a
        href={buildBackendFileUrl(arquivo.url)}
        target="_blank"
        rel="noreferrer"
        className="rounded-2xl border border-border/60 bg-background/60 p-3 transition hover:border-primary/50"
      >
        <p className="text-sm font-medium">{arquivo.nome}</p>
        <p className="mt-1 text-xs text-muted-foreground">{title}</p>
      </a>
    );
  }

  return (
    <div className="rounded-2xl border border-dashed border-border/60 bg-background/40 p-3">
      <p className="text-sm font-medium">{arquivo.nome}</p>
      <p className="mt-1 text-xs text-muted-foreground">{title}</p>
      <p className="mt-1 text-[11px] text-amber-200">
        {arquivo.tipo_referencia === "local"
          ? "Arquivo local"
          : "Referência de arquivo legado"}
      </p>
    </div>
  );
}

function formatDevolucaoTipoLabel(tipo: string) {
  return tipo.replaceAll("_", " ");
}

export function AssociadoDocumentCard({
  documento,
}: {
  documento: AssociadoSnapshot["documentos"][number];
}) {
  const title =
    documento.nome_original || documento.arquivo_referencia || "Documento";

  if (documento.arquivo_disponivel_localmente) {
    return (
      <a
        href={buildBackendFileUrl(documento.arquivo)}
        target="_blank"
        rel="noreferrer"
        className="rounded-2xl border border-border/60 bg-background/60 p-4 transition hover:border-primary/50"
      >
        <div className="flex items-center justify-between gap-3">
          <p className="font-medium capitalize">{documento.tipo.replaceAll("_", " ")}</p>
          <StatusBadge status={documento.status} />
        </div>
        <p className="mt-2 text-sm text-muted-foreground">{title}</p>
      </a>
    );
  }

  return (
    <div className="rounded-2xl border border-dashed border-border/60 bg-background/40 p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="font-medium capitalize">{documento.tipo.replaceAll("_", " ")}</p>
        <StatusBadge status={documento.status} />
      </div>
      <p className="mt-2 text-sm text-muted-foreground">{title}</p>
      <p className="mt-1 text-[11px] text-amber-200">
        {documento.tipo_referencia === "local"
          ? "Arquivo local"
          : "Referência de arquivo legado"}
      </p>
    </div>
  );
}

export function AssociadoDocumentsGrid({
  associado,
}: {
  associado: AssociadoSnapshot;
}) {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {associado.documentos.length ? (
        associado.documentos.map((documento) => (
          <AssociadoDocumentCard key={documento.id} documento={documento} />
        ))
      ) : (
        <p className="text-sm text-muted-foreground">Nenhum documento anexado.</p>
      )}
    </div>
  );
}

export function AssociadoSnapshotSummary({
  associado,
}: {
  associado: AssociadoSnapshot;
}) {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <DetailItem
        label="Matrícula do servidor"
        value={associado.matricula_display || associado.matricula}
      />
      <DetailItem label="CPF/CNPJ" value={associado.cpf_cnpj} />
      <DetailItem label="Agente" value={associado.agente?.full_name} />
      <div className="rounded-2xl border border-border/60 bg-background/50 p-4">
        <p className="text-xs uppercase tracking-[0.16em] text-muted-foreground">
          Status
        </p>
        <div className="mt-2">
          <StatusBadge
            status={associado.status_visual_slug}
            label={associado.status_visual_label}
          />
          {associado.possui_meses_nao_descontados ? (
            <p className="mt-2 text-xs text-amber-200">
              {associado.meses_nao_descontados_count} mês(es) não descontado(s)
            </p>
          ) : null}
        </div>
      </div>
    </div>
  );
}

export function AssociadoContractsOverview({
  associado,
  onParcelaClick,
  defaultOpenContractId,
  showDocuments = true,
  agentRestricted = false,
}: ContractsOverviewProps) {
  const defaultValue = React.useMemo(() => {
    if (defaultOpenContractId) {
      return [`contrato-${defaultOpenContractId}`];
    }
    return associado.contratos.length
      ? [`contrato-${associado.contratos[0].id}`]
      : [];
  }, [associado.contratos, defaultOpenContractId]);

  return (
    <div className="space-y-4">
      <Accordion type="multiple" defaultValue={defaultValue} className="space-y-4">
        {associado.contratos.map((contrato) => (
          <AccordionItem
            key={contrato.id}
            value={`contrato-${contrato.id}`}
            className="overflow-hidden rounded-[1.5rem] border border-border/60 bg-background/40"
          >
            <AccordionTrigger className="px-6 py-5 text-base hover:no-underline">
              <div className="flex w-full flex-wrap items-center justify-between gap-3 pr-4">
                <div className="text-left">
                  <CardTitle className="text-lg">{contrato.codigo}</CardTitle>
                  <p className="mt-2 text-sm text-muted-foreground">
                    Contrato em {formatDate(contrato.data_contrato)} com mensalidade de{" "}
                    {formatCurrency(contrato.valor_mensalidade)}
                  </p>
                </div>
                <div className="text-right">
                  <StatusBadge
                    status={contrato.status_visual_slug}
                    label={contrato.status_visual_label}
                  />
                  {contrato.possui_meses_nao_descontados ? (
                    <p className="mt-2 text-xs text-amber-200">
                      {contrato.meses_nao_descontados_count} mês(es) não descontado(s)
                    </p>
                  ) : null}
                </div>
              </div>
            </AccordionTrigger>
            <AccordionContent className="space-y-4 px-6">
              {agentRestricted ? null : (
                <>
                  <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                    <DetailItem label="Valor bruto" value={formatCurrency(contrato.valor_bruto)} />
                    <DetailItem label="Valor líquido" value={formatCurrency(contrato.valor_liquido)} />
                    <DetailItem
                      label="Mensalidade associativa"
                      value={formatCurrency(contrato.valor_mensalidade)}
                    />
                    <DetailItem
                      label="Taxa de antecipação"
                      value={`${contrato.taxa_antecipacao}%`}
                    />
                    <DetailItem label="Disponível" value={formatCurrency(contrato.margem_disponivel)} />
                    <DetailItem
                      label="Valor total antecipação"
                      value={formatCurrency(contrato.valor_total_antecipacao)}
                    />
                    <DetailItem label="Prazo (meses)" value={String(contrato.prazo_meses)} />
                    <DetailItem
                      label="Comissão do agente"
                      value={formatCurrency(contrato.comissao_agente)}
                    />
                    <DetailItem label="Data de aprovação" value={formatDate(contrato.data_aprovacao)} />
                    <DetailItem
                      label="Primeira mensalidade"
                      value={formatDate(contrato.data_primeira_mensalidade)}
                    />
                    <DetailItem
                      label="Mês de averbação"
                      value={formatMonthYear(contrato.mes_averbacao)}
                    />
                    <DetailItem
                      label="1º ciclo ativado em"
                      value={formatDate(contrato.data_primeiro_ciclo_ativado)}
                    />
                  </div>

                  <Card className="rounded-[1.5rem] border-border/60 bg-card/60">
                    <CardHeader>
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <CardTitle className="text-base">Pagamento da efetivação</CardTitle>
                        <StatusBadge
                          status={contrato.pagamento_inicial_status}
                          label={contrato.pagamento_inicial_status_label}
                        />
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div className="grid gap-4 md:grid-cols-3">
                        <DetailItem
                          label="Valor pago"
                          value={
                            contrato.pagamento_inicial_valor
                              ? formatCurrency(contrato.pagamento_inicial_valor)
                              : "Não informado"
                          }
                        />
                        <DetailItem
                          label="Recebido em"
                          value={
                            contrato.pagamento_inicial_paid_at
                              ? formatDateTime(contrato.pagamento_inicial_paid_at)
                              : "Aguardando tesouraria"
                          }
                        />
                        <DetailItem
                          label="Evidências"
                          value={String(contrato.pagamento_inicial_evidencias.length)}
                        />
                      </div>
                      {contrato.pagamento_inicial_evidencias.length ? (
                        <div className="grid gap-3 md:grid-cols-2">
                          {contrato.pagamento_inicial_evidencias.map((arquivo) => (
                            <InitialPaymentEvidenceCard key={arquivo.id} arquivo={arquivo} />
                          ))}
                        </div>
                      ) : (
                        <p className="text-sm text-muted-foreground">
                          Nenhuma evidência de pagamento inicial disponível.
                        </p>
                      )}
                    </CardContent>
                  </Card>

                  {contrato.liquidacao_contrato ? (
                    <Card className="rounded-[1.5rem] border-border/60 bg-card/60">
                      <CardHeader>
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <CardTitle className="text-base">Liquidação do contrato</CardTitle>
                          <StatusBadge status={contrato.liquidacao_contrato.status} />
                        </div>
                      </CardHeader>
                      <CardContent className="space-y-4">
                        <div className="grid gap-4 md:grid-cols-3">
                          <DetailItem
                            label="Data da liquidação"
                            value={formatDate(contrato.liquidacao_contrato.data_liquidacao)}
                          />
                          <DetailItem
                            label="Valor total"
                            value={formatCurrency(contrato.liquidacao_contrato.valor_total)}
                          />
                          <DetailItem
                            label="Responsável"
                            value={contrato.liquidacao_contrato.realizado_por?.full_name}
                          />
                        </div>
                        {contrato.liquidacao_contrato.observacao ? (
                          <div className="rounded-2xl border border-border/60 bg-background/60 p-4 text-sm text-muted-foreground">
                            {contrato.liquidacao_contrato.observacao}
                          </div>
                        ) : null}
                        {contrato.liquidacao_contrato.comprovante ? (
                          <LiquidacaoEvidenceCard
                            arquivo={contrato.liquidacao_contrato.comprovante}
                          />
                        ) : (
                          <p className="text-sm text-muted-foreground">
                            Nenhum comprovante de liquidação disponível.
                          </p>
                        )}
                        {contrato.liquidacao_contrato.parcelas.length ? (
                          <div className="space-y-3">
                            <p className="text-sm font-medium text-foreground">
                              Parcelas afetadas
                            </p>
                            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                              {contrato.liquidacao_contrato.parcelas.map((parcela) => (
                                <div
                                  key={`${contrato.liquidacao_contrato?.id}-${parcela.id}`}
                                  className="rounded-2xl border border-border/60 bg-background/60 p-4"
                                >
                                  <div className="flex items-center justify-between gap-3">
                                    <p className="font-medium">
                                      Parcela {parcela.numero}
                                    </p>
                                    <StatusBadge status={parcela.status} />
                                  </div>
                                  <p className="mt-2 text-sm text-muted-foreground">
                                    {formatMonthYear(parcela.referencia_mes)} ·{" "}
                                    {formatCurrency(parcela.valor)}
                                  </p>
                                  <p className="text-sm text-muted-foreground">
                                    Pagamento {formatDate(parcela.data_pagamento)}
                                  </p>
                                </div>
                              ))}
                            </div>
                          </div>
                        ) : null}
                      </CardContent>
                    </Card>
                  ) : null}

                  {contrato.devolucoes_associado.length ? (
                    <Card className="rounded-[1.5rem] border-border/60 bg-card/60">
                      <CardHeader>
                        <div className="flex flex-wrap items-center justify-between gap-3">
                          <CardTitle className="text-base">Devoluções ao associado</CardTitle>
                          <StatusBadge
                            status={contrato.devolucoes_associado[0].status}
                            label={`${contrato.devolucoes_associado.length} registro(s)`}
                          />
                        </div>
                      </CardHeader>
                      <CardContent className="space-y-4">
                        <div className="grid gap-4 xl:grid-cols-2">
                          {contrato.devolucoes_associado.map((devolucao) => (
                            <div
                              key={devolucao.id}
                              className="space-y-4 rounded-[1.5rem] border border-border/60 bg-background/50 p-4"
                            >
                              <div className="flex flex-wrap items-center justify-between gap-3">
                                <div>
                                  <p className="font-medium capitalize">
                                    {formatDevolucaoTipoLabel(devolucao.tipo)}
                                  </p>
                                  <p className="text-sm text-muted-foreground">
                                    {formatDate(devolucao.data_devolucao)} ·{" "}
                                    {formatCurrency(devolucao.valor)}
                                  </p>
                                </div>
                                <StatusBadge status={devolucao.status} />
                              </div>
                              <div className="grid gap-3 md:grid-cols-2">
                                <DetailItem
                                  label="Responsável"
                                  value={devolucao.realizado_por?.full_name}
                                />
                                <DetailItem
                                  label="Parcelas"
                                  value={String(devolucao.quantidade_parcelas)}
                                />
                                <DetailItem
                                  label="Competência"
                                  value={
                                    devolucao.competencia_referencia
                                      ? formatMonthYear(devolucao.competencia_referencia)
                                      : "Sem competência"
                                  }
                                />
                              </div>
                              <div className="rounded-2xl border border-border/60 bg-background/60 p-4 text-sm text-muted-foreground">
                                {devolucao.motivo}
                              </div>
                              {devolucao.anexos.length ? (
                                <div className="grid gap-3 md:grid-cols-2">
                                  {devolucao.anexos.map((anexo) => (
                                    <DevolucaoEvidenceCard
                                      key={`${devolucao.id}-${anexo.arquivo_referencia}-${anexo.nome}`}
                                      arquivo={anexo}
                                    />
                                  ))}
                                </div>
                              ) : null}
                              {devolucao.revertida_em ? (
                                <div className="rounded-2xl border border-border/60 bg-background/60 p-4 text-sm text-muted-foreground">
                                  Revertida em {formatDateTime(devolucao.revertida_em)}
                                  {devolucao.revertida_por?.full_name
                                    ? ` por ${devolucao.revertida_por.full_name}.`
                                    : "."}{" "}
                                  {devolucao.motivo_reversao || "Sem motivo informado."}
                                </div>
                              ) : null}
                            </div>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  ) : null}
                </>
              )}

              <div className="grid gap-4 xl:grid-cols-3">
                {contrato.ciclos.map((ciclo) => (
                  <Card key={ciclo.id} className="rounded-[1.5rem] border-border/60 bg-card/60">
                    <CardHeader>
                      <div className="flex items-center justify-between gap-3">
                        <CardTitle className="text-base">Ciclo {ciclo.numero}</CardTitle>
                        <StatusBadge
                          status={ciclo.status_visual_slug}
                          label={ciclo.status_visual_label}
                        />
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div className="rounded-2xl border border-border/60 bg-background/60 p-4 text-sm">
                        <p className="font-medium">
                          Ativado em {formatDate(ciclo.data_ativacao_ciclo)}
                        </p>
                        <p className="mt-2 text-muted-foreground">
                          Origem:{" "}
                          {ciclo.ativacao_inferida
                            ? `${ciclo.origem_data_ativacao} (inferida)`
                            : ciclo.origem_data_ativacao}
                        </p>
                        <p className="text-muted-foreground">
                          Renovação ativada em: {formatDate(ciclo.data_solicitacao_renovacao)}
                        </p>
                        {ciclo.data_renovacao ? (
                          <p className="text-muted-foreground">
                            Renovado em {formatDateTime(ciclo.data_renovacao)}
                          </p>
                        ) : null}
                        {ciclo.origem_renovacao ? (
                          <p className="text-muted-foreground">
                            Origem da renovação: {ciclo.origem_renovacao}
                          </p>
                        ) : null}
                      </div>
                      <div className="grid gap-3 md:grid-cols-2">
                        {ciclo.parcelas.map((parcela) => (
                          <button
                            key={parcela.id}
                            type="button"
                            onClick={() =>
                              onParcelaClick?.({
                                contratoId: contrato.id,
                                referenciaMes: parcela.referencia_mes,
                                kind: "cycle",
                              })
                            }
                            className="rounded-2xl border border-border/60 bg-background/60 p-4 text-left transition hover:border-primary/50"
                          >
                            <div className="flex items-center justify-between gap-3">
                              <p className="font-medium">
                                Parcela {parcela.numero}/{ciclo.parcelas.length}
                              </p>
                              <StatusBadge status={parcela.status} />
                            </div>
                            <p className="mt-2 text-sm text-muted-foreground">
                              {formatMonthYear(parcela.referencia_mes)} ·{" "}
                              {formatCurrency(parcela.valor)}
                            </p>
                            <p className="text-sm text-muted-foreground">
                              Vencimento {formatDate(parcela.data_vencimento)}
                            </p>
                          </button>
                        ))}
                      </div>
                      {ciclo.termo_antecipacao || ciclo.comprovantes_ciclo.length ? (
                        <div className="space-y-3 pt-1">
                          <p className="text-sm font-medium text-foreground">
                            {agentRestricted ? "Comprovantes do agente" : "Documentos do ciclo"}
                          </p>
                          <div className="grid gap-3">
                            {!agentRestricted && ciclo.termo_antecipacao ? (
                              <CycleDocumentLink
                                label="Termo de antecipação"
                                arquivo={ciclo.termo_antecipacao}
                              />
                            ) : null}
                            {ciclo.comprovantes_ciclo.map((arquivo) => (
                              <CycleDocumentLink
                                key={`${arquivo.tipo}-${arquivo.arquivo_referencia}`}
                                label={arquivo.tipo.replaceAll("_", " ")}
                                arquivo={arquivo}
                              />
                            ))}
                          </div>
                        </div>
                      ) : null}
                    </CardContent>
                  </Card>
                ))}
              </div>

              {contrato.meses_nao_pagos.filter(
                (mes) =>
                  !["quitada", "descontado", "liquidada"].includes(String(mes.status)),
              ).length ? (
                <div className="space-y-3">
                  <p className="text-sm font-medium text-foreground">Parcelas não descontadas</p>
                  <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                    {contrato.meses_nao_pagos
                      .filter(
                        (mes) =>
                          !["quitada", "descontado", "liquidada"].includes(
                            String(mes.status),
                          ),
                      )
                      .map((mes) => (
                      <button
                        key={mes.id}
                        type="button"
                        onClick={() =>
                          onParcelaClick?.({
                            contratoId: contrato.id,
                            referenciaMes: mes.referencia_mes,
                            kind: "unpaid",
                          })
                        }
                        className="rounded-[1.5rem] border border-border/60 bg-card/60 text-left transition hover:border-primary/50"
                      >
                        <CardContent className="space-y-2 pt-6">
                          <div className="flex items-center justify-between gap-3">
                            <p className="font-medium">{formatMonthYear(mes.referencia_mes)}</p>
                            <StatusBadge status={mes.status} />
                          </div>
                          <p className="text-sm text-muted-foreground">
                            {formatCurrency(mes.valor)}
                          </p>
                          <p className="text-sm text-muted-foreground">
                            {mes.observacao || "Sem observação."}
                          </p>
                        </CardContent>
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}

              {contrato.meses_nao_pagos.filter((mes) =>
                ["quitada", "descontado", "liquidada"].includes(String(mes.status)),
              ).length ? (
                <div className="space-y-3">
                  <p className="text-sm font-medium text-foreground">Quitadas fora do ciclo</p>
                  <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                    {contrato.meses_nao_pagos
                      .filter((mes) =>
                        ["quitada", "descontado", "liquidada"].includes(String(mes.status)),
                      )
                      .map((mes) => (
                        <button
                          key={mes.id}
                          type="button"
                          onClick={() =>
                            onParcelaClick?.({
                              contratoId: contrato.id,
                              referenciaMes: mes.referencia_mes,
                              kind: "unpaid",
                            })
                          }
                          className="rounded-[1.5rem] border border-border/60 bg-card/60 text-left transition hover:border-primary/50"
                        >
                          <CardContent className="space-y-2 pt-6">
                            <div className="flex items-center justify-between gap-3">
                              <p className="font-medium">{formatMonthYear(mes.referencia_mes)}</p>
                              <StatusBadge status={mes.status} />
                            </div>
                            <p className="text-sm text-muted-foreground">
                              {formatCurrency(mes.valor)}
                            </p>
                            <p className="text-sm text-muted-foreground">
                              {mes.observacao || "Sem observação."}
                            </p>
                          </CardContent>
                        </button>
                      ))}
                  </div>
                </div>
              ) : null}

              {!agentRestricted && contrato.movimentos_financeiros_avulsos.length ? (
                <div className="space-y-3">
                  <p className="text-sm font-medium text-foreground">
                    Movimentos financeiros fora do ciclo
                  </p>
                  <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                    {contrato.movimentos_financeiros_avulsos.map((movimento) => (
                      <Card
                        key={movimento.id}
                        className="rounded-[1.5rem] border-border/60 bg-card/60"
                      >
                        <CardContent className="space-y-2 pt-6">
                          <div className="flex items-center justify-between gap-3">
                            <p className="font-medium">
                              {formatMonthYear(movimento.referencia_mes)}
                            </p>
                            <StatusBadge status={movimento.status} />
                          </div>
                          <p className="text-sm text-muted-foreground">
                            {formatCurrency(movimento.valor)}
                          </p>
                          <p className="text-sm text-muted-foreground">
                            {movimento.observacao || "Sem observação."}
                          </p>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </div>
              ) : null}
            </AccordionContent>
          </AccordionItem>
        ))}
      </Accordion>

      {showDocuments && !agentRestricted ? (
        <section className="space-y-3">
          <p className="text-sm font-medium text-foreground">Documentos do associado</p>
          <AssociadoDocumentsGrid associado={associado} />
        </section>
      ) : null}
    </div>
  );
}
