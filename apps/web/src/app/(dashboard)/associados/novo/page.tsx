import RoleGuard from "@/components/auth/role-guard";
import AssociadoForm from "@/components/associados/associado-form";

export default function NovoAssociadoPage() {
  return (
    <RoleGuard allow={["ADMIN"]}>
      <AssociadoForm mode="create" />
    </RoleGuard>
  );
}
