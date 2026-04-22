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
  RotateCcwIcon,
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
import AssociadoReactivationDialog from "@/components/associados/associado-reactivation-dialog";
import CadastroOrigemBadge from "@/components/associados/cadastro-origem-badge";
import AdminContractEditor from "@/components/associados/admin-contract-editor";
import type {
  AdminContractEditorHandle,
  AdminContractEditorPendingChanges,
  ContractEditorDirtyState,
} from "@/components/associados/admin-contract-editor";
import AdminLegacyInactivationReversalDialog from "@/components/associados/admin-legacy-inactivation-reversal-dialog";
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
import CopySnippet from "@/components/shared/copy-snippet";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
const INACTIVATION_OPTIONS = [
  {
    value: "inativo_inadimplente",
    label: "Inativo inadimplente",
    description: "Use quando a inativação deve manter o associado na régua de inadimplência.",
  },
  {
    value: "inativo_passivel_renovacao",
    label: "Inativo passível de renovação",
    description: "Use quando a inativação deve preservar o caso para tratamento de renovação.",
  },
] as const;
type InactivationTarget = (typeof INACTIVATION_OPTIONS)[number]["value"];
type LegacyInactivationReversalPayload = {
  motivo: string;
  status_retorno: string;
  etapa_esteira: string;
  status_esteira: string;
  observacao_esteira: string;
};
const SAFE_RENEWAL_STAGE_OPTIONS = [
  { value: "apto_a_renovar", label: "Apto a renovar" },
  { value: "em_analise_renovacao", label: "Em análise" },
  { value: "pendente_termo_agente", label: "Pendente termo do agente" },
  { value: "pendente_termo_analista", label: "Pendente termo do analista" },
  { value: "aprovado_analise_renovacao", label: "Aprovado pela análise" },
  { value: "aprovado_para_renovacao", label: "Aprovado para renovação" },
  { value: "solicitado_para_liquidacao", label: "Solicitado para liquidação" },
  { value: "efetivado", label: "Efetivar renovação" },
  { value: "revertido", label: "Cancelar renovação e manter ativo" },
] as const;

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
    .map((warning) => {
      if (warning.action === "normalized_last_occurrence") {
        return `${warning.message} A normalização já foi aplicada.`;
      }
      if (warning.action === "use_send_to_stage") {
        return `${warning.message} Use "Enviar para etapa" se quiser reposicionar a renovação.`;
      }
      if (warning.action === "review_cycle_dates") {
        return `${warning.message} Revise as datas dos ciclos antes da próxima edição.`;
      }
      if (warning.action === "review_duplicate_reference") {
        return `${warning.message} Revise a competência duplicada no editor.`;
      }
      return warning.message;
    })
    .join(" ");
}

function getAdminWarningSignature(warning: AdminEditorWarning) {
  return [
    warning.code,
    warning.scope ?? "",
    warning.competencia ?? "",
    warning.action ?? "",
    warning.message,
  ].join("::");
}

