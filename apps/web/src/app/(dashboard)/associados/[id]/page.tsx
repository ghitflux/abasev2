"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Building2Icon, CreditCardIcon, FileTextIcon, MapPinIcon, UserIcon, WorkflowIcon } from "lucide-react";

import type { AssociadoDetail } from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import { buildBackendFileUrl } from "@/lib/backend-files";
import { formatCurrency, formatDate, formatMonthYear } from "@/lib/formatters";
import { usePermissions } from "@/hooks/use-permissions";
import RoleGuard from "@/components/auth/role-guard";
import StatusBadge from "@/components/custom/status-badge";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";

type AssociadoPageProps = {
  params: Promise<{ id: string }>;
};

function AssociadoPageContent({ params }: AssociadoPageProps) {
  const { id } = React.use(params);
  const associadoId = Number(id);
  const { hasRole } = usePermissions();
  const isAdmin = hasRole("ADMIN");
  const backHref = isAdmin ? "/associados" : "/agentes/meus-contratos";

  const associadoQuery = useQuery({
    queryKey: ["associado", associadoId],
    queryFn: () => apiFetch<AssociadoDetail>(`associados/${associadoId}`),
  });

  if (associadoQuery.isLoading) {
    return (
      <div className="flex items-center gap-3 rounded-3xl border border-border/60 bg-card/60 px-6 py-8 text-sm text-muted-foreground">
        <Spinner />
        Carregando detalhe do associado...
      </div>
    );
  }

  const associado = associadoQuery.data;
  if (!associado) {
    return null;
  }

  return (
    <div className="space-y-6">
      <section className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.2em] text-muted-foreground">Associado</p>
          <h1 className="mt-2 text-3xl font-semibold">{associado.nome_completo}</h1>
          <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
            <span>{associado.matricula}</span>
            <span>{associado.cpf_cnpj}</span>
            <StatusBadge status={associado.status} />
          </div>
        </div>
        <div className="flex flex-wrap gap-3">
          <Button variant="outline" asChild>
            <Link href={backHref}>Voltar</Link>
          </Button>
          {isAdmin ? (
            <Button asChild>
              <Link href={`/associados/${associado.id}/editar`}>Editar</Link>
            </Button>
          ) : null}
        </div>
      </section>

      <Accordion type="multiple" defaultValue={["dados", "contratos"]} className="space-y-4">
        <AccordionItem value="dados" className="rounded-[1.75rem] border border-border/60 bg-card/60 px-6">
          <AccordionTrigger className="text-base">
            <span className="inline-flex items-center gap-2">
              <UserIcon className="size-4 text-primary" />
              Dados Pessoais
            </span>
          </AccordionTrigger>
          <AccordionContent>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <DetailItem label="Tipo documento" value={associado.tipo_documento} />
              <DetailItem label="CPF/CNPJ" value={associado.cpf_cnpj} />
              <DetailItem label="RG" value={associado.rg} />
              <DetailItem label="Órgão expedidor" value={associado.orgao_expedidor} />
              <DetailItem label="Data de nascimento" value={formatDate(associado.data_nascimento)} />
              <DetailItem label="Profissão" value={associado.profissao} />
              <DetailItem label="Estado civil" value={associado.estado_civil} />
              <DetailItem label="Agente" value={associado.agente?.full_name} />
            </div>
          </AccordionContent>
        </AccordionItem>

        <AccordionItem value="endereco" className="rounded-[1.75rem] border border-border/60 bg-card/60 px-6">
          <AccordionTrigger className="text-base">
            <span className="inline-flex items-center gap-2">
              <MapPinIcon className="size-4 text-primary" />
              Endereço
            </span>
          </AccordionTrigger>
          <AccordionContent>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <DetailItem label="CEP" value={associado.endereco?.cep} />
              <DetailItem label="Endereço" value={associado.endereco?.endereco} />
              <DetailItem label="Número" value={associado.endereco?.numero} />
              <DetailItem label="Complemento" value={associado.endereco?.complemento} />
              <DetailItem label="Bairro" value={associado.endereco?.bairro} />
              <DetailItem label="Cidade" value={associado.endereco?.cidade} />
              <DetailItem label="UF" value={associado.endereco?.uf} />
            </div>
          </AccordionContent>
        </AccordionItem>

        <AccordionItem value="banco" className="rounded-[1.75rem] border border-border/60 bg-card/60 px-6">
          <AccordionTrigger className="text-base">
            <span className="inline-flex items-center gap-2">
              <CreditCardIcon className="size-4 text-primary" />
              Dados Bancários
            </span>
          </AccordionTrigger>
          <AccordionContent>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <DetailItem label="Banco" value={associado.dados_bancarios?.banco} />
              <DetailItem label="Agência" value={associado.dados_bancarios?.agencia} />
              <DetailItem label="Conta" value={associado.dados_bancarios?.conta} />
              <DetailItem label="Tipo de conta" value={associado.dados_bancarios?.tipo_conta} />
              <DetailItem label="Chave PIX" value={associado.dados_bancarios?.chave_pix} />
            </div>
          </AccordionContent>
        </AccordionItem>

        <AccordionItem value="contato" className="rounded-[1.75rem] border border-border/60 bg-card/60 px-6">
          <AccordionTrigger className="text-base">
            <span className="inline-flex items-center gap-2">
              <Building2Icon className="size-4 text-primary" />
              Contato e Vínculo
            </span>
          </AccordionTrigger>
          <AccordionContent>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <DetailItem label="Celular" value={associado.contato?.celular} />
              <DetailItem label="E-mail" value={associado.contato?.email} />
              <DetailItem label="Órgão público" value={associado.contato?.orgao_publico} />
              <DetailItem label="Situação do servidor" value={associado.contato?.situacao_servidor} />
              <DetailItem label="Matrícula do servidor" value={associado.contato?.matricula_servidor} />
            </div>
          </AccordionContent>
        </AccordionItem>

        <AccordionItem value="contratos" className="rounded-[1.75rem] border border-border/60 bg-card/60 px-6">
          <AccordionTrigger className="text-base">
            <span className="inline-flex items-center gap-2">
              <FileTextIcon className="size-4 text-primary" />
              Contrato, Ciclos e Parcelas
            </span>
          </AccordionTrigger>
          <AccordionContent className="space-y-4">
            {associado.contratos.map((contrato) => (
              <Card key={contrato.id} className="rounded-[1.5rem] border-border/60 bg-background/40">
                <CardHeader>
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <CardTitle className="text-lg">{contrato.codigo}</CardTitle>
                      <p className="mt-2 text-sm text-muted-foreground">
                        Contrato em {formatDate(contrato.data_contrato)} com mensalidade de{" "}
                        {formatCurrency(contrato.valor_mensalidade)}
                      </p>
                    </div>
                    <StatusBadge status={contrato.status} />
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                    <DetailItem label="Valor bruto" value={formatCurrency(contrato.valor_bruto)} />
                    <DetailItem label="Valor líquido" value={formatCurrency(contrato.valor_liquido)} />
                    <DetailItem label="Mensalidade associativa" value={formatCurrency(contrato.valor_mensalidade)} />
                    <DetailItem label="Taxa de antecipação" value={`${contrato.taxa_antecipacao}%`} />
                    <DetailItem label="Disponível" value={formatCurrency(contrato.margem_disponivel)} />
                    <DetailItem label="Valor total antecipação" value={formatCurrency(contrato.valor_total_antecipacao)} />
                    <DetailItem label="Prazo (meses)" value={String(contrato.prazo_meses)} />
                    <DetailItem label="Comissão do agente" value={formatCurrency(contrato.comissao_agente)} />
                    <DetailItem label="Data de aprovação" value={formatDate(contrato.data_aprovacao)} />
                    <DetailItem label="Primeira mensalidade" value={formatDate(contrato.data_primeira_mensalidade)} />
                    <DetailItem label="Mês de averbação" value={formatMonthYear(contrato.mes_averbacao)} />
                  </div>
                  <div className="grid gap-4 xl:grid-cols-3">
                    {contrato.ciclos.map((ciclo) => (
                      <Card key={ciclo.id} className="rounded-[1.5rem] border-border/60 bg-card/60">
                        <CardHeader>
                          <div className="flex items-center justify-between">
                            <CardTitle className="text-base">Ciclo {ciclo.numero}</CardTitle>
                            <StatusBadge status={ciclo.status} />
                          </div>
                        </CardHeader>
                        <CardContent className="space-y-3">
                          {ciclo.parcelas.map((parcela) => (
                            <div key={parcela.id} className="rounded-2xl border border-border/60 bg-background/60 p-4">
                              <div className="flex items-center justify-between gap-3">
                                <p className="font-medium">
                                  Parcela {parcela.numero}/{ciclo.parcelas.length}
                                </p>
                                <StatusBadge status={parcela.status} />
                              </div>
                              <p className="mt-2 text-sm text-muted-foreground">
                                {formatMonthYear(parcela.referencia_mes)} · {formatCurrency(parcela.valor)}
                              </p>
                              <p className="text-sm text-muted-foreground">
                                Vencimento {formatDate(parcela.data_vencimento)}
                              </p>
                            </div>
                          ))}
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                </CardContent>
              </Card>
            ))}
          </AccordionContent>
        </AccordionItem>

        <AccordionItem value="documentos" className="rounded-[1.75rem] border border-border/60 bg-card/60 px-6">
          <AccordionTrigger className="text-base">Documentos</AccordionTrigger>
          <AccordionContent>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {associado.documentos.length ? (
                associado.documentos.map((documento) => (
                  <a
                    key={documento.id}
                    href={buildBackendFileUrl(documento.arquivo)}
                    target="_blank"
                    rel="noreferrer"
                    className="rounded-2xl border border-border/60 bg-background/60 p-4 transition hover:border-primary/50"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <p className="font-medium capitalize">{documento.tipo.replaceAll("_", " ")}</p>
                      <StatusBadge status={documento.status} />
                    </div>
                    <p className="mt-2 text-sm text-muted-foreground">Abrir arquivo</p>
                  </a>
                ))
              ) : (
                <p className="text-sm text-muted-foreground">Nenhum documento anexado.</p>
              )}
            </div>
          </AccordionContent>
        </AccordionItem>

        <AccordionItem value="esteira" className="rounded-[1.75rem] border border-border/60 bg-card/60 px-6">
          <AccordionTrigger className="text-base">
            <span className="inline-flex items-center gap-2">
              <WorkflowIcon className="size-4 text-primary" />
              Histórico da Esteira
            </span>
          </AccordionTrigger>
          <AccordionContent className="space-y-4">
            <div className="flex flex-wrap items-center gap-3">
              <StatusBadge status={associado.esteira?.etapa_atual ?? "pendente"} />
              <StatusBadge status={associado.esteira?.status ?? "aguardando"} />
            </div>
            <div className="space-y-3">
              {associado.esteira?.transicoes?.length ? (
                associado.esteira.transicoes.map((transicao) => (
                  <div key={transicao.id} className="rounded-2xl border border-border/60 bg-background/60 p-4 text-sm">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <p className="font-medium capitalize">
                        {transicao.de_status.replaceAll("_", " ")} → {transicao.para_status.replaceAll("_", " ")}
                      </p>
                      <span className="text-muted-foreground">{formatDate(transicao.realizado_em)}</span>
                    </div>
                    <p className="mt-2 text-muted-foreground">{transicao.observacao || transicao.acao}</p>
                  </div>
                ))
              ) : (
                <p className="text-sm text-muted-foreground">Sem transições registradas.</p>
              )}
            </div>
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </div>
  );
}

export default function AssociadoPage(props: AssociadoPageProps) {
  return (
    <RoleGuard allow={["ADMIN", "AGENTE"]}>
      <AssociadoPageContent {...props} />
    </RoleGuard>
  );
}

function DetailItem({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="rounded-2xl border border-border/60 bg-background/60 p-4">
      <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">{label}</p>
      <p className="mt-2 text-sm font-medium text-foreground">{value || "-"}</p>
    </div>
  );
}
