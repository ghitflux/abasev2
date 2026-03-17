"use client";

import RoleGuard from "@/components/auth/role-guard";
import AssociadoForm from "@/components/associados/associado-form";

export default function CadastrarAssociadoAgentePage() {
  return (
    <RoleGuard allow={["AGENTE"]}>
      <AssociadoForm
        mode="create"
        cancelHref="/agentes/meus-contratos"
        successHref={(associado) => `/associados/${associado.id}`}
      />
    </RoleGuard>
  );
}