function getUnseenAdminWarnings(
  warnings: AdminEditorWarning[] | undefined,
  knownWarnings: AdminEditorWarning[] | undefined,
) {
  const knownSignatures = new Set(
    (knownWarnings ?? []).map(getAdminWarningSignature),
  );
  return (warnings ?? []).filter(
    (warning) => !knownSignatures.has(getAdminWarningSignature(warning)),
  );
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
            scope: "cycle_layout",
            action: "review_cycle_dates",
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
        scope: "cycle_layout",
        competencia: referencia_mes,
        action: "review_duplicate_reference",
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

function formatAdminStatusLabel(status?: string | null) {
  if (!status) {
    return "status anterior";
  }
  return status.replaceAll("_", " ");
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
  const [inactivationTarget, setInactivationTarget] =
    React.useState<InactivationTarget>("inativo_inadimplente");
  const [reativarDialogOpen, setReativarDialogOpen] = React.useState(false);
  const [saveAllOpen, setSaveAllOpen] = React.useState(false);
  const [revertInactivationOpen, setRevertInactivationOpen] =
    React.useState(false);
  const [revertLegacyInactivationOpen, setRevertLegacyInactivationOpen] =
    React.useState(false);
  const [renewalStageDialogOpen, setRenewalStageDialogOpen] =
    React.useState(false);
  const [renewalStageSelections, setRenewalStageSelections] = React.useState<
    Record<number, string>
  >({});
  const [renewalStageTarget, setRenewalStageTarget] = React.useState<{
    contratoId: number;
    contratoCodigo: string;
    targetStage: string;
  } | null>(null);
  const [pendingRenewalStageAfterSave, setPendingRenewalStageAfterSave] =
    React.useState<{
      contratoId: number;
      contratoCodigo: string;
      targetStage: string;
    } | null>(null);
  const pendingRenewalStageAfterSaveRef = React.useRef<{
    contratoId: number;
    contratoCodigo: string;
    targetStage: string;
  } | null>(null);
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
  const adminEditHref = canUseAdminEditor
    ? `/associados-editar/${associadoId}${
        adminMode || isCoordinator ? "?admin=1" : ""
      }`
    : null;

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

  const invalidateAdminRelatedQueries = React.useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ["associado", associadoId] });
    void queryClient.invalidateQueries({
      queryKey: ["admin-associado-history", associadoId],
    });
  }, [associadoId, queryClient]);

  const getCachedAdminWarnings = React.useCallback(() => {
    return (
      queryClient.getQueryData<AdminAssociadoEditorPayload>([
        "admin-associado-editor",
        associadoId,
      ])?.warnings ?? []
    );
  }, [associadoId, queryClient]);

  const inativarAssociadoMutation = useMutation({
    mutationFn: async (statusDestino: InactivationTarget) =>
      apiFetch<AssociadoDetail>(`associados/${associadoId}/inativar`, {
        method: "POST",
        body: {
          status_destino: statusDestino,
        },
      }),
    onSuccess: async (payload) => {
      toast.success("Associado inativado com sucesso.");
      setInativarDialogOpen(false);
      queryClient.setQueryData(["associado", associadoId], payload);
      await queryClient.invalidateQueries({ queryKey: ["associados"] });
      await queryClient.invalidateQueries({ queryKey: ["contratos"] });
      await queryClient.invalidateQueries({
        queryKey: ["admin-associado-editor", associadoId],
      });
      await queryClient.invalidateQueries({
        queryKey: ["admin-associado-history", associadoId],
      });
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : "Falha ao inativar associado.",
      );
    },
  });

  const revertInactivationMutation = useMutation({
    mutationFn: async (motivo: string) => {
      const eventId = adminEditorQuery.data?.inactivation_reversal?.event_id;
      if (!eventId) {
        throw new Error("Nenhuma inativação reversível foi encontrada.");
      }
      return apiFetch(`admin-overrides/events/${eventId}/reverter/`, {
        method: "POST",
        body: { motivo_reversao: motivo },
      });
    },
    onSuccess: async () => {
      toast.success("Inativação revertida com sucesso.");
      setRevertInactivationOpen(false);
      await queryClient.invalidateQueries({ queryKey: ["associado", associadoId] });
      await queryClient.invalidateQueries({
        queryKey: ["admin-associado-editor", associadoId],
      });
      await queryClient.invalidateQueries({
        queryKey: ["admin-associado-history", associadoId],
      });
      await queryClient.invalidateQueries({ queryKey: ["associados"] });
      await queryClient.invalidateQueries({ queryKey: ["contratos"] });
    },
    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : "Falha ao reverter a inativação.",
      );
    },
  });

  const revertLegacyInactivationMutation = useMutation({
    mutationFn: async (payload: LegacyInactivationReversalPayload) =>
      apiFetch(
        `admin-overrides/associados/${associadoId}/reverter-inativacao-legada/`,
        {
          method: "POST",
          body: payload,
        },
      ),
    onSuccess: async () => {
      toast.success("Inativação legada revertida com sucesso.");
      setRevertLegacyInactivationOpen(false);
      await queryClient.invalidateQueries({ queryKey: ["associado", associadoId] });
      await queryClient.invalidateQueries({
        queryKey: ["admin-associado-editor", associadoId],
      });
      await queryClient.invalidateQueries({
        queryKey: ["admin-associado-history", associadoId],
      });
      await queryClient.invalidateQueries({ queryKey: ["associados"] });
      await queryClient.invalidateQueries({ queryKey: ["contratos"] });
    },
    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : "Falha ao reverter a inativação legada.",
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
    (payload?: AdminAssociadoEditorPayload) => {
      if (payload) {
        queryClient.setQueryData(
          ["admin-associado-editor", associadoId],
          payload,
        );
      } else {
        void queryClient.invalidateQueries({
          queryKey: ["admin-associado-editor", associadoId],
        });
      }
      invalidateAdminRelatedQueries();
    },
    [
      associadoId,
      invalidateAdminRelatedQueries,
      queryClient,
    ],
  );

  const hasUnsavedAdminChanges =
    canUseAdminEditor &&
    adminMode &&
    (Object.values(contractDirtyState).some(hasDirtyContractState) ||
      esteiraDirty);

  const queueRenewalStageAfterSave = React.useCallback(
    (
      target: {
        contratoId: number;
        contratoCodigo: string;
        targetStage: string;
      } | null,
    ) => {
      pendingRenewalStageAfterSaveRef.current = target;
      setPendingRenewalStageAfterSave(target);
    },
    [],
  );

  const requestRenewalStageTransition = React.useCallback(
    (target: {
      contratoId: number;
      contratoCodigo: string;
      targetStage: string;
    }) => {
      if (hasUnsavedAdminChanges) {
        queueRenewalStageAfterSave(target);
        setSaveAllOpen(true);
        return;
      }

      queueRenewalStageAfterSave(null);
      setRenewalStageTarget(target);
      setRenewalStageDialogOpen(true);
    },
    [hasUnsavedAdminChanges, queueRenewalStageAfterSave],
  );

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
      const unseenLocalWarnings = getUnseenAdminWarnings(
        localWarnings,
        getCachedAdminWarnings(),
      );
      if (unseenLocalWarnings.length) {
        toast.warning(formatAdminWarnings(unseenLocalWarnings));
      }
      return apiFetch<AdminAssociadoEditorPayload>(
        `admin-overrides/associados/${associadoId}/save-all/`,
        {
          method: "POST",
          body: {
            motivo,
            dirty_sections: pending.esteira ? ["esteira"] : undefined,
            contratos: pending.contratos,
            esteira: pending.esteira ?? undefined,
          },
        },
      );
    },
    onSuccess: (payload) => {
      const previousWarnings = getCachedAdminWarnings();
      toast.success("Alterações do editor salvas.");
      const unseenWarnings = getUnseenAdminWarnings(
        payload.warnings,
        previousWarnings,
      );
      if (unseenWarnings.length) {
        toast.warning(formatAdminWarnings(unseenWarnings));
      }
      queryClient.setQueryData(
        ["admin-associado-editor", associadoId],
        payload,
      );
      setContractDirtyState({});
      setEsteiraDirty(false);
      void queryClient.invalidateQueries({ queryKey: ["tesouraria-baixa-manual"] });
      invalidateAdminRelatedQueries();

      const queuedTransition = pendingRenewalStageAfterSaveRef.current;
      if (queuedTransition) {
        queueRenewalStageAfterSave(null);
        setRenewalStageTarget(queuedTransition);
        setRenewalStageDialogOpen(true);
      }
    },
    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : "Falha ao salvar alterações administrativas.",
      );
    },
  });

  const renewalStageMutation = useMutation({
    mutationFn: async ({
      contratoId,
      targetStage,
      motivo,
    }: {
      contratoId: number;
      targetStage: string;
      motivo: string;
    }) =>
      apiFetch<AdminAssociadoEditorPayload>(
        `admin-overrides/associados/${associadoId}/renewal-stage/`,
        {
          method: "POST",
          body: {
            contrato_id: contratoId,
            target_stage: targetStage,
            motivo,
          },
        },
      ),
    onSuccess: (payload, variables) => {
      const previousWarnings = getCachedAdminWarnings();
      toast.success("Etapa de renovação atualizada.");
      const unseenWarnings = getUnseenAdminWarnings(
        payload.warnings,
        previousWarnings,
      );
      if (unseenWarnings.length) {
        toast.warning(formatAdminWarnings(unseenWarnings));
      }
      queryClient.setQueryData(
        ["admin-associado-editor", associadoId],
        payload,
      );
      setRenewalStageSelections((current) => {
        if (!(variables.contratoId in current)) {
          return current;
        }
        const next = { ...current };
        delete next[variables.contratoId];
        return next;
      });
      setRenewalStageTarget(null);
      invalidateAdminRelatedQueries();
    },
    onError: (error) => {
      toast.error(
        error instanceof Error
          ? error.message
          : "Falha ao reposicionar a renovação.",
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
  const matriculaDisplay =
    associado.matricula_display ||
    associado.matricula ||
    associado.contato?.matricula_servidor ||
    "";
  const agenteNome = associado.agente?.full_name || "Sem agente";

  return (
    <div className="space-y-6">
      <section className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="text-sm uppercase tracking-[0.2em] text-muted-foreground">
            Associado
          </p>
          <h1 className="mt-2">
            <CopySnippet
              label="Nome"
              value={associado.nome_completo}
              inline
              className="max-w-full text-3xl font-semibold leading-tight"
            />
          </h1>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {matriculaDisplay ? (
              <CopySnippet label="Matrícula" value={matriculaDisplay} mono />
            ) : (
              <span className="inline-flex rounded-full border border-border/60 bg-background/70 px-3 py-1 text-xs text-muted-foreground">
                Sem matrícula
              </span>
            )}
            <CopySnippet label="CPF" value={associado.cpf_cnpj} mono />
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-border/60 bg-card/60 px-3 py-1 text-xs font-medium text-foreground/90">
              <UserIcon className="size-3.5 text-primary" />
              Agente: {agenteNome}
            </span>
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
          {(isAdmin || isCoordinator) && associado.status === "inativo" ? (
            <Button
              variant="outline"
              className="border-emerald-500/40 text-emerald-200"
              onClick={() => setReativarDialogOpen(true)}
            >
              Iniciar reativação
            </Button>
          ) : null}
          {(isAdmin || isCoordinator) && associado.status !== "inativo" ? (
            <Button
              variant="outline"
              className="border-amber-500/40 text-amber-200"
              onClick={() => setInativarDialogOpen(true)}
            >
              Inativar associado
            </Button>
          ) : null}
          {adminEditHref ? (
            <Button variant="outline" asChild>
              <Link href={adminEditHref}>
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
                  O editor avançado pode ser usado para ajustar cadastro,
                  contrato, ciclos, arquivos e esteira, inclusive quando o
                  associado estiver inativo.
                </p>
                <div className="flex flex-wrap gap-3">
                  {adminEditorQuery.data?.inactivation_reversal?.available ? (
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => setRevertInactivationOpen(true)}
                    >
                      <RotateCcwIcon className="mr-2 size-4" />
                      Reverter inativação
                    </Button>
                  ) : null}
                  {adminEditorQuery.data?.legacy_inactivation_reversal?.available ? (
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => setRevertLegacyInactivationOpen(true)}
                    >
                      <RotateCcwIcon className="mr-2 size-4" />
                      Reverter inativação legada
                    </Button>
                  ) : null}
                  {adminEditHref ? (
                    <Button type="button" variant="outline" size="sm" asChild>
                      <Link href={adminEditHref}>Editar cadastro</Link>
                    </Button>
                  ) : null}
                </div>
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
                <div className="rounded-[1.5rem] border border-primary/20 bg-primary/5 p-4">
                  <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                    <div>
                      <p className="text-sm font-semibold text-foreground">
                        Transição segura da renovação
                      </p>
                      <p className="text-sm text-muted-foreground">
                        Reposiciona o contrato em uma etapa do fluxo de renovação com validação de negócio e registro no histórico.
                      </p>
                    </div>
                  </div>
                  <div className="mt-4 grid gap-3">
                    {adminEditorQuery.data.contratos.map((contract) => {
                      const selectedStage =
                        renewalStageSelections[contract.id] ??
                        contract.refinanciamento_ativo?.status ??
                        "apto_a_renovar";
                      return (
                        <div
                          key={`renewal-stage-${contract.id}`}
                          className="grid gap-3 rounded-2xl border border-border/60 bg-background/60 p-4 lg:grid-cols-[minmax(0,1fr)_18rem_auto]"
                        >
                          <div className="min-w-0">
                            <p className="font-medium text-foreground">
                              {contract.codigo}
                            </p>
                            <p className="text-sm text-muted-foreground">
                              Atual:{" "}
                              {(
                                SAFE_RENEWAL_STAGE_OPTIONS.find(
                                  (item) =>
                                    item.value ===
                                    (contract.refinanciamento_ativo?.status ??
                                      "apto_a_renovar"),
                                )?.label ??
                                contract.refinanciamento_ativo?.status ??
                                "Apto a renovar"
                              ).replaceAll("_", " ")}
                            </p>
                          </div>
                          <Select
                            value={selectedStage}
                            onValueChange={(value) =>
                              setRenewalStageSelections((current) => ({
                                ...current,
                                [contract.id]: value,
                              }))
                            }
                          >
                            <SelectTrigger>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {SAFE_RENEWAL_STAGE_OPTIONS.map((option) => (
                                <SelectItem
                                  key={`${contract.id}-${option.value}`}
                                  value={option.value}
                                >
                                  {option.label}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                          <Button
                            type="button"
                            variant="outline"
                            disabled={
                              saveAllMutation.isPending ||
                              renewalStageMutation.isPending
                            }
                            onClick={() =>
                              requestRenewalStageTransition({
                                contratoId: contract.id,
                                contratoCodigo: contract.codigo,
                                targetStage: selectedStage,
                              })
                            }
                          >
                            Enviar para etapa
                          </Button>
                        </div>
                      );
                    })}
                  </div>
                  {hasUnsavedAdminChanges ? (
                    <p className="mt-3 text-xs text-amber-200">
                      Se houver alterações pendentes, elas serão salvas antes da transição segura.
                    </p>
                  ) : null}
                </div>
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
                    renewalStageOptions={SAFE_RENEWAL_STAGE_OPTIONS}
                    selectedRenewalStage={
                      renewalStageSelections[contract.id] ??
                      contract.refinanciamento_ativo?.status ??
                      "apto_a_renovar"
                    }
                    onSelectedRenewalStageChange={(value) =>
                      setRenewalStageSelections((current) => ({
                        ...current,
                        [contract.id]: value,
                      }))
                    }
                    onRequestRenewalStageTransition={() =>
                      requestRenewalStageTransition({
                        contratoId: contract.id,
                        contratoCodigo: contract.codigo,
                        targetStage:
                          renewalStageSelections[contract.id] ??
                          contract.refinanciamento_ativo?.status ??
                          "apto_a_renovar",
                      })
                    }
                    renewalTransitionDisabled={
                      saveAllMutation.isPending ||
                      renewalStageMutation.isPending
                    }
                    renewalTransitionPending={
                      renewalStageMutation.isPending &&
                      renewalStageMutation.variables?.contratoId === contract.id
                    }
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
        onOpenChange={(open) => {
          setSaveAllOpen(open);
          if (!open && !saveAllMutation.isPending) {
            queueRenewalStageAfterSave(null);
          }
        }}
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
            {pendingRenewalStageAfterSave ? (
              <p>
                Próxima ação:{" "}
                <span className="font-medium text-foreground">
                  salvar e abrir a transição para{" "}
                  {SAFE_RENEWAL_STAGE_OPTIONS.find(
                    (item) =>
                      item.value === pendingRenewalStageAfterSave.targetStage,
                  )?.label ?? pendingRenewalStageAfterSave.targetStage}
                </span>
              </p>
            ) : null}
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
      <AdminOverrideConfirmDialog
        open={renewalStageDialogOpen}
        onOpenChange={setRenewalStageDialogOpen}
        title="Enviar renovação para etapa"
        description="A transição reposiciona a renovação no fluxo operacional e sincroniza o histórico administrativo."
        summary={
          renewalStageTarget ? (
            <div className="grid gap-2 text-sm">
              <p>
                Contrato:{" "}
                <span className="font-medium text-foreground">
                  {renewalStageTarget.contratoCodigo}
                </span>
              </p>
              <p>
                Etapa destino:{" "}
                <span className="font-medium text-foreground">
                  {SAFE_RENEWAL_STAGE_OPTIONS.find(
                    (item) => item.value === renewalStageTarget.targetStage,
                  )?.label ?? renewalStageTarget.targetStage}
                </span>
              </p>
            </div>
          ) : null
        }
        submitLabel="Enviar para etapa"
        isSubmitting={renewalStageMutation.isPending}
        onConfirm={async (motivo) => {
          if (!renewalStageTarget) {
            return;
          }
          await renewalStageMutation.mutateAsync({
            contratoId: renewalStageTarget.contratoId,
            targetStage: renewalStageTarget.targetStage,
            motivo,
          });
          setRenewalStageDialogOpen(false);
          setRenewalStageTarget(null);
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
          if (open) {
            setInactivationTarget("inativo_inadimplente");
          }
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Inativar associado</AlertDialogTitle>
            <AlertDialogDescription>
              Confirme como o associado deve ficar classificado após a
              inativação. O associado, documentos e histórico serão mantidos.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="space-y-3">
            <Select
              value={inactivationTarget}
              onValueChange={(value) =>
                setInactivationTarget(value as InactivationTarget)
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {INACTIVATION_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-sm text-muted-foreground">
              {
                INACTIVATION_OPTIONS.find(
                  (option) => option.value === inactivationTarget,
                )?.description
              }
            </p>
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={inativarAssociadoMutation.isPending}>
              Voltar
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={(event) => {
                event.preventDefault();
                inativarAssociadoMutation.mutate(inactivationTarget);
              }}
              disabled={inativarAssociadoMutation.isPending}
            >
              Confirmar inativação
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      <AdminOverrideConfirmDialog
        open={revertInactivationOpen}
        onOpenChange={setRevertInactivationOpen}
        title="Reverter inativação"
        description="A reversão restaura o status anterior da inativação sem abrir um novo fluxo de reativação."
        summary={
          adminEditorQuery.data?.inactivation_reversal?.available ? (
            <div className="space-y-2">
              <p className="font-medium text-foreground">
                O associado voltará para{" "}
                {formatAdminStatusLabel(
                  adminEditorQuery.data.inactivation_reversal.previous_status,
                )}
                .
              </p>
              <p>
                Inativação registrada em{" "}
                {formatDate(
                  adminEditorQuery.data.inactivation_reversal.event_created_at,
                )}
                {adminEditorQuery.data.inactivation_reversal.realizado_por
                  ? ` por ${adminEditorQuery.data.inactivation_reversal.realizado_por.full_name}`
                  : ""}
                .
              </p>
            </div>
          ) : null
        }
        submitLabel="Reverter inativação"
        isSubmitting={revertInactivationMutation.isPending}
        onConfirm={async (motivo) => {
          await revertInactivationMutation.mutateAsync(motivo);
        }}
      />
      <AdminLegacyInactivationReversalDialog
        open={revertLegacyInactivationOpen}
        onOpenChange={setRevertLegacyInactivationOpen}
        currentStatus={
          adminEditorQuery.data?.legacy_inactivation_reversal?.current_status
        }
        defaultStatus={
          adminEditorQuery.data?.legacy_inactivation_reversal?.suggested_status
        }
        defaultStage={
          adminEditorQuery.data?.legacy_inactivation_reversal
            ?.suggested_esteira_etapa
        }
        defaultQueueStatus={
          adminEditorQuery.data?.legacy_inactivation_reversal
            ?.suggested_esteira_status
        }
        isSubmitting={revertLegacyInactivationMutation.isPending}
        onConfirm={async (payload) => {
          await revertLegacyInactivationMutation.mutateAsync(payload);
        }}
      />
      <AssociadoReactivationDialog
        open={reativarDialogOpen}
        onOpenChange={setReativarDialogOpen}
        associado={associado}
        onSuccess={(payload) => {
          queryClient.setQueryData(["associado", associadoId], payload);
          void queryClient.invalidateQueries({ queryKey: ["associados"] });
          void queryClient.invalidateQueries({ queryKey: ["contratos"] });
          void queryClient.invalidateQueries({ queryKey: ["tesouraria-contratos"] });
        }}
      />
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
