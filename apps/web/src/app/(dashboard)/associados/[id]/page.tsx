"use client";

import * as React from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircleIcon,
  Building2Icon,
  CreditCardIcon,
  FileTextIcon,
  LoaderCircleIcon,
  MapPinIcon,
  SaveIcon,
  ShieldCheckIcon,
  SmartphoneIcon,
  UserIcon,
  WorkflowIcon,
} from "lucide-react";
import { toast } from "sonner";

import type {
  AdminAssociadoEditorPayload,
  AdminEditorWarning,
  AdminOverrideHistoryEvent,
  AssociadoDetail,
} from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import {
  AssociadoContractsOverview,
  AssociadoDocumentsGrid,
} from "@/components/associados/associado-contracts-overview";
import CadastroOrigemBadge from "@/components/associados/cadastro-origem-badge";
import AdminContractEditor from "@/components/associados/admin-contract-editor";
import type {
  AdminContractEditorHandle,
  AdminContractEditorPendingChanges,
  ContractEditorDirtyState,
} from "@/components/associados/admin-contract-editor";
import AdminOverrideConfirmDialog from "@/components/associados/admin-override-confirm-dialog";
import AdminEsteiraEditor from "@/components/associados/admin-esteira-editor";
import type { AdminEsteiraEditorHandle } from "@/components/associados/admin-esteira-editor";
import { formatDate } from "@/lib/formatters";
import { dashboardRetainedQueryOptions } from "@/lib/dashboard-query";
import { usePermissions } from "@/hooks/use-permissions";
import RoleGuard from "@/components/auth/role-guard";
import {
  ParcelaDetalheDialog,
  type ParcelaDetailTarget,
} from "@/components/contratos/parcela-detalhe-dialog";
import { DetailRouteSkeleton } from "@/components/shared/page-skeletons";
import StatusBadge from "@/components/custom/status-badge";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";

const AdminFileManager = dynamic(
  () => import("@/components/associados/admin-file-manager"),
);
const AdminOverrideHistory = dynamic(
  () => import("@/components/associados/admin-override-history"),
);

const DEFAULT_OPEN_SECTIONS = ["contato", "contratos"];
const ADMIN_EDITOR_SECTIONS = [
  "contratos",
  "documentos",
  "esteira",
  "historico-admin",
];

type AssociadoPageProps = {
  params: Promise<{ id: string }>;
};

function hasDirtyContractState(state?: ContractEditorDirtyState) {
  return Boolean(state?.core || state?.cycles || state?.refinanciamento);
}

function isSameDirtyContractState(
  previous: ContractEditorDirtyState | undefined,
  next: ContractEditorDirtyState,
) {
  return (
    previous?.core === next.core &&
    previous?.cycles === next.cycles &&
    previous?.refinanciamento === next.refinanciamento
  );
}

function formatAdminWarnings(warnings: AdminEditorWarning[]) {
  return warnings
    .slice(0, 3)
    .map((warning) => warning.message)
    .join(" ");
}

function mergeAccordionSections(
  current: string[],
  sections: readonly string[],
) {
  const next = new Set(current);
  sections.forEach((section) => next.add(section));
  return Array.from(next);
}

function collectLocalCycleWarnings(
  contratos: AdminContractEditorPendingChanges[],
): AdminEditorWarning[] {
  const warnings: AdminEditorWarning[] = [];

  contratos.forEach((contrato) => {
    const cyclesPayload = contrato.cycles;
    if (!cyclesPayload) {
      return;
    }

    const normalizedCycles = cyclesPayload.cycles
      .map((cycle) => ({
        numero: cycle.numero,
        data_inicio: new Date(`${cycle.data_inicio}T12:00:00`),
        data_fim: new Date(`${cycle.data_fim}T12:00:00`),
      }))
      .sort(
        (left, right) =>
          left.data_inicio.getTime() - right.data_inicio.getTime(),
      );

    normalizedCycles.forEach((left, index) => {
      normalizedCycles.slice(index + 1).forEach((right) => {
        if (right.data_inicio.getTime() > left.data_fim.getTime()) {
          return;
        }
        if (left.data_inicio.getTime() <= right.data_fim.getTime()) {
          warnings.push({
            code: "cycle_date_overlap",
            severity: "warning",
            contrato_id: contrato.id,
            contrato_codigo: "",
            message: `Ciclos ${left.numero} e ${right.numero} possuem datas sobrepostas.`,
            details: {
              cycle_numbers: [left.numero, right.numero],
            },
          });
        }
      });
    });

    const references = new Map<
      string,
      Array<{ numero: number; cycle_ref: string }>
    >();
    cyclesPayload.parcelas.forEach((parcela) => {
      const current = references.get(parcela.referencia_mes) ?? [];
      current.push({
        numero: parcela.numero,
        cycle_ref: parcela.cycle_ref,
      });
      references.set(parcela.referencia_mes, current);
    });

    references.forEach((parcelas, referencia_mes) => {
      if (parcelas.length < 2) {
        return;
      }
      warnings.push({
        code: "duplicate_reference_month",
        severity: "warning",
        contrato_id: contrato.id,
        contrato_codigo: "",
        message: `A competência ${referencia_mes.slice(5, 7)}/${referencia_mes.slice(0, 4)} aparece em mais de uma parcela.`,
        details: {
          referencia_mes,
          parcelas,
        },
      });
    });
  });

  return warnings.filter(
    (warning, index, collection) =>
      collection.findIndex(
        (candidate) =>
          candidate.code === warning.code &&
          candidate.message === warning.message,
      ) === index,
  );
}

