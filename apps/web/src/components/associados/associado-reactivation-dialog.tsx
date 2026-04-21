"use client";

import * as React from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { LoaderCircleIcon } from "lucide-react";
import { toast } from "sonner";

import type { AssociadoDetail, Documento, SimpleUser } from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import { buildBackendFileUrl } from "@/lib/backend-files";
import {
  centsToDecimal,
  decimalToCents,
  formatCurrency,
  formatLongMonthYear,
} from "@/lib/formatters";
import {
  calculateContratoDates,
  parseIsoDate,
} from "@/components/associados/contrato-dates";
import DatePicker from "@/components/custom/date-picker";
import FileUploadDropzone from "@/components/custom/file-upload-dropzone";
import InputCurrency from "@/components/custom/input-currency";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Field,
  FieldContent,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const PRAZO_OPTIONS = [
  { value: 3, label: "3 meses" },
  { value: 4, label: "4 meses" },
];

const DOCUMENT_FIELDS = [
  { key: "documento_frente", label: "Documento (frente)" },
  { key: "documento_verso", label: "Documento (verso)" },
  { key: "comprovante_residencia", label: "Comprovante de residência" },
  { key: "contracheque", label: "Contracheque atual" },
  { key: "termo_adesao", label: "Termo de adesão" },
  { key: "termo_antecipacao", label: "Termo de antecipação" },
  { key: "anexo_extra_1", label: "Anexo extra 1" },
  { key: "anexo_extra_2", label: "Anexo extra 2" },
] as const;

const DOCUMENT_ACCEPT = {
  "application/pdf": [".pdf"],
  "image/png": [".png"],
  "image/jpeg": [".jpg", ".jpeg"],
};

type ReactivationDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  associado: AssociadoDetail;
  onSuccess: (payload: AssociadoDetail) => void;
};

type ReactivationState = {
  valorBrutoTotal: number | null;
  valorLiquido: number | null;
  prazoMeses: number;
  mensalidade: number | null;
  dataAprovacao?: Date;
  agenteResponsavelId: string;
  percentualRepasse: string;
};

function buildInitialState(associado: AssociadoDetail): ReactivationState {
  const contrato = associado.contratos[0];
  return {
    valorBrutoTotal: decimalToCents(contrato?.valor_bruto ?? null),
    valorLiquido: decimalToCents(contrato?.valor_liquido ?? null),
    prazoMeses: contrato?.prazo_meses ?? 3,
    mensalidade: decimalToCents(contrato?.valor_mensalidade ?? null),
    dataAprovacao:
      parseIsoDate(contrato?.data_aprovacao) ?? new Date(),
    agenteResponsavelId: associado.agente?.id ? String(associado.agente.id) : "",
    percentualRepasse: associado.percentual_repasse ?? "",
  };
}

function computePreview(state: ReactivationState) {
  const valorBrutoTotal = state.valorBrutoTotal ?? 0;
  const valorLiquido = state.valorLiquido ?? 0;
  const mensalidade = state.mensalidade ?? 0;
  const prazoMeses = state.prazoMeses;
  const percentualRepasse =
    Number.parseFloat(state.percentualRepasse || "10") || 10;

  const bruto30 = Math.round(valorBrutoTotal * 0.3);
  const margemLiquido = valorLiquido - bruto30;
  const valorTotalAntecipacao = mensalidade * prazoMeses;
  const doacaoAssociado = Math.round(valorTotalAntecipacao * 0.3);
  const margemDisponivel = valorTotalAntecipacao - doacaoAssociado;
  const comissaoAgente = Math.round(
    margemDisponivel * (percentualRepasse / 100),
  );
  const contratoDates = calculateContratoDates(state.dataAprovacao, new Date());

  return {
    bruto30,
    margemLiquido,
    valorTotalAntecipacao,
    doacaoAssociado,
    margemDisponivel,
    comissaoAgente,
    contratoDates,
  };
}

