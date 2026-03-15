"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";

import type { AssociadoDetail } from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import RoleGuard from "@/components/auth/role-guard";
import AssociadoForm from "@/components/associados/associado-form";
import { FormRouteSkeleton } from "@/components/shared/page-skeletons";

type EditarAssociadoPageProps = {
  params: Promise<{ id: string }>;
};

function EditarAssociadoPageContent({ params }: EditarAssociadoPageProps) {
  const { id } = React.use(params);
  const associadoId = Number(id);

  const associadoQuery = useQuery({
    queryKey: ["associado", associadoId],
    queryFn: () => apiFetch<AssociadoDetail>(`associados/${associadoId}`),
  });

  if (associadoQuery.isLoading) {
    return <FormRouteSkeleton />;
  }

  return <AssociadoForm mode="edit" associadoId={associadoId} initialData={associadoQuery.data} />;
}

export default function EditarAssociadoPage(props: EditarAssociadoPageProps) {
  return (
    <RoleGuard allow={["ADMIN"]}>
      <EditarAssociadoPageContent {...props} />
    </RoleGuard>
  );
}