function AssociadoPageContent({ params }: AssociadoPageProps) {
  const { id } = React.use(params);
  const associadoId = Number(id);
  const router = useRouter();
  const searchParams = useSearchParams();
  const adminQueryParam = searchParams.get("admin");
  const [selectedTarget, setSelectedTarget] =
    React.useState<ParcelaDetailTarget | null>(null);
  const [adminMode, setAdminMode] = React.useState(false);
  const [openSections, setOpenSections] = React.useState<string[]>(
    DEFAULT_OPEN_SECTIONS,
  );
  const [inativarDialogOpen, setInativarDialogOpen] = React.useState(false);
  const [saveAllOpen, setSaveAllOpen] = React.useState(false);
  const contractEditorRefs = React.useRef<
    Record<number, AdminContractEditorHandle | null>
  >({});
  const esteiraEditorRef = React.useRef<AdminEsteiraEditorHandle | null>(null);
  const [contractDirtyState, setContractDirtyState] = React.useState<
    Record<number, ContractEditorDirtyState>
  >({});
  const [esteiraDirty, setEsteiraDirty] = React.useState(false);
  const autoAdminEnabledRef = React.useRef(false);
  const { hasRole } = usePermissions();
  const queryClient = useQueryClient();
  const isAdmin = hasRole("ADMIN");
  const isAnalyst = hasRole("ANALISTA") && !isAdmin;
  const isCoordinator = hasRole("COORDENADOR") && !isAdmin;
  const isAgent = hasRole("AGENTE") && !isAdmin;
  const isTreasurer = hasRole("TESOUREIRO") && !isAdmin;
  const canUseAdminEditor = isAdmin || isCoordinator;
  const backHref = isAdmin
    ? "/associados"
    : isCoordinator
      ? "/associados"
      : isAnalyst
        ? "/analise"
        : isTreasurer
          ? "/tesouraria"
          : "/agentes/meus-contratos";

  const associadoQuery = useQuery({
    queryKey: ["associado", associadoId],
    queryFn: () => apiFetch<AssociadoDetail>(`associados/${associadoId}`),
    ...dashboardRetainedQueryOptions,
  });

  const adminEditorQuery = useQuery({
    queryKey: ["admin-associado-editor", associadoId],
    queryFn: () =>
      apiFetch<AdminAssociadoEditorPayload>(
        `admin-overrides/associados/${associadoId}/editor/`,
      ),
    enabled: canUseAdminEditor && adminMode,
    ...dashboardRetainedQueryOptions,
  });

  const adminHistoryQuery = useQuery({
    queryKey: ["admin-associado-history", associadoId],
    queryFn: () =>
      apiFetch<AdminOverrideHistoryEvent[]>(
        `admin-overrides/associados/${associadoId}/history/`,
      ),
    enabled: canUseAdminEditor && adminMode,
    ...dashboardRetainedQueryOptions,
  });

  const inativarAssociadoMutation = useMutation({
    mutationFn: async () =>
      apiFetch<AssociadoDetail>(`associados/${associadoId}/inativar`, {
        method: "POST",
      }),
    onSuccess: async (payload) => {
      toast.success("Associado inativado com sucesso.");
      setInativarDialogOpen(false);
      queryClient.setQueryData(["associado", associadoId], payload);
      await queryClient.invalidateQueries({ queryKey: ["associados"] });
      await queryClient.invalidateQueries({ queryKey: ["contratos"] });
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : "Falha ao inativar associado.",
      );
    },
  });

  React.useEffect(() => {
    if (!canUseAdminEditor || autoAdminEnabledRef.current || adminMode) {
      return;
    }
    if (adminQueryParam === "1") {
      setAdminMode(true);
      autoAdminEnabledRef.current = true;
    }
  }, [adminMode, adminQueryParam, canUseAdminEditor]);

  React.useEffect(() => {
    if (!adminMode) {
      setContractDirtyState({});
      setEsteiraDirty(false);
    }
  }, [adminMode]);

  React.useEffect(() => {
    if (adminMode) {
      setOpenSections((current) =>
        mergeAccordionSections(current, ADMIN_EDITOR_SECTIONS),
      );
      return;
    }

    setOpenSections((current) =>
      current.filter((section) => section !== "historico-admin"),
    );
  }, [adminMode]);

  const handleAdminModeChange = React.useCallback(
    (checked: boolean) => {
      const next = Boolean(checked);
      setAdminMode((current) => (current === next ? current : next));

      const nextSearchParams = new URLSearchParams(searchParams.toString());
      if (next) {
        nextSearchParams.set("admin", "1");
      } else {
        nextSearchParams.delete("admin");
      }

      const queryString = nextSearchParams.toString();
      const href = queryString
        ? `/associados/${associadoId}?${queryString}`
        : `/associados/${associadoId}`;

      React.startTransition(() => {
        router.replace(href, { scroll: false });
      });
    },
    [associadoId, router, searchParams],
  );

  const handleContractDirtyChange = React.useCallback(
    (contractId: number, state: ContractEditorDirtyState) => {
      setContractDirtyState((current) => {
        if (isSameDirtyContractState(current[contractId], state)) {
          return current;
        }
        return {
          ...current,
          [contractId]: state,
        };
      });
    },
    [],
  );

  const handleEsteiraDirtyChange = React.useCallback((dirty: boolean) => {
    setEsteiraDirty((current) => (current === dirty ? current : dirty));
  }, []);

  const handleAdminPayloadRefresh = React.useCallback(
    async (payload?: AdminAssociadoEditorPayload) => {
      if (payload) {
        queryClient.setQueryData(
          ["admin-associado-editor", associadoId],
          payload,
        );
      } else {
        await adminEditorQuery.refetch();
      }
      await Promise.all([
        associadoQuery.refetch(),
        adminHistoryQuery.refetch(),
      ]);
    },
    [
      adminEditorQuery,
      adminHistoryQuery,
      associadoId,
      associadoQuery,
      queryClient,
    ],
  );

  const hasUnsavedAdminChanges =
    canUseAdminEditor &&
    adminMode &&
    (Object.values(contractDirtyState).some(hasDirtyContractState) ||
      esteiraDirty);

  const adminEditorErrorMessage =
    adminEditorQuery.error instanceof Error
      ? adminEditorQuery.error.message
      : "Falha ao carregar o editor avançado.";
  const adminHistoryErrorMessage =
    adminHistoryQuery.error instanceof Error
      ? adminHistoryQuery.error.message
      : "Falha ao carregar o histórico do editor.";
  const isAdminEditorLoading =
    adminMode &&
    (adminEditorQuery.isLoading ||
      (adminEditorQuery.isFetching && !adminEditorQuery.data));
  const isAdminHistoryLoading =
    adminMode &&
    (adminHistoryQuery.isLoading ||
      (adminHistoryQuery.isFetching && !adminHistoryQuery.data));

  const collectPendingAdminChanges = React.useCallback(() => {
    const contratos = (adminEditorQuery.data?.contratos ?? [])
      .map(
        (contract) =>
          contractEditorRefs.current[contract.id]?.getPendingChanges() ?? null,
      )
      .filter((item): item is NonNullable<typeof item> => Boolean(item));
    const esteira = esteiraEditorRef.current?.getPendingChanges() ?? null;

    return {
      contratos,
      esteira,
    };
  }, [adminEditorQuery.data?.contratos]);

  const saveAllMutation = useMutation({
    mutationFn: async (motivo: string) => {
      const pending = collectPendingAdminChanges();
      if (!pending.contratos.length && !pending.esteira) {
        throw new Error("Nenhuma alteração pendente para salvar.");
      }
      const localWarnings = collectLocalCycleWarnings(pending.contratos);
      if (localWarnings.length) {
        const confirmed = window.confirm(
          [
            "Foram detectadas sobreposições ou duplicidades no layout.",
            "",
            ...localWarnings
              .slice(0, 5)
              .map((warning) => `- ${warning.message}`),
            "",
            "Deseja salvar mesmo assim?",
          ].join("\n"),
        );
        if (!confirmed) {
          throw new Error(
            "Salvamento cancelado para revisão das sobreposições.",
          );
        }
      }
      return apiFetch<AdminAssociadoEditorPayload>(
        `admin-overrides/associados/${associadoId}/save-all/`,
        {
          method: "POST",
          body: {
            motivo,
            contratos: pending.contratos,
            esteira: pending.esteira ?? undefined,
          },
        },
      );
    },
    onSuccess: async (payload) => {
      toast.success("Alterações do editor salvas.");
      if (payload.warnings?.length) {
        toast.warning(formatAdminWarnings(payload.warnings));
      }
      queryClient.setQueryData(
        ["admin-associado-editor", associadoId],
        payload,
      );
      setContractDirtyState({});
      setEsteiraDirty(false);
      void queryClient.invalidateQueries({ queryKey: ["tesouraria-baixa-manual"] });
      await Promise.all([
        associadoQuery.refetch(),
        adminHistoryQuery.refetch(),
      ]);
    },
    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : "Falha ao salvar alterações administrativas.",
      );
    },
  });

  React.useEffect(() => {
    if (!hasUnsavedAdminChanges) {
      return;
    }

    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };

    const handleClickCapture = (event: MouseEvent) => {
      if (
        event.defaultPrevented ||
        event.button !== 0 ||
        event.metaKey ||
        event.ctrlKey ||
        event.shiftKey ||
        event.altKey
      ) {
        return;
      }

      const target = event.target;
      if (!(target instanceof Element)) {
        return;
      }

      const anchor = target.closest("a[href]");
      if (!(anchor instanceof HTMLAnchorElement)) {
        return;
      }

      const href = anchor.getAttribute("href");
      if (!href || href.startsWith("#") || anchor.target === "_blank") {
        return;
      }

      const confirmed = window.confirm(
        "Existem alterações administrativas não salvas. Deseja sair sem salvar?",
      );
      if (!confirmed) {
        event.preventDefault();
        event.stopPropagation();
      }
    };

    window.addEventListener("beforeunload", handleBeforeUnload);
    document.addEventListener("click", handleClickCapture, true);

    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
      document.removeEventListener("click", handleClickCapture, true);
    };
  }, [hasUnsavedAdminChanges]);

  if (associadoQuery.isLoading) {
    return <DetailRouteSkeleton />;
  }

  const associado = associadoQuery.data;
  if (!associado) {
    return null;
  }

  return (
    <div className="space-y-6">
      <section className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.2em] text-muted-foreground">
            Associado
          </p>
          <h1 className="mt-2 text-3xl font-semibold">
            {associado.nome_completo}
          </h1>
          <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
            <span>{associado.matricula_display || associado.matricula}</span>
            <span>{associado.cpf_cnpj}</span>
            <CadastroOrigemBadge
              origem={associado.origem_cadastro_slug}
              label={associado.origem_cadastro_label}
            />
            <StatusBadge
              status={associado.status_visual_slug}
              label={associado.status_visual_label}
            />
            {(associado.mobile_sessions ?? []).some((s) => s.is_active) && (
              <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800 dark:bg-green-900/30 dark:text-green-400">
                <SmartphoneIcon className="h-3 w-3" />
                App ativo
              </span>
            )}
          </div>
        </div>
        <div className="flex flex-wrap gap-3">
          {canUseAdminEditor ? (
            <label className="inline-flex items-center gap-3 rounded-full border border-border/60 bg-card/60 px-4 py-2 text-sm">
              <Switch
                checked={adminMode}
                onCheckedChange={handleAdminModeChange}
              />
              Modo editor avançado
            </label>
          ) : null}
          <Button variant="outline" asChild>
            <Link href={backHref}>Voltar</Link>
          </Button>
          {(isAdmin || isCoordinator) && associado.status !== "inativo" ? (
            <Button
              variant="outline"
              className="border-amber-500/40 text-amber-200"
              onClick={() => setInativarDialogOpen(true)}
            >
              Inativar associado
            </Button>
          ) : null}
          {isAdmin ? (
            <Button variant="outline" asChild>
              <Link
                href={
                  adminMode
                    ? `/associados-editar/${associado.id}?admin=1`
                    : `/associados-editar/${associado.id}`
                }
              >
                Editar cadastro
              </Link>
            </Button>
          ) : null}
        </div>
      </section>

      {canUseAdminEditor && adminMode ? (
        <Alert
          variant={adminEditorQuery.isError ? "destructive" : "default"}
          className={
            adminEditorQuery.isError
              ? "border-destructive/40 bg-destructive/10"
              : "border-primary/30 bg-primary/5"
          }
        >
          {adminEditorQuery.isError ? (
            <AlertCircleIcon className="size-4" />
          ) : isAdminEditorLoading ? (
            <LoaderCircleIcon className="size-4 animate-spin" />
          ) : (
            <ShieldCheckIcon className="size-4 text-primary" />
          )}
          <AlertTitle>
            {adminEditorQuery.isError
              ? "Falha ao carregar o editor avançado"
              : isAdminEditorLoading
                ? "Carregando editor avançado"
                : "Editor avançado ativo"}
          </AlertTitle>
          <AlertDescription className="gap-3">
            {adminEditorQuery.isError ? (
              <>
                <p>{adminEditorErrorMessage}</p>
                <div className="flex flex-wrap gap-3">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      void adminEditorQuery.refetch();
                      void adminHistoryQuery.refetch();
                    }}
                  >
                    Tentar novamente
                  </Button>
                </div>
              </>
            ) : isAdminEditorLoading ? (
              <p>
                Preparando contrato, arquivos, esteira e histórico
                administrativo deste associado.
              </p>
            ) : (
              <>
                <p>
                  Use <strong>Editar cadastro</strong> para dados cadastrais e
                  os blocos abaixo para contrato, arquivos e esteira.
                </p>
                {adminEditorQuery.data?.warnings?.length ? (
                  <p>
                    {adminEditorQuery.data.warnings.length} warning(s)
                    operacional(is) detectado(s) no layout atual.
                  </p>
                ) : null}
              </>
            )}
          </AlertDescription>
        </Alert>
      ) : null}

      <Accordion
        type="multiple"
        value={openSections}
        onValueChange={setOpenSections}
        className="space-y-4"
      >
        {isAgent ? null : (
          <>
            <AccordionItem
              value="dados"
              className="rounded-[1.75rem] border border-border/60 bg-card/60 px-6"
            >
              <AccordionTrigger className="text-base">
                <span className="inline-flex items-center gap-2">
                  <UserIcon className="size-4 text-primary" />
                  Dados Pessoais
                </span>
              </AccordionTrigger>
              <AccordionContent>
                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                  <DetailItem
                    label="Tipo documento"
                    value={associado.tipo_documento}
                  />
                  <DetailItem label="CPF/CNPJ" value={associado.cpf_cnpj} />
                  <DetailItem label="RG" value={associado.rg} />
                  <DetailItem
                    label="Órgão expedidor"
                    value={associado.orgao_expedidor}
                  />
                  <DetailItem
                    label="Data de nascimento"
                    value={formatDate(associado.data_nascimento)}
                  />
                  <DetailItem label="Profissão" value={associado.profissao} />
                  <DetailItem
                    label="Estado civil"
                    value={associado.estado_civil}
                  />
                  <DetailItem
                    label="Agente"
                    value={associado.agente?.full_name}
                  />
                </div>
              </AccordionContent>
            </AccordionItem>

            <AccordionItem
              value="endereco"
              className="rounded-[1.75rem] border border-border/60 bg-card/60 px-6"
            >
              <AccordionTrigger className="text-base">
                <span className="inline-flex items-center gap-2">
                  <MapPinIcon className="size-4 text-primary" />
                  Endereço
                </span>
              </AccordionTrigger>
              <AccordionContent>
                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                  <DetailItem label="CEP" value={associado.endereco?.cep} />
                  <DetailItem
                    label="Endereço"
                    value={associado.endereco?.endereco}
                  />
                  <DetailItem
                    label="Número"
                    value={associado.endereco?.numero}
                  />
                  <DetailItem
                    label="Complemento"
                    value={associado.endereco?.complemento}
                  />
                  <DetailItem
                    label="Bairro"
                    value={associado.endereco?.bairro}
                  />
                  <DetailItem
                    label="Cidade"
                    value={associado.endereco?.cidade}
                  />
                  <DetailItem label="UF" value={associado.endereco?.uf} />
                </div>
              </AccordionContent>
            </AccordionItem>

            <AccordionItem
              value="banco"
              className="rounded-[1.75rem] border border-border/60 bg-card/60 px-6"
            >
              <AccordionTrigger className="text-base">
                <span className="inline-flex items-center gap-2">
                  <CreditCardIcon className="size-4 text-primary" />
                  Dados Bancários
                </span>
              </AccordionTrigger>
              <AccordionContent>
                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                  <DetailItem
                    label="Banco"
                    value={associado.dados_bancarios?.banco}
                  />
                  <DetailItem
                    label="Agência"
                    value={associado.dados_bancarios?.agencia}
                  />
                  <DetailItem
                    label="Conta"
                    value={associado.dados_bancarios?.conta}
                  />
                  <DetailItem
                    label="Tipo de conta"
                    value={associado.dados_bancarios?.tipo_conta}
                  />
                  <DetailItem
                    label="Chave PIX"
                    value={associado.dados_bancarios?.chave_pix}
                  />
                </div>
              </AccordionContent>
            </AccordionItem>
          </>
        )}

        <AccordionItem
          value="contato"
          className="rounded-[1.75rem] border border-border/60 bg-card/60 px-6"
        >
          <AccordionTrigger className="text-base">
            <span className="inline-flex items-center gap-2">
              <Building2Icon className="size-4 text-primary" />
              Contato e Vínculo
            </span>
          </AccordionTrigger>
          <AccordionContent>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <DetailItem label="Celular" value={associado.contato?.celular} />
              <DetailItem label="E-mail" value={associado.contato?.email} />
              <DetailItem
                label="Órgão público"
                value={associado.contato?.orgao_publico}
              />
              <DetailItem
                label="Situação do servidor"
                value={associado.contato?.situacao_servidor}
              />
              <DetailItem
                label="Matrícula do servidor"
                value={associado.contato?.matricula_servidor}
              />
            </div>
          </AccordionContent>
        </AccordionItem>

        <AccordionItem
          value="contratos"
          className="rounded-[1.75rem] border border-border/60 bg-card/60 px-6"
        >
          <AccordionTrigger className="text-base">
            <span className="inline-flex items-center gap-2">
              <FileTextIcon className="size-4 text-primary" />
              Contrato, Ciclos e Parcelas
            </span>
          </AccordionTrigger>
          <AccordionContent className="space-y-4">
            {canUseAdminEditor && adminMode && isAdminEditorLoading ? (
              <div className="space-y-4">
                <div className="h-32 animate-pulse rounded-[1.5rem] bg-background/60" />
                <div className="h-72 animate-pulse rounded-[1.5rem] bg-background/60" />
              </div>
            ) : null}
            {canUseAdminEditor && adminMode && adminEditorQuery.isError ? (
              <Alert
                variant="destructive"
                className="border-destructive/40 bg-destructive/10"
              >
                <AlertCircleIcon className="size-4" />
                <AlertTitle>Editor de contrato indisponível</AlertTitle>
                <AlertDescription className="gap-3">
                  <p>{adminEditorErrorMessage}</p>
                  <div className="flex flex-wrap gap-3">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        void adminEditorQuery.refetch();
                      }}
                    >
                      Recarregar editor
                    </Button>
                  </div>
                </AlertDescription>
              </Alert>
            ) : null}
            {canUseAdminEditor &&
            adminMode &&
            !isAdminEditorLoading &&
            !adminEditorQuery.isError &&
            adminEditorQuery.data?.contratos?.length ? (
              <div className="space-y-4">
                {adminEditorQuery.data.contratos.map((contract) => (
                  <AdminContractEditor
                    key={`admin-${contract.id}`}
                    ref={(instance) => {
                      contractEditorRefs.current[contract.id] = instance;
                    }}
                    associadoId={associadoId}
                    contract={contract}
                    onDirtyChange={(state) =>
                      handleContractDirtyChange(contract.id, state)
                    }
                    onPayloadRefresh={handleAdminPayloadRefresh}
                  />
                ))}
              </div>
            ) : null}
            {canUseAdminEditor &&
            adminMode &&
            !isAdminEditorLoading &&
            !adminEditorQuery.isError &&
            !adminEditorQuery.data?.contratos?.length ? (
              <Alert className="border-border/60 bg-background/60">
                <AlertCircleIcon className="size-4" />
                <AlertTitle>Nenhum contrato disponível no editor</AlertTitle>
                <AlertDescription>
                  <p>
                    Este associado não possui contrato operacional elegível para
                    override nesta tela.
                  </p>
                </AlertDescription>
              </Alert>
            ) : null}
            <AssociadoContractsOverview
              associado={associado}
              onParcelaClick={setSelectedTarget}
              showDocuments={false}
              agentRestricted={isAgent}
            />
          </AccordionContent>
        </AccordionItem>

        {isAgent ? null : (
          <AccordionItem
            value="documentos"
            className="rounded-[1.75rem] border border-border/60 bg-card/60 px-6"
          >
            <AccordionTrigger className="text-base">
              Documentos
            </AccordionTrigger>
            <AccordionContent>
              {canUseAdminEditor && adminMode && isAdminEditorLoading ? (
                <div className="mb-4 h-28 animate-pulse rounded-[1.5rem] bg-background/60" />
              ) : null}
              {canUseAdminEditor && adminMode && adminEditorQuery.isError ? (
                <Alert
                  variant="destructive"
                  className="mb-4 border-destructive/40 bg-destructive/10"
                >
                  <AlertCircleIcon className="size-4" />
                  <AlertTitle>Arquivos do editor indisponíveis</AlertTitle>
                  <AlertDescription>
                    <p>{adminEditorErrorMessage}</p>
                  </AlertDescription>
                </Alert>
              ) : null}
              {canUseAdminEditor &&
              adminMode &&
              !isAdminEditorLoading &&
              !adminEditorQuery.isError ? (
                <div className="mb-4">
                  <AdminFileManager
                    associadoId={associadoId}
                    associado={associado}
                  />
                </div>
              ) : null}
              <AssociadoDocumentsGrid associado={associado} />
            </AccordionContent>
          </AccordionItem>
        )}

        {isAgent ? null : (
          <AccordionItem
            value="esteira"
            className="rounded-[1.75rem] border border-border/60 bg-card/60 px-6"
          >
            <AccordionTrigger className="text-base">
              <span className="inline-flex items-center gap-2">
                <WorkflowIcon className="size-4 text-primary" />
                Histórico da Esteira
              </span>
            </AccordionTrigger>
            <AccordionContent className="space-y-4">
              {canUseAdminEditor && adminMode && isAdminEditorLoading ? (
                <div className="h-28 animate-pulse rounded-[1.5rem] bg-background/60" />
              ) : null}
              {canUseAdminEditor && adminMode && adminEditorQuery.isError ? (
                <Alert
                  variant="destructive"
                  className="border-destructive/40 bg-destructive/10"
                >
                  <AlertCircleIcon className="size-4" />
                  <AlertTitle>Editor de esteira indisponível</AlertTitle>
                  <AlertDescription>
                    <p>{adminEditorErrorMessage}</p>
                  </AlertDescription>
                </Alert>
              ) : null}
              {canUseAdminEditor &&
              adminMode &&
              !isAdminEditorLoading &&
              !adminEditorQuery.isError ? (
                <AdminEsteiraEditor
                  ref={esteiraEditorRef}
                  esteira={associado.esteira}
                  onDirtyChange={handleEsteiraDirtyChange}
                />
              ) : null}
              <div className="flex flex-wrap items-center gap-3">
                <StatusBadge
                  status={associado.esteira?.etapa_atual ?? "pendente"}
                />
                <StatusBadge
                  status={associado.esteira?.status ?? "aguardando"}
                />
              </div>
              <div className="space-y-3">
                {associado.esteira?.transicoes?.length ? (
                  associado.esteira.transicoes.map((transicao) => (
                    <div
                      key={transicao.id}
                      className="rounded-2xl border border-border/60 bg-background/60 p-4 text-sm"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <p className="font-medium capitalize">
                          {transicao.de_status.replaceAll("_", " ")} →{" "}
                          {transicao.para_status.replaceAll("_", " ")}
                        </p>
                        <span className="text-muted-foreground">
                          {formatDate(transicao.realizado_em)}
                        </span>
                      </div>
                      <p className="mt-2 text-muted-foreground">
                        {transicao.observacao || transicao.acao}
                      </p>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-muted-foreground">
                    Sem transições registradas.
                  </p>
                )}
              </div>
            </AccordionContent>
          </AccordionItem>
        )}

        {canUseAdminEditor && adminMode ? (
          <AccordionItem
            value="historico-admin"
            className="rounded-[1.75rem] border border-border/60 bg-card/60 px-6"
          >
            <AccordionTrigger className="text-base">
              Histórico do Editor
            </AccordionTrigger>
            <AccordionContent>
              {isAdminHistoryLoading ? (
                <div className="space-y-3">
                  <div className="h-24 animate-pulse rounded-[1.5rem] bg-background/60" />
                  <div className="h-24 animate-pulse rounded-[1.5rem] bg-background/60" />
                </div>
              ) : adminHistoryQuery.isError ? (
                <Alert
                  variant="destructive"
                  className="border-destructive/40 bg-destructive/10"
                >
                  <AlertCircleIcon className="size-4" />
                  <AlertTitle>
                    Falha ao carregar o histórico do editor
                  </AlertTitle>
                  <AlertDescription className="gap-3">
                    <p>{adminHistoryErrorMessage}</p>
                    <div className="flex flex-wrap gap-3">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          void adminHistoryQuery.refetch();
                        }}
                      >
                        Tentar novamente
                      </Button>
                    </div>
                  </AlertDescription>
                </Alert>
              ) : (
                <AdminOverrideHistory
                  associadoId={associadoId}
                  events={adminHistoryQuery.data ?? []}
                />
              )}
            </AccordionContent>
          </AccordionItem>
        ) : null}
      </Accordion>
      {hasUnsavedAdminChanges ? (
        <div className="fixed inset-x-4 bottom-4 z-50 flex justify-center md:inset-x-auto md:right-6">
          <div className="flex w-full max-w-2xl items-center justify-between gap-4 rounded-2xl border border-primary/30 bg-background/95 px-4 py-3 shadow-2xl shadow-black/40 backdrop-blur md:w-auto md:min-w-[32rem]">
            <div className="min-w-0">
              <p className="text-sm font-semibold text-foreground">
                Alterações do editor pendentes
              </p>
              <p className="text-sm text-muted-foreground">
                Salve contrato, ciclos, renovação e esteira em uma única ação.
              </p>
            </div>
            <div className="flex items-center gap-3">
              <StatusBadge
                status="pendente"
                label={`${Object.values(contractDirtyState).filter(hasDirtyContractState).length + (esteiraDirty ? 1 : 0)} bloco(s) pendente(s)`}
              />
              <Button
                onClick={() => setSaveAllOpen(true)}
                disabled={saveAllMutation.isPending}
              >
                <SaveIcon className="size-4" />
                Salvar alterações
              </Button>
            </div>
          </div>
        </div>
      ) : null}
      <AdminOverrideConfirmDialog
        open={saveAllOpen}
        onOpenChange={setSaveAllOpen}
        title="Salvar alterações do editor"
        description="Todas as alterações pendentes do editor avançado serão gravadas agora."
        summary={
          <div className="grid gap-2 text-sm">
            <p>
              Contratos pendentes:{" "}
              <span className="font-medium text-foreground">
                {
                  Object.values(contractDirtyState).filter(
                    hasDirtyContractState,
                  ).length
                }
              </span>
            </p>
            <p>
              Esteira pendente:{" "}
              <span className="font-medium text-foreground">
                {esteiraDirty ? "Sim" : "Não"}
              </span>
            </p>
          </div>
        }
        submitLabel="Salvar tudo"
        isSubmitting={saveAllMutation.isPending}
        onConfirm={async (motivo) => {
          try {
            await saveAllMutation.mutateAsync(motivo);
            setSaveAllOpen(false);
          } catch {
            // The mutation already shows the error toast.
          }
        }}
      />
      <ParcelaDetalheDialog
        associadoId={associadoId}
        target={selectedTarget}
        onOpenChange={(open) => {
          if (!open) {
            setSelectedTarget(null);
          }
        }}
      />
      <AlertDialog
        open={inativarDialogOpen}
        onOpenChange={(open) => {
          setInativarDialogOpen(open);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Inativar associado</AlertDialogTitle>
            <AlertDialogDescription>
              Esta ação marca o associado como inativo e o status passa a
              aparecer nos filtros e indicadores operacionais.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={inativarAssociadoMutation.isPending}>
              Voltar
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={(event) => {
                event.preventDefault();
                inativarAssociadoMutation.mutate();
              }}
              disabled={inativarAssociadoMutation.isPending}
            >
              Confirmar inativação
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

export default function AssociadoPage(props: AssociadoPageProps) {
  return (
    <RoleGuard
      allow={["ADMIN", "AGENTE", "ANALISTA", "COORDENADOR", "TESOUREIRO"]}
    >
      <AssociadoPageContent {...props} />
    </RoleGuard>
  );
}

function DetailItem({
  label,
  value,
}: {
  label: string;
  value?: string | null;
}) {
  return (
    <div className="rounded-2xl border border-border/60 bg-background/60 p-4">
      <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">
        {label}
      </p>
      <p className="mt-2 text-sm font-medium text-foreground">{value || "-"}</p>
    </div>
  );
}