export default function AssociadoReactivationDialog({
  open,
  onOpenChange,
  associado,
  onSuccess,
}: ReactivationDialogProps) {
  const [state, setState] = React.useState<ReactivationState>(() =>
    buildInitialState(associado),
  );
  const [documents, setDocuments] = React.useState<Record<string, File | null>>({});

  const agentesQuery = useQuery({
    queryKey: ["associados-agentes"],
    queryFn: () => apiFetch<SimpleUser[]>("associados/agentes"),
    staleTime: 5 * 60 * 1000,
  });

  React.useEffect(() => {
    if (!open) {
      return;
    }
    setState(buildInitialState(associado));
    setDocuments({});
  }, [associado, open]);

  const currentDocumentsByType = React.useMemo(
    () =>
      new Map(
        (associado.documentos ?? []).map((documento) => [documento.tipo, documento]),
      ),
    [associado.documentos],
  );

  const preview = React.useMemo(() => computePreview(state), [state]);

  const reactivationMutation = useMutation({
    mutationFn: async () => {
      if (!state.agenteResponsavelId) {
        throw new Error("Selecione o agente responsável para a reativação.");
      }
      if (!state.valorBrutoTotal || !state.valorLiquido || !state.mensalidade) {
        throw new Error("Preencha valor bruto, valor líquido e mensalidade.");
      }

      const payload = await apiFetch<AssociadoDetail>(
        `associados/${associado.id}/reativar`,
        {
          method: "POST",
          body: {
            valor_bruto_total: centsToDecimal(state.valorBrutoTotal),
            valor_liquido: centsToDecimal(state.valorLiquido),
            prazo_meses: state.prazoMeses,
            mensalidade: centsToDecimal(state.mensalidade),
            data_aprovacao: state.dataAprovacao
              ? state.dataAprovacao.toISOString().slice(0, 10)
              : undefined,
            agente_responsavel_id: Number.parseInt(state.agenteResponsavelId, 10),
            ...(state.percentualRepasse.trim()
              ? {
                  percentual_repasse: Number.parseFloat(
                    state.percentualRepasse,
                  ).toFixed(2),
                }
              : {}),
          },
        },
      );

      const uploads = Object.entries(documents).filter(([, file]) => Boolean(file));
      if (uploads.length) {
        const results = await Promise.allSettled(
          uploads.map(async ([tipo, file]) => {
            const formData = new FormData();
            formData.append("tipo", tipo);
            formData.append("arquivo", file as File);
            await apiFetch(`associados/${associado.id}/documentos`, {
              method: "POST",
              formData,
            });
          }),
        );
        const failedUploads = results.filter(
          (result) => result.status === "rejected",
        ).length;
        if (failedUploads > 0) {
          toast.error(
            `Reativação criada, mas ${failedUploads} anexo(s) não foram enviados.`,
          );
        }
      }

      try {
        return await apiFetch<AssociadoDetail>(`associados/${associado.id}`);
      } catch {
        return payload;
      }
    },
    onSuccess: (payload) => {
      toast.success("Reativação enviada para análise.");
      onSuccess(payload);
      onOpenChange(false);
    },
    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : "Falha ao enviar reativação para análise.",
      );
    },
  });

  const agenteOptions = agentesQuery.data ?? [];

  const updateDocument = React.useCallback((tipo: string, file: File | null) => {
    setDocuments((current) => ({ ...current, [tipo]: file }));
  }, []);

  const renderCurrentDocument = React.useCallback(
    (documento?: Documento) => {
      if (!documento) {
        return (
          <p className="text-xs text-muted-foreground">
            Nenhum anexo atual para este tipo.
          </p>
        );
      }

      return (
        <div className="rounded-2xl border border-border/60 bg-background/50 p-3">
          <a
            href={buildBackendFileUrl(documento.arquivo)}
            target="_blank"
            rel="noreferrer"
            className="text-sm font-medium text-primary underline-offset-4 hover:underline"
          >
            {documento.nome_original ||
              (documento.arquivo_referencia
                ? documento.arquivo_referencia.split("/").pop()
                : null) ||
              "Abrir anexo atual"}
          </a>
          <p className="mt-1 text-xs text-muted-foreground">
            Status atual: {documento.status || "pendente"}
          </p>
        </div>
      );
    },
    [],
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[calc(100vh-2rem)] w-full max-w-5xl sm:max-w-5xl overflow-hidden rounded-4xl border-border/60 bg-background/95 p-0">
        <div className="grid max-h-[calc(100vh-2rem)] grid-rows-[auto_minmax(0,1fr)_auto]">
          <DialogHeader className="border-b border-border/60 px-6 py-5 text-left">
            <DialogTitle>Reativar associado</DialogTitle>
            <DialogDescription>
              Crie um novo contrato para {associado.nome_completo} e envie a
              solicitação direto para a tesouraria, preservando o histórico
              anterior.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-6 overflow-y-auto px-6 py-5">
            <section className="rounded-[1.5rem] border border-border/60 bg-card/50 p-5">
              <div className="mb-4">
                <h3 className="text-base font-semibold">Base financeira</h3>
                <p className="text-sm text-muted-foreground">
                  Os valores derivados seguem a mesma regra da etapa 5 do
                  cadastro.
                </p>
              </div>
              <FieldGroup className="grid gap-5 md:grid-cols-5">
                <Field>
                  <FieldLabel>Valor bruto total</FieldLabel>
                  <FieldContent>
                    <InputCurrency
                      value={state.valorBrutoTotal}
                      onChange={(value) =>
                        setState((current) => ({
                          ...current,
                          valorBrutoTotal: value,
                        }))
                      }
                    />
                  </FieldContent>
                </Field>
                <Field>
                  <FieldLabel>Valor líquido</FieldLabel>
                  <FieldContent>
                    <InputCurrency
                      value={state.valorLiquido}
                      onChange={(value) =>
                        setState((current) => ({
                          ...current,
                          valorLiquido: value,
                        }))
                      }
                    />
                  </FieldContent>
                </Field>
                <Field>
                  <FieldLabel>Prazo</FieldLabel>
                  <FieldContent>
                    <Select
                      value={String(state.prazoMeses)}
                      onValueChange={(value) =>
                        setState((current) => ({
                          ...current,
                          prazoMeses: Number.parseInt(value, 10),
                        }))
                      }
                    >
                      <SelectTrigger className="rounded-xl bg-card/60">
                        <SelectValue placeholder="Prazo" />
                      </SelectTrigger>
                      <SelectContent>
                        {PRAZO_OPTIONS.map((option) => (
                          <SelectItem key={option.value} value={String(option.value)}>
                            {option.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </FieldContent>
                </Field>
                <Field>
                  <FieldLabel>30% do bruto</FieldLabel>
                  <FieldContent>
                    <Input
                      readOnly
                      value={formatCurrency(preview.bruto30 / 100)}
                      className="rounded-xl bg-card/60"
                    />
                  </FieldContent>
                </Field>
                <Field>
                  <FieldLabel>Margem líquida</FieldLabel>
                  <FieldContent>
                    <Input
                      readOnly
                      value={formatCurrency(preview.margemLiquido / 100)}
                      className="rounded-xl bg-card/60"
                    />
                  </FieldContent>
                </Field>
              </FieldGroup>
            </section>

            <section className="rounded-[1.5rem] border border-border/60 bg-card/50 p-5">
              <div className="mb-4">
                <h3 className="text-base font-semibold">Contrato da reativação</h3>
                <p className="text-sm text-muted-foreground">
                  Se o percentual de repasse ficar em branco, o backend usará a
                  configuração vigente do agente.
                </p>
              </div>
              <FieldGroup className="grid gap-5 md:grid-cols-4">
                <Field>
                  <FieldLabel>Mensalidade</FieldLabel>
                  <FieldContent>
                    <InputCurrency
                      value={state.mensalidade}
                      onChange={(value) =>
                        setState((current) => ({
                          ...current,
                          mensalidade: value,
                        }))
                      }
                    />
                  </FieldContent>
                </Field>
                <Field>
                  <FieldLabel>Data da aprovação</FieldLabel>
                  <FieldContent>
                    <DatePicker
                      value={state.dataAprovacao}
                      onChange={(value) =>
                        setState((current) => ({
                          ...current,
                          dataAprovacao: value,
                        }))
                      }
                    />
                  </FieldContent>
                </Field>
                <Field>
                  <FieldLabel>Agente responsável</FieldLabel>
                  <FieldContent>
                    <Select
                      value={state.agenteResponsavelId}
                      onValueChange={(value) =>
                        setState((current) => ({
                          ...current,
                          agenteResponsavelId: value,
                        }))
                      }
                    >
                      <SelectTrigger className="rounded-xl bg-card/60">
                        <SelectValue
                          placeholder={
                            agentesQuery.isLoading
                              ? "Carregando agentes..."
                              : "Selecione o agente"
                          }
                        />
                      </SelectTrigger>
                      <SelectContent>
                        {agenteOptions.map((agente) => (
                          <SelectItem key={agente.id} value={String(agente.id)}>
                            {agente.full_name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </FieldContent>
                </Field>
                <Field>
                  <FieldLabel>Repasse manual (%)</FieldLabel>
                  <FieldContent>
                    <Input
                      type="number"
                      min="0"
                      step="0.01"
                      value={state.percentualRepasse}
                      placeholder="Usar configuração do agente"
                      onChange={(event) =>
                        setState((current) => ({
                          ...current,
                          percentualRepasse: event.target.value,
                        }))
                      }
                      className="rounded-xl bg-card/60"
                    />
                  </FieldContent>
                </Field>
                <Field>
                  <FieldLabel>Disponível</FieldLabel>
                  <FieldContent>
                    <Input
                      readOnly
                      value={formatCurrency(preview.margemDisponivel / 100)}
                      className="rounded-xl bg-card/60"
                    />
                  </FieldContent>
                </Field>
                <Field>
                  <FieldLabel>Total antecipação</FieldLabel>
                  <FieldContent>
                    <Input
                      readOnly
                      value={formatCurrency(preview.valorTotalAntecipacao / 100)}
                      className="rounded-xl bg-card/60"
                    />
                  </FieldContent>
                </Field>
                <Field>
                  <FieldLabel>Doação do associado</FieldLabel>
                  <FieldContent>
                    <Input
                      readOnly
                      value={formatCurrency(preview.doacaoAssociado / 100)}
                      className="rounded-xl bg-card/60"
                    />
                  </FieldContent>
                </Field>
                <Field>
                  <FieldLabel>Comissão do agente</FieldLabel>
                  <FieldContent>
                    <Input
                      readOnly
                      value={formatCurrency(preview.comissaoAgente / 100)}
                      className="rounded-xl bg-card/60"
                    />
                  </FieldContent>
                </Field>
                <Field>
                  <FieldLabel>Primeira mensalidade</FieldLabel>
                  <FieldContent>
                    <Input
                      readOnly
                      value={
                        preview.contratoDates.dataPrimeiraMensalidade
                          ? preview.contratoDates.dataPrimeiraMensalidade
                              .toISOString()
                              .slice(0, 10)
                          : ""
                      }
                      className="rounded-xl bg-card/60"
                    />
                  </FieldContent>
                </Field>
                <Field>
                  <FieldLabel>Mês de averbação</FieldLabel>
                  <FieldContent>
                    <Input
                      readOnly
                      value={formatLongMonthYear(preview.contratoDates.mesAverbacao)}
                      className="rounded-xl bg-card/60"
                    />
                  </FieldContent>
                </Field>
              </FieldGroup>
            </section>

            <section className="rounded-[1.5rem] border border-border/60 bg-card/50 p-5">
              <div className="mb-4">
                <h3 className="text-base font-semibold">Anexos atualizados</h3>
                <p className="text-sm text-muted-foreground">
                  Os arquivos enviados aqui substituem os anexos atuais do
                  associado para a nova reativação.
                </p>
              </div>
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                {DOCUMENT_FIELDS.map((field) => (
                  <div
                    key={field.key}
                    className="space-y-3 rounded-3xl border border-border/60 bg-background/40 p-4"
                  >
                    <p className="text-sm font-medium">{field.label}</p>
                    {renderCurrentDocument(currentDocumentsByType.get(field.key))}
                    <FileUploadDropzone
                      accept={DOCUMENT_ACCEPT}
                      maxSize={100 * 1024 * 1024}
                      file={documents[field.key] ?? null}
                      onUpload={(file) => updateDocument(field.key, file)}
                      emptyTitle="Selecionar novo arquivo"
                      emptyDescription="PDF, JPG ou PNG até 100 MB"
                    />
                  </div>
                ))}
              </div>
            </section>
          </div>

          <DialogFooter className="border-t border-border/60 px-6 py-4">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={reactivationMutation.isPending}
            >
              Cancelar
            </Button>
            <Button
              type="button"
              onClick={() => reactivationMutation.mutate()}
              disabled={reactivationMutation.isPending}
            >
              {reactivationMutation.isPending ? (
                <>
                  <LoaderCircleIcon className="size-4 animate-spin" />
                  Enviando para tesouraria
                </>
              ) : (
                "Enviar reativação"
              )}
            </Button>
          </DialogFooter>
        </div>
      </DialogContent>
    </Dialog>
  );
}
