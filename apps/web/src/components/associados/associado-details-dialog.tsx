"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Building2Icon,
  CreditCardIcon,
  MapPinIcon,
  UserIcon,
} from "lucide-react";

import type { AssociadoDetail } from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import { formatCurrency, formatDate } from "@/lib/formatters";
import {
  AssociadoContractsOverview,
  AssociadoDocumentsGrid,
} from "@/components/associados/associado-contracts-overview";
import CadastroOrigemBadge from "@/components/associados/cadastro-origem-badge";
import StatusBadge from "@/components/custom/status-badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

type Props = {
  associadoId: number | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title?: string;
  description?: string;
  showDocuments?: boolean;
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

function Section({
  icon: Icon,
  title,
  children,
}: React.PropsWithChildren<{
  icon: React.ComponentType<{ className?: string }>;
  title: string;
}>) {
  return (
    <section className="space-y-4 rounded-[1.5rem] border border-border/60 bg-card/60 p-5">
      <div className="flex items-center gap-2">
        <Icon className="size-4 text-primary" />
        <h3 className="text-base font-semibold">{title}</h3>
      </div>
      {children}
    </section>
  );
}

export default function AssociadoDetailsDialog({
  associadoId,
  open,
  onOpenChange,
  title = "Detalhes do associado",
  description = "Consulta rápida do cadastro e dos contratos sem sair da fila operacional.",
  showDocuments = false,
}: Props) {
  const query = useQuery({
    queryKey: ["associado", associadoId],
    queryFn: () => apiFetch<AssociadoDetail>(`associados/${associadoId}`),
    enabled: open && associadoId != null,
  });

  const associado = query.data;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="grid max-h-[calc(100vh-2rem)] w-[96vw] max-w-[96vw] grid-rows-[auto_minmax(0,1fr)] overflow-hidden border-border/60 bg-background/95 p-5 sm:p-6 xl:max-w-[90vw] 2xl:max-w-[110rem]">
        <DialogHeader className="shrink-0">
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>

        <div className="min-h-0 overflow-y-auto pr-1">
          {query.isLoading ? (
            <div className="space-y-4">
              <div className="h-24 animate-pulse rounded-[1.5rem] bg-card/60" />
              <div className="h-64 animate-pulse rounded-[1.5rem] bg-card/60" />
            </div>
          ) : query.isError ? (
            <div className="rounded-[1.5rem] border border-destructive/40 bg-destructive/10 px-5 py-4 text-sm text-destructive">
              {query.error instanceof Error
                ? query.error.message
                : "Falha ao carregar os detalhes do associado."}
            </div>
          ) : associado ? (
            <div className="space-y-5">
              <section className="rounded-[1.75rem] border border-border/60 bg-card/70 p-6">
                <p className="text-sm uppercase tracking-[0.2em] text-muted-foreground">
                  Associado
                </p>
                <h2 className="mt-2 text-2xl font-semibold">
                  {associado.nome_completo}
                </h2>
                <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
                  <span>
                    {associado.matricula_display || associado.matricula}
                  </span>
                  <span>{associado.cpf_cnpj}</span>
                  {associado.contratos[0]?.doacao_associado ? (
                    <span>
                      Doação:{" "}
                      {formatCurrency(associado.contratos[0].doacao_associado)}
                    </span>
                  ) : null}
                  <CadastroOrigemBadge
                    origem={associado.origem_cadastro_slug}
                    label={associado.origem_cadastro_label}
                  />
                  <StatusBadge
                    status={associado.status_visual_slug}
                    label={associado.status_visual_label}
                  />
                </div>
              </section>

              <div className="grid gap-5 xl:grid-cols-3">
                <Section icon={UserIcon} title="Dados pessoais">
                  <div className="grid gap-3 md:grid-cols-2">
                    <DetailItem
                      label="Tipo documento"
                      value={associado.tipo_documento}
                    />
                    <DetailItem
                      label="Data de nascimento"
                      value={formatDate(associado.data_nascimento)}
                    />
                    <DetailItem label="RG" value={associado.rg} />
                    <DetailItem
                      label="Órgão expedidor"
                      value={associado.orgao_expedidor}
                    />
                    <DetailItem label="Profissão" value={associado.profissao} />
                    <DetailItem
                      label="Estado civil"
                      value={associado.estado_civil}
                    />
                    <DetailItem
                      label="Agente"
                      value={associado.agente?.full_name}
                    />
                  </div>
                </Section>

                <Section icon={MapPinIcon} title="Endereço e vínculo">
                  <div className="grid gap-3 md:grid-cols-2">
                    <DetailItem label="CEP" value={associado.endereco?.cep} />
                    <DetailItem
                      label="Endereço"
                      value={associado.endereco?.endereco}
                    />
                    <DetailItem
                      label="Número"
                      value={associado.endereco?.numero}
                    />
                    <DetailItem
                      label="Complemento"
                      value={associado.endereco?.complemento}
                    />
                    <DetailItem
                      label="Bairro"
                      value={associado.endereco?.bairro}
                    />
                    <DetailItem
                      label="Cidade"
                      value={associado.endereco?.cidade}
                    />
                    <DetailItem label="UF" value={associado.endereco?.uf} />
                    <DetailItem
                      label="Órgão público"
                      value={associado.contato?.orgao_publico}
                    />
                    <DetailItem
                      label="Situação do servidor"
                      value={associado.contato?.situacao_servidor}
                    />
                    <DetailItem
                      label="Matrícula do servidor"
                      value={associado.contato?.matricula_servidor}
                    />
                  </div>
                </Section>

                <Section
                  icon={CreditCardIcon}
                  title="Contato e dados bancários"
                >
                  <div className="grid gap-3 md:grid-cols-2">
                    <DetailItem
                      label="Celular"
                      value={associado.contato?.celular}
                    />
                    <DetailItem
                      label="E-mail"
                      value={associado.contato?.email}
                    />
                    <DetailItem
                      label="Banco"
                      value={associado.dados_bancarios?.banco}
                    />
                    <DetailItem
                      label="Agência"
                      value={associado.dados_bancarios?.agencia}
                    />
                    <DetailItem
                      label="Conta"
                      value={associado.dados_bancarios?.conta}
                    />
                    <DetailItem
                      label="Tipo de conta"
                      value={associado.dados_bancarios?.tipo_conta}
                    />
                    <DetailItem
                      label="Chave PIX"
                      value={associado.dados_bancarios?.chave_pix}
                    />
                  </div>
                </Section>
              </div>

              <Section
                icon={Building2Icon}
                title="Contratos, ciclos e parcelas"
              >
                <AssociadoContractsOverview
                  associado={associado}
                  showDocuments={false}
                />
              </Section>

              {showDocuments ? (
                <Section icon={Building2Icon} title="Documentos">
                  <AssociadoDocumentsGrid associado={associado} />
                </Section>
              ) : null}
            </div>
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}
