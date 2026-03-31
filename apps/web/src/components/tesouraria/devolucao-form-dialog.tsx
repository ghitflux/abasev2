"use client";

import * as React from "react";

import type {
  DevolucaoArquivo,
  DevolucaoContratoItem,
} from "@/lib/api/types";
import {
  formatCurrency,
  formatDate,
  formatMonthYear,
} from "@/lib/formatters";
import { buildBackendFileUrl } from "@/lib/backend-files";
import CalendarCompetencia from "@/components/custom/calendar-competencia";
import DatePicker from "@/components/custom/date-picker";
import FileUploadDropzone from "@/components/custom/file-upload-dropzone";
import InputCurrency from "@/components/custom/input-currency";
import SearchableSelect, {
  type SelectOption,
} from "@/components/custom/searchable-select";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

const comprovanteAccept = {
  "application/pdf": [".pdf"],
  "image/png": [".png"],
  "image/jpeg": [".jpg", ".jpeg"],
};

export type DevolucaoFormState = {
  mode: "create" | "edit";
  devolucaoId: number | null;
  row: DevolucaoContratoItem | null;
  tipo: "pagamento_indevido" | "desconto_indevido" | "desistencia_pos_liquidacao";
  dataDevolucao?: Date;
  quantidadeParcelas: number;
  valor: number | null;
  motivo: string;
  competenciaReferencia?: Date;
  comprovantePrincipal: File | null;
  comprovantesExtras: File[];
  existingComprovantePrincipal: DevolucaoArquivo | null;
  existingAnexosExtras: DevolucaoArquivo[];
  removerAnexosIds: number[];
};

type DevolucaoFormDialogProps = {
  open: boolean;
  value: DevolucaoFormState | null;
  setValue: React.Dispatch<React.SetStateAction<DevolucaoFormState | null>>;
  onClose: () => void;
  onSubmit: () => void;
  isSubmitting: boolean;
  allowContractSelection?: boolean;
  contractSearch: string;
  onContractSearchChange: (value: string) => void;
  contractOptions: DevolucaoContratoItem[];
  contractSearchLoading?: boolean;
};

function formatContractOption(row: DevolucaoContratoItem): SelectOption {
  return {
    value: String(row.contrato_id),
    label: `${row.nome} · ${row.contrato_codigo}`,
  };
}

