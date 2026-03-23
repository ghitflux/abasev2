"use client";

import * as React from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { PencilIcon } from "lucide-react";
import { toast } from "sonner";

import type { AssociadoDetail, ComprovanteCiclo, Documento } from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import { formatMonthYear } from "@/lib/formatters";
import { buildBackendFileUrl } from "@/lib/backend-files";
import StatusBadge from "@/components/custom/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import AdminFileVersionDialog from "@/components/associados/admin-file-version-dialog";

type Props = {
  associadoId: number;
  associado: AssociadoDetail;
};

type PendingTarget =
  | {
      kind: "documento";
      id: number;
      title: string;
      description?: string;
      currentStatus?: string | null;
      currentReference?: string | null;
    }
  | {
      kind: "comprovante";
      id: number;
      title: string;
      description?: string;
      currentStatus?: string | null;
      currentReference?: string | null;
    };

function openFile(url?: string | null) {
  if (!url) {
    return;
  }
  window.open(buildBackendFileUrl(url), "_blank", "noopener,noreferrer");
}

export default function AdminFileManager({ associadoId, associado }: Props) {
  const [pendingTarget, setPendingTarget] = React.useState<PendingTarget | null>(null);
  const queryClient = useQueryClient();

  const refresh = React.useCallback(async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["associado", associadoId] }),
      queryClient.invalidateQueries({ queryKey: ["admin-associado-editor", associadoId] }),
      queryClient.invalidateQueries({ queryKey: ["admin-associado-history", associadoId] }),
    ]);
  }, [associadoId, queryClient]);

  const mutation = useMutation({
    mutationFn: async (payload: {
      target: PendingTarget;
      motivo: string;
      status?: string;
      status_validacao?: string;
      file?: File | null;
    }) => {
      const formData = new FormData();
      formData.append("motivo", payload.motivo);
      if (payload.file) {
        formData.append("arquivo", payload.file);
      }
      if (payload.target.kind === "documento" && payload.status) {
        formData.append("status", payload.status);
      }
      if (payload.target.kind === "comprovante" && payload.status_validacao) {
        formData.append("status_validacao", payload.status_validacao);
      }
      const endpoint =
        payload.target.kind === "documento"
          ? `admin-overrides/documentos/${payload.target.id}/versionar/`
          : `admin-overrides/comprovantes/${payload.target.id}/versionar/`;
      return apiFetch(endpoint, {
        method: "POST",
        formData,
      });
    },
    onSuccess: async () => {
      toast.success("Versão atualizada.");
      await refresh();
      setPendingTarget(null);
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Falha ao versionar o arquivo.");
    },
  });

  const comprovantes: Array<ComprovanteCiclo & { cycleLabel: string }> = associado.contratos.flatMap(
    (contrato) =>
      contrato.ciclos.flatMap((ciclo) => {
        const arquivos: Array<ComprovanteCiclo & { cycleLabel: string }> = [];
        if (ciclo.termo_antecipacao?.id) {
          arquivos.push({
            ...ciclo.termo_antecipacao,
            cycleLabel: `${contrato.codigo} · Ciclo ${ciclo.numero}`,
          });
        }
        ciclo.comprovantes_ciclo.forEach((arquivo) => {
          if (arquivo.id) {
            arquivos.push({
              ...arquivo,
              cycleLabel: `${contrato.codigo} · Ciclo ${ciclo.numero}`,
            });
          }
        });
        return arquivos;
      }),
  );

  return (
    <div className="space-y-4">
      <Card className="rounded-[1.5rem] border-border/60 bg-card/60">
        <CardHeader>
          <CardTitle className="text-base">Documentos do associado</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 xl:grid-cols-2">
          {associado.documentos.length ? (
            associado.documentos.map((documento: Documento) => (
              <div
                key={documento.id}
                className="rounded-2xl border border-border/60 bg-background/60 p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-medium capitalize">{documento.tipo.replaceAll("_", " ")}</p>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {documento.nome_original || documento.arquivo_referencia || "Sem arquivo"}
                    </p>
                  </div>
                  <StatusBadge status={documento.status} />
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  {documento.arquivo ? (
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => openFile(documento.arquivo)}
                    >
                      Abrir
                    </Button>
                  ) : null}
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      setPendingTarget({
                        kind: "documento",
                        id: documento.id,
                        title: `Versionar ${documento.tipo.replaceAll("_", " ")}`,
                        currentStatus: documento.status,
                        currentReference: documento.nome_original || documento.arquivo_referencia,
                      })
                    }
                  >
                    <PencilIcon className="mr-2 size-4" />
                    Versionar
                  </Button>
                </div>
              </div>
            ))
          ) : (
            <p className="text-sm text-muted-foreground">Nenhum documento disponível.</p>
          )}
        </CardContent>
      </Card>

      <Card className="rounded-[1.5rem] border-border/60 bg-card/60">
        <CardHeader>
          <CardTitle className="text-base">Comprovantes e termos</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 xl:grid-cols-2">
          {comprovantes.length ? (
            comprovantes.map((arquivo) => (
              <div
                key={`${arquivo.id}-${arquivo.cycleLabel}`}
                className="rounded-2xl border border-border/60 bg-background/60 p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-medium capitalize">{arquivo.tipo.replaceAll("_", " ")}</p>
                    <p className="mt-1 text-sm text-muted-foreground">{arquivo.cycleLabel}</p>
                    <p className="text-sm text-muted-foreground">
                      {arquivo.nome_original || arquivo.arquivo_referencia}
                    </p>
                  </div>
                  <StatusBadge
                    status={arquivo.status_validacao || "pendente"}
                    label={arquivo.status_validacao?.replaceAll("_", " ")}
                  />
                </div>
                <div className="mt-4 flex flex-wrap gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => openFile(arquivo.arquivo)}
                  >
                    Abrir
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      setPendingTarget({
                        kind: "comprovante",
                        id: arquivo.id ?? 0,
                        title: `Versionar ${arquivo.tipo.replaceAll("_", " ")}`,
                        description: arquivo.cycleLabel,
                        currentStatus: arquivo.status_validacao || "pendente",
                        currentReference: arquivo.nome_original || arquivo.arquivo_referencia,
                      })
                    }
                  >
                    <PencilIcon className="mr-2 size-4" />
                    Versionar
                  </Button>
                </div>
              </div>
            ))
          ) : (
            <p className="text-sm text-muted-foreground">
              Nenhum comprovante versionável disponível nos ciclos atuais.
            </p>
          )}
        </CardContent>
      </Card>

      <AdminFileVersionDialog
        open={Boolean(pendingTarget)}
        onOpenChange={(open) => {
          if (!open) {
            setPendingTarget(null);
          }
        }}
        target={pendingTarget}
        isSubmitting={mutation.isPending}
        onSubmit={async ({ motivo, status, status_validacao, file }) => {
          if (!pendingTarget) {
            return;
          }
          await mutation.mutateAsync({
            target: pendingTarget,
            motivo,
            status,
            status_validacao,
            file,
          });
        }}
      />
    </div>
  );
}
