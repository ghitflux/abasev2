"use client";

import * as React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Building2Icon, CreditCardIcon, FileTextIcon, MapPinIcon, SmartphoneIcon, UserIcon, WorkflowIcon } from "lucide-react";

import type { AssociadoDetail } from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import {
  AssociadoContractsOverview,
  AssociadoDocumentsGrid,
} from "@/components/associados/associado-contracts-overview";
import { formatDate } from "@/lib/formatters";
import { usePermissions } from "@/hooks/use-permissions";
import RoleGuard from "@/components/auth/role-guard";
import {
  ParcelaDetalheDialog,
  type ParcelaDetailTarget,
} from "@/components/contratos/parcela-detalhe-dialog";
import { DetailRouteSkeleton } from "@/components/shared/page-skeletons";
import StatusBadge from "@/components/custom/status-badge";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Button } from "@/components/ui/button";

type AssociadoPageProps = {
  params: Promise<{ id: string }>;
};

function AssociadoPageContent({ params }: AssociadoPageProps) {
  const { id } = React.use(params);
  const associadoId = Number(id);
  const [selectedTarget, setSelectedTarget] =
    React.useState<ParcelaDetailTarget | null>(null);
  const { hasRole } = usePermissions();
  const isAdmin = hasRole("ADMIN");
  const isAnalyst = hasRole("ANALISTA") && !isAdmin;
  const isAgent = hasRole("AGENTE") && !isAdmin;
  const backHref = isAdmin
    ? "/associados"
    : isAnalyst
      ? "/analise"
      : "/agentes/meus-contratos";

  const associadoQuery = useQuery({
    queryKey: ["associado", associadoId],
    queryFn: () => apiFetch<AssociadoDetail>(`associados/${associadoId}`),
  });

  if (associadoQuery.isLoading) {
    return <DetailRouteSkeleton />;
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
            <span>{associado.matricula_display || associado.matricula}</span>
            <span>{associado.cpf_cnpj}</span>
            <StatusBadge
              status={associado.status_visual_slug}
              label={associado.status_visual_label}
            />
            {(associado.mobile_sessions ?? []).some((s) => s.is_active) && (
              <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800 dark:bg-green-900/30 dark:text-green-400">
                <SmartphoneIcon className="h-3 w-3" />
                App ativo
              </span>
            )}
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

      <Accordion type="multiple" defaultValue={["contato", "contratos"]} className="space-y-4">
        {isAgent ? null : (
          <>
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
          </>
        )}

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
            <AssociadoContractsOverview
              associado={associado}
              onParcelaClick={setSelectedTarget}
              showDocuments={false}
              agentRestricted={isAgent}
            />
          </AccordionContent>
        </AccordionItem>

        {isAgent ? null : (
          <AccordionItem value="documentos" className="rounded-[1.75rem] border border-border/60 bg-card/60 px-6">
          <AccordionTrigger className="text-base">Documentos</AccordionTrigger>
          <AccordionContent>
            <AssociadoDocumentsGrid associado={associado} />
          </AccordionContent>
        </AccordionItem>
        )}

        {isAgent ? null : (
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
        )}
      </Accordion>
      <ParcelaDetalheDialog
        associadoId={associadoId}
        target={selectedTarget}
        onOpenChange={(open) => {
          if (!open) {
            setSelectedTarget(null);
          }
        }}
      />
    </div>
  );
}

export default function AssociadoPage(props: AssociadoPageProps) {
  return (
    <RoleGuard allow={["ADMIN", "AGENTE", "ANALISTA"]}>
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