export default function DevolucaoFormDialog({
  open,
  value,
  setValue,
  onClose,
  onSubmit,
  isSubmitting,
  allowContractSelection = false,
  contractSearch,
  onContractSearchChange,
  contractOptions,
  contractSearchLoading = false,
}: DevolucaoFormDialogProps) {
  const selectedContractId = value?.row ? String(value.row.contrato_id) : "";
  const selectedContract = value?.row ?? null;
  const contractSelectOptions = React.useMemo(
    () => contractOptions.map(formatContractOption),
    [contractOptions],
  );

  const canSubmit = Boolean(
    value?.row &&
      value.dataDevolucao &&
      value.valor &&
      value.motivo.trim() &&
      (value.tipo !== "desconto_indevido" || value.competenciaReferencia) &&
      (value.comprovantePrincipal ||
        value.existingComprovantePrincipal ||
        value.existingAnexosExtras.some(
          (anexo) => !value.removerAnexosIds.includes(anexo.id ?? -1),
        )),
  );

  return (
    <Dialog open={open} onOpenChange={(nextOpen) => !nextOpen && onClose()}>
      <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>
            {value?.mode === "edit" ? "Editar devolução" : "Registrar devolução"}
          </DialogTitle>
          <DialogDescription>
            {value?.mode === "edit"
              ? "A edição mantém o histórico da devolução e preserva os anexos existentes até você substituí-los ou removê-los."
              : value?.tipo === "desistencia_pos_liquidacao"
                ? "Use este fluxo quando a renovação já foi liquidada, houve pagamento e o associado desistiu depois."
                : "O registro é manual e não altera parcelas, ciclos ou pagamentos mensais do contrato."}
          </DialogDescription>
        </DialogHeader>

        {value ? (
          <div className="space-y-5">
            {allowContractSelection ? (
              <div className="grid gap-4 rounded-2xl border border-border/60 bg-background/40 p-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                <div className="space-y-2">
                  <Label htmlFor="devolucao-contract-search">Buscar contrato elegível</Label>
                  <Input
                    id="devolucao-contract-search"
                    value={contractSearch}
                    onChange={(event) => onContractSearchChange(event.target.value)}
                    placeholder="Nome, CPF, matrícula ou contrato"
                    className="h-11 rounded-xl border-border/60 bg-background/50"
                  />
                  <p className="text-xs text-muted-foreground">
                    {contractSearchLoading
                      ? "Buscando contratos elegíveis..."
                      : "Somente contratos passíveis de devolução aparecem na busca."}
                  </p>
                </div>
                <div className="space-y-2">
                  <Label>Contrato selecionado</Label>
                  <SearchableSelect
                    options={contractSelectOptions}
                    value={selectedContractId}
                    onChange={(nextValue) => {
                      const nextRow =
                        contractOptions.find(
                          (option) => String(option.contrato_id) === nextValue,
                        ) ?? null;
                      setValue((current) =>
                        current ? { ...current, row: nextRow } : current,
                      );
                    }}
                    placeholder="Selecione um contrato"
                    searchPlaceholder="Filtrar resultados"
                    emptyLabel="Nenhum contrato elegível encontrado."
                    className="rounded-xl border-border/60 bg-background/50"
                  />
                </div>
              </div>
            ) : null}

            {selectedContract ? (
              <div className="grid gap-4 rounded-2xl border border-border/60 bg-background/40 p-4 md:grid-cols-2">
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
                    Associado
                  </p>
                  <p className="mt-2 text-sm font-medium">{selectedContract.nome}</p>
                  <p className="text-xs text-muted-foreground">
                    {selectedContract.cpf_cnpj} ·{" "}
                    {selectedContract.matricula || "Sem matrícula"}
                  </p>
                </div>
                <div>
                  <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
                    Contrato / Agente
                  </p>
                  <p className="mt-2 text-sm font-medium">
                    {selectedContract.contrato_codigo}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {selectedContract.agente_nome || "Sem agente responsável"}
                  </p>
                </div>
              </div>
            ) : (
              <div className="rounded-2xl border border-dashed border-border/60 bg-background/30 px-4 py-6 text-sm text-muted-foreground">
                Selecione um contrato elegível para continuar o lançamento manual.
              </div>
            )}

            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <Label>Tipo</Label>
                <Select
                  value={value.tipo}
                  onValueChange={(nextValue) =>
                    setValue((current) =>
                      current
                        ? {
                            ...current,
                            tipo: nextValue as DevolucaoFormState["tipo"],
                          }
                        : current,
                    )
                  }
                  disabled={selectedContract?.tipo_sugerido === "desistencia_pos_liquidacao"}
                >
                  <SelectTrigger className="h-11 rounded-xl border-border/60 bg-background/50">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="pagamento_indevido">Pagamento indevido</SelectItem>
                    <SelectItem value="desconto_indevido">Desconto indevido</SelectItem>
                    <SelectItem value="desistencia_pos_liquidacao">
                      Desistência pós-liquidação
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Data da devolução</Label>
                <DatePicker
                  value={value.dataDevolucao}
                  onChange={(date) =>
                    setValue((current) =>
                      current ? { ...current, dataDevolucao: date } : current,
                    )
                  }
                />
              </div>
              <div className="space-y-2">
                <Label>Valor</Label>
                <InputCurrency
                  value={value.valor}
                  onChange={(nextValue) =>
                    setValue((current) =>
                      current ? { ...current, valor: nextValue } : current,
                    )
                  }
                  className="h-11 rounded-xl border-border/60 bg-background/50"
                  placeholder="R$ 0,00"
                />
              </div>
              {value.tipo === "desconto_indevido" ? (
                <div className="space-y-2">
                  <div className="flex items-center justify-between gap-3">
                    <Label>Competência de referência</Label>
                    {value.competenciaReferencia ? (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-auto px-0 text-xs"
                        onClick={() =>
                          setValue((current) =>
                            current
                              ? { ...current, competenciaReferencia: undefined }
                              : current,
                          )
                        }
                      >
                        Limpar
                      </Button>
                    ) : null}
                  </div>
                  <CalendarCompetencia
                    value={value.competenciaReferencia}
                    onChange={(nextValue) =>
                      setValue((current) =>
                        current
                          ? { ...current, competenciaReferencia: nextValue }
                          : current,
                      )
                    }
                  />
                </div>
              ) : (
                <div className="space-y-2">
                  <Label>Competência de referência</Label>
                  <div className="rounded-xl border border-border/60 bg-background/40 px-4 py-3 text-sm text-muted-foreground">
                    Não se aplica ao fluxo selecionado.
                  </div>
                </div>
              )}
              <div className="space-y-2">
                <Label>Quantidade de parcelas</Label>
                <Input
                  type="number"
                  min={1}
                  step={1}
                  value={String(value.quantidadeParcelas)}
                  onChange={(event) =>
                    setValue((current) =>
                      current
                        ? {
                            ...current,
                            quantidadeParcelas: Math.max(
                              1,
                              Number.parseInt(event.target.value || "1", 10) || 1,
                            ),
                          }
                        : current,
                    )
                  }
                  className="h-11 rounded-xl border-border/60 bg-background/50"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label>Motivo</Label>
              <Textarea
                value={value.motivo}
                onChange={(event) =>
                  setValue((current) =>
                    current ? { ...current, motivo: event.target.value } : current,
                  )
                }
                placeholder="Descreva o motivo da devolução ao associado."
                className="min-h-[120px] rounded-2xl border-border/60 bg-background/50"
              />
            </div>

            <div className="space-y-4 rounded-2xl border border-border/60 bg-background/35 p-4">
              <div className="space-y-1">
                <h3 className="text-sm font-semibold text-foreground">
                  Comprovante principal
                </h3>
                <p className="text-sm text-muted-foreground">
                  {value.mode === "edit"
                    ? "Se enviar um novo arquivo principal, o comprovante principal atual será preservado como anexo complementar."
                    : "Envie o comprovante principal da devolução."}
                </p>
              </div>
              {value.existingComprovantePrincipal ? (
                <div className="rounded-xl border border-border/60 bg-card/60 p-3 text-sm">
                  <p className="font-medium">
                    Atual: {value.existingComprovantePrincipal.nome}
                  </p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Button asChild size="sm" variant="outline">
                      <a
                        href={buildBackendFileUrl(value.existingComprovantePrincipal.url)}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Ver arquivo atual
                      </a>
                    </Button>
                  </div>
                </div>
              ) : null}
              <FileUploadDropzone
                accept={comprovanteAccept}
                file={value.comprovantePrincipal}
                onUpload={(file) =>
                  setValue((current) =>
                    current ? { ...current, comprovantePrincipal: file } : current,
                  )
                }
                className="rounded-2xl"
                emptyTitle="Enviar comprovante principal"
                emptyDescription="PDF, JPG ou PNG com limite de 10 MB"
              />
            </div>

            <div className="space-y-4 rounded-2xl border border-border/60 bg-background/35 p-4">
              <div className="space-y-1">
                <h3 className="text-sm font-semibold text-foreground">
                  Anexos complementares
                </h3>
                <p className="text-sm text-muted-foreground">
                  Use anexos extras para adicionar comprovantes auxiliares, prints ou documentos de apoio.
                </p>
              </div>

              {value.existingAnexosExtras.length ? (
                <div className="space-y-3">
                  {value.existingAnexosExtras.map((anexo) => {
                    const markedForRemoval = value.removerAnexosIds.includes(anexo.id ?? -1);
                    return (
                      <div
                        key={`${anexo.id}-${anexo.nome}`}
                        className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border/60 bg-card/60 p-3 text-sm"
                      >
                        <div>
                          <p className="font-medium">{anexo.nome}</p>
                          <p className="text-xs text-muted-foreground">
                            {markedForRemoval ? "Será removido ao salvar." : "Anexo ativo."}
                          </p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <Button asChild size="sm" variant="outline">
                            <a
                              href={buildBackendFileUrl(anexo.url)}
                              target="_blank"
                              rel="noreferrer"
                            >
                              Ver anexo
                            </a>
                          </Button>
                          {anexo.id ? (
                            <Button
                              type="button"
                              size="sm"
                              variant={markedForRemoval ? "secondary" : "outline"}
                              onClick={() =>
                                setValue((current) => {
                                  if (!current || !anexo.id) return current;
                                  const removeIds = current.removerAnexosIds.includes(anexo.id)
                                    ? current.removerAnexosIds.filter((item) => item !== anexo.id)
                                    : [...current.removerAnexosIds, anexo.id];
                                  return { ...current, removerAnexosIds: removeIds };
                                })
                              }
                            >
                              {markedForRemoval ? "Manter" : "Remover"}
                            </Button>
                          ) : null}
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : null}

              <FileUploadDropzone
                accept={comprovanteAccept}
                files={value.comprovantesExtras}
                multiple
                onUploadMany={(files) =>
                  setValue((current) =>
                    current ? { ...current, comprovantesExtras: files } : current,
                  )
                }
                className="rounded-2xl"
                emptyTitle="Enviar anexos complementares"
                emptyDescription="Arquivos adicionais opcionais para complementar o registro"
              />
            </div>

            {selectedContract ? (
              <div className="rounded-2xl border border-border/60 bg-background/35 p-4 text-sm text-muted-foreground">
                <p>
                  Contrato em {formatDate(selectedContract.data_contrato)} · Averbação{" "}
                  {selectedContract.mes_averbacao
                    ? formatMonthYear(selectedContract.mes_averbacao)
                    : "não informada"}
                </p>
                {value.valor ? (
                  <p className="mt-1 font-medium text-foreground">
                    Valor informado: {formatCurrency((value.valor / 100).toFixed(2))}
                  </p>
                ) : null}
              </div>
            ) : null}
          </div>
        ) : null}

        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>
            Cancelar
          </Button>
          <Button
            variant="success"
            disabled={!canSubmit || isSubmitting}
            onClick={onSubmit}
          >
            {value?.mode === "edit" ? "Salvar devolução" : "Registrar devolução"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
