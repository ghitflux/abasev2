"use client";

import { useQuery } from "@tanstack/react-query";

import type { AssociadoDetail } from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import AssociadoForm from "@/components/associados/associado-form";
import { FormRouteSkeleton } from "@/components/shared/page-skeletons";

type EditarAssociadoPageClientProps = {
  associadoId: number;
  adminMode?: boolean;
};

export default function EditarAssociadoPageClient({
  associadoId,
  adminMode = false,
}: EditarAssociadoPageClientProps) {
  const associadoQuery = useQuery({
    queryKey: ["associado", associadoId],
    queryFn: () => apiFetch<AssociadoDetail>(`associados/${associadoId}`),
    enabled: Number.isFinite(associadoId) && associadoId > 0,
  });

  if (associadoQuery.isLoading) {
    return <FormRouteSkeleton />;
  }

  return (
    <AssociadoForm
      mode="edit"
      associadoId={associadoId}
      initialData={associadoQuery.data}
      cancelHref={adminMode ? `/associados/${associadoId}?admin=1` : `/associados/${associadoId}`}
      successHref={(associado) =>
        adminMode ? `/associados/${associado.id}?admin=1` : `/associados/${associado.id}`
      }
      title={adminMode ? "Salvar cadastro do associado" : undefined}
      description={
        adminMode
          ? "Revise e salve os dados cadastrais. Ao concluir, o sistema volta para o detalhe do associado com o modo admin ativo."
          : undefined
      }
      submitLabel={adminMode ? "Salvar cadastro" : undefined}
    />
  );
}
