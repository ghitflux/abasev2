"use client";

import * as React from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import type { AdminAssociadoEditorPayload, AssociadoDetail } from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import AdminContractEditor from "@/components/associados/admin-contract-editor";
import AdminFileManager from "@/components/associados/admin-file-manager";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  associadoId: number | null;
  contractId: number | null;
  contractCode?: string;
  associadoNome?: string;
};

export default function RenovacaoAdminEditDialog({
  open,
  onOpenChange,
  associadoId,
  contractId,
  contractCode,
  associadoNome,
}: Props) {
  const queryClient = useQueryClient();
  const editorQuery = useQuery({
    queryKey: ["admin-associado-editor", associadoId],
    queryFn: () =>
      apiFetch<AdminAssociadoEditorPayload>(`admin-overrides/associados/${associadoId}/editor/`),
    enabled: open && associadoId != null,
  });
  const associadoQuery = useQuery({
    queryKey: ["associado", associadoId],
    queryFn: () => apiFetch<AssociadoDetail>(`associados/${associadoId}`),
    enabled: open && associadoId != null,
  });

  const selectedContract = React.useMemo(
    () => editorQuery.data?.contratos.find((item) => item.id === contractId) ?? null,
    [contractId, editorQuery.data?.contratos],
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="grid max-h-[calc(100vh-2rem)] w-[96vw] max-w-[96vw] grid-rows-[auto_minmax(0,1fr)] overflow-hidden border-border/60 bg-background/95 p-5 sm:p-6 xl:max-w-[92vw] 2xl:max-w-[120rem]">
        <DialogHeader className="shrink-0">
          <DialogTitle>
            Reeditar renovação {contractCode ? `· ${contractCode}` : ""}
          </DialogTitle>
          <DialogDescription>
            Ajuste status, valores e comprovantes da renovação lançada para{" "}
            {associadoNome || "o associado selecionado"}.
          </DialogDescription>
        </DialogHeader>

        <div className="min-h-0 overflow-y-auto pr-1">
          {editorQuery.isLoading || associadoQuery.isLoading ? (
            <div className="space-y-4">
              <div className="h-32 animate-pulse rounded-[1.5rem] bg-card/60" />
              <div className="h-72 animate-pulse rounded-[1.5rem] bg-card/60" />
            </div>
          ) : editorQuery.isError || associadoQuery.isError ? (
            <div className="rounded-[1.5rem] border border-destructive/40 bg-destructive/10 px-5 py-4 text-sm text-destructive">
              {(editorQuery.error instanceof Error && editorQuery.error.message) ||
                (associadoQuery.error instanceof Error && associadoQuery.error.message) ||
                "Falha ao carregar o editor administrativo da renovação."}
            </div>
          ) : selectedContract && associadoId && associadoQuery.data ? (
            <div className="space-y-5">
              <AdminContractEditor
                associadoId={associadoId}
                contract={selectedContract}
                onPayloadRefresh={async (payload) => {
                  if (payload) {
                    queryClient.setQueryData(["admin-associado-editor", associadoId], payload);
                  } else {
                    await editorQuery.refetch();
                  }
                  await Promise.all([
                    associadoQuery.refetch(),
                    queryClient.invalidateQueries({ queryKey: ["renovacao-ciclos"] }),
                  ]);
                }}
              />
              <AdminFileManager associadoId={associadoId} associado={associadoQuery.data} />
            </div>
          ) : (
            <div className="rounded-[1.5rem] border border-border/60 bg-card/60 px-5 py-4 text-sm text-muted-foreground">
              O contrato de referência da renovação não foi encontrado no editor administrativo.
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
