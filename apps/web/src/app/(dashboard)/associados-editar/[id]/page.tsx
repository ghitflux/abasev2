import RoleGuard from "@/components/auth/role-guard";
import EditarAssociadoPageClient from "@/components/associados/editar-associado-page-client";

type EditarAssociadoPageProps = {
  params: Promise<{ id: string }>;
  searchParams?: Promise<{ admin?: string }>;
};

export default async function EditarAssociadoPage({
  params,
  searchParams,
}: EditarAssociadoPageProps) {
  const { id } = await params;
  const resolvedSearchParams = searchParams ? await searchParams : undefined;
  const associadoId = Number(id);
  const adminMode = resolvedSearchParams?.admin === "1";

  return (
    <RoleGuard allow={["ADMIN"]}>
      <EditarAssociadoPageClient associadoId={associadoId} adminMode={adminMode} />
    </RoleGuard>
  );
}
