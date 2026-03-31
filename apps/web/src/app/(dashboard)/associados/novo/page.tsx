"use client";

import RoleGuard from "@/components/auth/role-guard";
import AssociadoForm from "@/components/associados/associado-form";

export default function NovoAssociadoPage() {
  return (
    <RoleGuard allow={["ADMIN", "COORDENADOR", "ANALISTA"]}>
      <AssociadoForm mode="create" />
    </RoleGuard>
  );
}
