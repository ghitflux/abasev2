"use client";

import * as React from "react";
import { format } from "date-fns";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircleIcon,
  ClipboardListIcon,
  ExternalLinkIcon,
  HandCoinsIcon,
  PaperclipIcon,
  PencilLineIcon,
  PlusIcon,
  SearchIcon,
  Trash2Icon,
  TrendingDownIcon,
  UploadIcon,
} from "lucide-react";
import { toast } from "sonner";

import type { DespesaItem, DespesaKpis, PaginatedResponse } from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import { buildBackendFileUrl } from "@/lib/backend-files";
import {
  centsToDecimal,
  decimalToCents,
  formatCurrency,
  formatDate,
  formatDateTime,
  formatLongMonthYear,
} from "@/lib/formatters";
import CalendarCompetencia from "@/components/custom/calendar-competencia";
import DatePicker from "@/components/custom/date-picker";
import FileUploadDropzone from "@/components/custom/file-upload-dropzone";
import InputCurrency from "@/components/custom/input-currency";
import StatusBadge from "@/components/custom/status-badge";
import DataTable, { type DataTableColumn } from "@/components/shared/data-table";
import StatsCard from "@/components/shared/stats-card";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogMedia,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

const PAGE_SIZE = 10;
const comprovanteAccept = {
  "application/pdf": [".pdf"],
  "image/png": [".png"],
  "image/jpeg": [".jpg", ".jpeg"],
};

type DespesaListResponse = PaginatedResponse<DespesaItem> & {
  kpis: DespesaKpis;
};

type DespesaFormState = {
  id?: number;
  categoria: string;
  descricao: string;
  valor: number | null;
  data_despesa?: Date;
  data_pagamento?: Date;
  status: string;
  tipo: string;
  recorrencia: string;
  recorrencia_ativa: boolean;
  observacoes: string;
};

const initialFormState: DespesaFormState = {
  categoria: "",
  descricao: "",
  valor: null,
  data_despesa: undefined,
  data_pagamento: undefined,
  status: "pendente",
  tipo: "fixa",
  recorrencia: "nenhuma",
  recorrencia_ativa: true,
  observacoes: "",
};

const statusOptions = [
  { value: "todos", label: "Status financeiro" },
  { value: "pendente", label: "Pendente" },
  { value: "pago", label: "Pago" },
];

const statusAnexoOptions = [
  { value: "todos", label: "Status do anexo" },
  { value: "pendente", label: "Pendente de anexo" },
  { value: "anexado", label: "Anexado" },
];

const tipoOptions = [
  { value: "todos", label: "Tipo" },
  { value: "fixa", label: "Fixa" },
  { value: "variavel", label: "Variável" },
];

const recorrenciaOptions = [
  { value: "nenhuma", label: "Sem recorrência" },
  { value: "mensal", label: "Mensal" },
  { value: "trimestral", label: "Trimestral" },
  { value: "anual", label: "Anual" },
];

const statusFinanceiroOptions = statusOptions.filter((option) => option.value !== "todos");
const tipoLancamentoOptions = tipoOptions.filter((option) => option.value !== "todos");

function parseIsoDate(value?: string | null) {
  if (!value) return undefined;

  const [year, month, day] = value.split("-").map(Number);
  if (!year || !month || !day) return undefined;

  return new Date(year, month - 1, day, 12, 0, 0, 0);
}

function formatDateForApi(value?: Date) {
  return value ? format(value, "yyyy-MM-dd") : "";
}

function buildFormData(state: DespesaFormState, attachment?: File | null) {
  const formData = new FormData();
  formData.set("categoria", state.categoria);
  formData.set("descricao", state.descricao);
  formData.set("valor", centsToDecimal(state.valor));
  formData.set("data_despesa", formatDateForApi(state.data_despesa));
  formData.set("status", state.status);
  formData.set("tipo", state.tipo);
  formData.set("recorrencia", state.recorrencia);
  formData.set("recorrencia_ativa", state.recorrencia_ativa ? "true" : "false");
  formData.set("observacoes", state.observacoes);

  if (state.status === "pago" && state.data_pagamento) {
    formData.set("data_pagamento", formatDateForApi(state.data_pagamento));
  }

  if (attachment) {
    formData.set("anexo", attachment);
  }

  return formData;
}

function mapItemToFormState(item: DespesaItem): DespesaFormState {
  return {
    id: item.id,
    categoria: item.categoria,
    descricao: item.descricao,
    valor: decimalToCents(item.valor),
    data_despesa: parseIsoDate(item.data_despesa),
    data_pagamento: parseIsoDate(item.data_pagamento),
    status: item.status,
    tipo: item.tipo || "fixa",
    recorrencia: item.recorrencia,
    recorrencia_ativa: item.recorrencia_ativa,
    observacoes: item.observacoes || "",
  };
}

function formatRecorrenciaLabel(value: string) {
  const labels: Record<string, string> = {
    nenhuma: "Sem recorrência",
    mensal: "Mensal",
    trimestral: "Trimestral",
    anual: "Anual",
  };
  return labels[value] ?? value;
}

function formatTipoLabel(value: string) {
  const labels: Record<string, string> = {
    fixa: "Fixa",
    variavel: "Variável",
  };
  return labels[value] ?? "Não informado";
}

export default function TesourariaDespesasPage() {
  const queryClient = useQueryClient();
  const [competencia, setCompetencia] = React.useState(() => new Date());
  const [page, setPage] = React.useState(1);
  const [search, setSearch] = React.useState("");
  const [statusFilter, setStatusFilter] = React.useState("todos");
  const [statusAnexoFilter, setStatusAnexoFilter] = React.useState("todos");
  const [tipoFilter, setTipoFilter] = React.useState("todos");
  const [formState, setFormState] = React.useState<DespesaFormState>(initialFormState);
  const [formAttachment, setFormAttachment] = React.useState<File | null>(null);
  const [existingFormAttachment, setExistingFormAttachment] = React.useState<DespesaItem["anexo"] | null>(
    null,
  );
  const [formOpen, setFormOpen] = React.useState(false);
  const [uploadTarget, setUploadTarget] = React.useState<DespesaItem | null>(null);
  const [uploadFile, setUploadFile] = React.useState<File | null>(null);
  const [deleteTarget, setDeleteTarget] = React.useState<DespesaItem | null>(null);
  const [deleteConfirmed, setDeleteConfirmed] = React.useState(false);

  const despesasQuery = useQuery({
    queryKey: [
      "tesouraria-despesas",
      page,
      competencia.toISOString(),
      search,
      statusFilter,
      statusAnexoFilter,
      tipoFilter,
    ],
    queryFn: () =>
      apiFetch<DespesaListResponse>("tesouraria/despesas", {
        query: {
          page,
          page_size: PAGE_SIZE,
          competencia: format(competencia, "yyyy-MM"),
          search: search || undefined,
          status: statusFilter !== "todos" ? statusFilter : undefined,
          status_anexo: statusAnexoFilter !== "todos" ? statusAnexoFilter : undefined,
          tipo: tipoFilter !== "todos" ? tipoFilter : undefined,
        },
      }),
  });

  const saveMutation = useMutation({
    mutationFn: async ({
      values,
      attachment,
    }: {
      values: DespesaFormState;
      attachment: File | null;
    }) => {
      const path = values.id ? `tesouraria/despesas/${values.id}/` : "tesouraria/despesas";
      return apiFetch<DespesaItem>(path, {
        method: values.id ? "PATCH" : "POST",
        formData: buildFormData(values, attachment),
      });
    },
    onSuccess: (payload, variables) => {
      setFormOpen(false);
      setFormState(initialFormState);
      setFormAttachment(null);
      setExistingFormAttachment(null);
      setPage(1);
      toast.success(
        !variables.values.id && payload.status_anexo === "pendente"
          ? "Despesa lançada. Pendente de anexo."
          : variables.values.id
            ? "Despesa atualizada."
            : "Despesa lançada com sucesso.",
      );
      void queryClient.invalidateQueries({ queryKey: ["tesouraria-despesas"] });
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Não foi possível salvar a despesa.");
    },
  });

  const uploadMutation = useMutation({
    mutationFn: async ({ id, file }: { id: number; file: File }) => {
      const formData = new FormData();
      formData.set("anexo", file);
      return apiFetch<DespesaItem>(`tesouraria/despesas/${id}/anexar`, {
        method: "POST",
        formData,
      });
    },
    onSuccess: () => {
      setUploadTarget(null);
      setUploadFile(null);
      toast.success("Anexo atualizado com sucesso.");
      void queryClient.invalidateQueries({ queryKey: ["tesouraria-despesas"] });
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Falha ao anexar comprovante.");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: number) =>
      apiFetch(`tesouraria/despesas/${id}/`, {
        method: "DELETE",
      }),
    onSuccess: () => {
      toast.success("Despesa excluída.");
      void queryClient.invalidateQueries({ queryKey: ["tesouraria-despesas"] });
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Falha ao excluir despesa.");
    },
  });

  const rows = despesasQuery.data?.results ?? [];
  const totalPages = Math.max(1, Math.ceil((despesasQuery.data?.count ?? 0) / PAGE_SIZE));
  const kpis = despesasQuery.data?.kpis;

  const columns = React.useMemo<DataTableColumn<DespesaItem>[]>(
    () => [
      {
        id: "descricao",
        header: "Despesa",
        cell: (row) => (
          <div className="min-w-72 space-y-1">
            <p className="font-semibold">{row.categoria}</p>
            <p className="text-sm text-muted-foreground">{row.descricao}</p>
            {row.observacoes ? (
              <p className="text-xs text-muted-foreground line-clamp-2">{row.observacoes}</p>
            ) : null}
          </div>
        ),
      },
      {
        id: "valor",
        header: "Valor / Datas",
        cell: (row) => (
          <div className="space-y-1">
            <p className="font-semibold">{formatCurrency(row.valor)}</p>
            <p className="text-xs text-muted-foreground">
              Lançada em {formatDate(row.data_despesa)}
            </p>
            <p className="text-xs text-muted-foreground">
              {row.data_pagamento
                ? `Paga em ${formatDate(row.data_pagamento)}`
                : "Pagamento pendente"}
            </p>
          </div>
        ),
      },
      {
        id: "status",
        header: "Situação",
        cell: (row) => (
          <div className="space-y-2">
            <StatusBadge
              status={row.status}
              label={row.status === "pago" ? "Pago" : "Pendente"}
            />
            <StatusBadge
              status={row.status_anexo === "anexado" ? "anexado" : "pendente"}
              label={row.status_anexo === "anexado" ? "Anexado" : "Pendente de anexo"}
            />
          </div>
        ),
      },
      {
        id: "classificacao",
        header: "Classificação",
        cell: (row) => (
          <div className="space-y-1 text-sm">
            <p>{formatTipoLabel(row.tipo)}</p>
            <p className="text-muted-foreground">{formatRecorrenciaLabel(row.recorrencia)}</p>
          </div>
        ),
      },
      {
        id: "lancado_por",
        header: "Lançado por",
        cell: (row) => (
          <div className="space-y-1 text-sm">
            <p>{row.lancado_por?.full_name || "Sistema"}</p>
            <p className="text-muted-foreground">{formatDateTime(row.created_at)}</p>
          </div>
        ),
      },
      {
        id: "acoes",
        header: "Ações",
        cell: (row) => {
          const attachmentHref = row.anexo
            ? buildBackendFileUrl(row.anexo.url || row.anexo.arquivo_referencia)
            : null;

          return (
            <div className="flex min-w-72 flex-wrap gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  setFormState(mapItemToFormState(row));
                  setFormAttachment(null);
                  setExistingFormAttachment(row.anexo ?? null);
                  setFormOpen(true);
                }}
              >
                <PencilLineIcon className="size-4" />
                Editar
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  setUploadTarget(row);
                  setUploadFile(null);
                }}
              >
                <PaperclipIcon className="size-4" />
                {row.anexo ? "Substituir anexo" : "Anexar"}
              </Button>
              {attachmentHref ? (
                <Button asChild size="sm" variant="outline">
                  <a href={attachmentHref} target="_blank" rel="noreferrer">
                    <ExternalLinkIcon className="size-4" />
                    Ver anexo
                  </a>
                </Button>
              ) : null}
              <Button
                size="sm"
                variant="outline"
                className="border-rose-500/40 text-rose-200"
                disabled={deleteMutation.isPending}
                onClick={() => {
                  setDeleteTarget(row);
                  setDeleteConfirmed(false);
                }}
              >
                <Trash2Icon className="size-4" />
                Excluir
              </Button>
            </div>
          );
        },
      },
    ],
    [deleteMutation],
  );

  const canSubmitForm =
    Boolean(
      formState.categoria.trim() &&
        formState.descricao.trim() &&
        formState.valor !== null &&
        formState.data_despesa &&
        (formState.status !== "pago" || formState.data_pagamento),
    );

  const uploadHref = uploadTarget?.anexo
    ? buildBackendFileUrl(uploadTarget.anexo.url || uploadTarget.anexo.arquivo_referencia)
    : null;
  const formAttachmentHref = existingFormAttachment
    ? buildBackendFileUrl(existingFormAttachment.url || existingFormAttachment.arquivo_referencia)
    : null;

  return (
    <div className="space-y-6">
      <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_auto]">
        <Card className="rounded-[1.75rem] border-border/60 bg-card/70">
          <CardContent className="flex flex-col gap-4 p-6 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="text-sm uppercase tracking-[0.28em] text-muted-foreground">
                Tesouraria
              </p>
              <h1 className="text-3xl font-semibold">Despesas da associação</h1>
              <p className="text-sm text-muted-foreground">
                Competência ativa: {formatLongMonthYear(competencia)}
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <CalendarCompetencia
                value={competencia}
                onChange={(value) => {
                  setCompetencia(value);
                  setPage(1);
                }}
                className="w-full rounded-2xl bg-card/60 sm:w-56"
              />
              <Button
                onClick={() => {
                  setFormState(initialFormState);
                  setFormAttachment(null);
                  setExistingFormAttachment(null);
                  setFormOpen(true);
                }}
              >
                <PlusIcon className="size-4" />
                Nova despesa
              </Button>
            </div>
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <StatsCard
          title="Total de despesas"
          value={String(kpis?.total_despesas ?? 0)}
          delta="Despesas no filtro atual"
          icon={ClipboardListIcon}
        />
        <StatsCard
          title="Valor total"
          value={formatCurrency(kpis?.valor_total)}
          delta="Soma das despesas filtradas"
          icon={HandCoinsIcon}
          tone="neutral"
        />
        <StatsCard
          title="Valor pago"
          value={formatCurrency(kpis?.valor_pago)}
          delta="Total liquidado"
          icon={TrendingDownIcon}
          tone="positive"
        />
        <StatsCard
          title="Valor pendente"
          value={formatCurrency(kpis?.valor_pendente)}
          delta="Ainda sem pagamento"
          icon={AlertCircleIcon}
          tone="warning"
        />
        <StatsCard
          title="Pendentes de anexo"
          value={String(kpis?.pendentes_anexo ?? 0)}
          delta="Aguardando comprovante"
          icon={UploadIcon}
          tone="warning"
        />
      </section>

      <section className="grid gap-3 rounded-[1.75rem] border border-border/60 bg-card/50 p-4 lg:grid-cols-[minmax(0,1fr)_180px_200px_180px_auto]">
        <div className="relative">
          <SearchIcon className="pointer-events-none absolute top-1/2 left-4 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
            placeholder="Buscar por categoria ou descrição"
            className="rounded-2xl border-border/60 bg-card/60 pl-11"
          />
        </div>
        <Select
          value={statusFilter}
          onValueChange={(value) => {
            setStatusFilter(value);
            setPage(1);
          }}
        >
          <SelectTrigger
            aria-label="Status financeiro"
            className="h-11 w-full rounded-2xl border-border/60 bg-card/60"
          >
            <SelectValue placeholder="Status financeiro" />
          </SelectTrigger>
          <SelectContent>
            {statusOptions.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select
          value={statusAnexoFilter}
          onValueChange={(value) => {
            setStatusAnexoFilter(value);
            setPage(1);
          }}
        >
          <SelectTrigger
            aria-label="Status do anexo"
            className="h-11 w-full rounded-2xl border-border/60 bg-card/60"
          >
            <SelectValue placeholder="Status do anexo" />
          </SelectTrigger>
          <SelectContent>
            {statusAnexoOptions.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select
          value={tipoFilter}
          onValueChange={(value) => {
            setTipoFilter(value);
            setPage(1);
          }}
        >
          <SelectTrigger aria-label="Tipo" className="h-11 w-full rounded-2xl border-border/60 bg-card/60">
            <SelectValue placeholder="Tipo" />
          </SelectTrigger>
          <SelectContent>
            {tipoOptions.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button onClick={() => void queryClient.invalidateQueries({ queryKey: ["tesouraria-despesas"] })}>
          Atualizar
        </Button>
      </section>

      <DataTable
        data={rows}
        columns={columns}
        currentPage={page}
        totalPages={totalPages}
        onPageChange={setPage}
        emptyMessage="Nenhuma despesa encontrada para os filtros informados."
        loading={despesasQuery.isLoading}
        skeletonRows={6}
      />

      <Dialog
        open={formOpen}
        onOpenChange={(open) => {
          setFormOpen(open);
          if (!open) {
            setFormState(initialFormState);
            setFormAttachment(null);
            setExistingFormAttachment(null);
          }
        }}
      >
        <DialogContent className="grid h-[min(92dvh,56rem)] w-[min(96vw,48rem)] max-h-[92dvh] grid-rows-[auto_minmax(0,1fr)_auto] overflow-hidden p-0 sm:max-w-3xl">
          <DialogHeader className="border-b border-border/60 px-6 pb-4 pt-6 pr-14">
            <DialogTitle>{formState.id ? "Editar despesa" : "Nova despesa"}</DialogTitle>
            <DialogDescription>
              Você pode anexar o comprovante agora ou depois. Se salvar sem arquivo, a despesa ficará pendente de anexo.
            </DialogDescription>
          </DialogHeader>

          <div className="min-h-0 overflow-y-auto overflow-x-hidden px-6 py-5">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="despesa-categoria">Categoria</Label>
                  <Input
                    id="despesa-categoria"
                    value={formState.categoria}
                    onChange={(event) =>
                      setFormState((current) => ({ ...current, categoria: event.target.value }))
                    }
                    placeholder="Ex.: Operacional"
                    className="rounded-xl border-border/60 bg-card/60"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="despesa-descricao">Descrição</Label>
                  <Input
                    id="despesa-descricao"
                    value={formState.descricao}
                    onChange={(event) =>
                      setFormState((current) => ({ ...current, descricao: event.target.value }))
                    }
                    placeholder="Detalhe da despesa"
                    className="rounded-xl border-border/60 bg-card/60"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Valor</Label>
                  <InputCurrency
                    value={formState.valor}
                    onChange={(value) =>
                      setFormState((current) => ({ ...current, valor: value }))
                    }
                    placeholder="R$ 0,00"
                    className="h-11 rounded-xl border-border/60 bg-card/60"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Data da despesa</Label>
                  <DatePicker
                    value={formState.data_despesa}
                    onChange={(date) => setFormState((current) => ({ ...current, data_despesa: date }))}
                    className="rounded-xl"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Status financeiro</Label>
                  <Select
                    value={formState.status}
                    onValueChange={(value) =>
                      setFormState((current) => ({
                        ...current,
                        status: value,
                        data_pagamento: value === "pago" ? current.data_pagamento : undefined,
                      }))
                    }
                  >
                    <SelectTrigger
                      aria-label="Status financeiro"
                      className="h-11 w-full rounded-xl border-border/60 bg-card/60"
                    >
                      <SelectValue placeholder="Selecione o status" />
                    </SelectTrigger>
                    <SelectContent>
                      {statusFinanceiroOptions.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Data de pagamento</Label>
                  <DatePicker
                    value={formState.data_pagamento}
                    onChange={(date) => setFormState((current) => ({ ...current, data_pagamento: date }))}
                    disabled={formState.status !== "pago"}
                    className="rounded-xl"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Tipo</Label>
                  <Select
                    value={formState.tipo}
                    onValueChange={(value) =>
                      setFormState((current) => ({ ...current, tipo: value }))
                    }
                  >
                    <SelectTrigger
                      aria-label="Tipo"
                      className="h-11 w-full rounded-xl border-border/60 bg-card/60"
                    >
                      <SelectValue placeholder="Selecione o tipo" />
                    </SelectTrigger>
                    <SelectContent>
                      {tipoLancamentoOptions.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Recorrência</Label>
                  <Select
                    value={formState.recorrencia}
                    onValueChange={(value) =>
                      setFormState((current) => ({ ...current, recorrencia: value }))
                    }
                  >
                    <SelectTrigger
                      aria-label="Recorrência"
                      className="h-11 w-full rounded-xl border-border/60 bg-card/60"
                    >
                      <SelectValue placeholder="Selecione a recorrência" />
                    </SelectTrigger>
                    <SelectContent>
                      {recorrenciaOptions.map((option) => (
                        <SelectItem key={option.value} value={option.value}>
                          {option.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex items-center gap-3 rounded-2xl border border-border/60 bg-card/50 px-4 py-3 md:col-span-2">
                  <Checkbox
                    id="despesa-recorrencia-ativa"
                    checked={formState.recorrencia_ativa}
                    onCheckedChange={(checked) =>
                      setFormState((current) => ({
                        ...current,
                        recorrencia_ativa: checked === true,
                      }))
                    }
                  />
                  <Label htmlFor="despesa-recorrencia-ativa" className="cursor-pointer text-sm font-medium">
                    Recorrência ativa
                  </Label>
                </div>
                <div className="space-y-2 md:col-span-2">
                  <Label htmlFor="despesa-observacoes">Observações</Label>
                  <Textarea
                    id="despesa-observacoes"
                    value={formState.observacoes}
                    onChange={(event) =>
                      setFormState((current) => ({ ...current, observacoes: event.target.value }))
                    }
                    placeholder="Informações adicionais da despesa"
                    className="min-h-28 rounded-2xl border-border/60 bg-card/60"
                  />
                </div>
                <div className="space-y-3 md:col-span-2">
                  <div className="space-y-2">
                    <Label>Anexo do comprovante</Label>
                    <FileUploadDropzone
                      accept={comprovanteAccept}
                      file={formAttachment}
                      onUpload={setFormAttachment}
                      isProcessing={saveMutation.isPending}
                      emptyTitle={formState.id ? "Substituir comprovante neste lançamento" : "Anexar comprovante agora (opcional)"}
                      emptyDescription="PDF, PNG ou JPG com até 10 MB"
                    />
                  </div>

                  {existingFormAttachment && !formAttachment ? (
                    <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-100">
                      <p className="font-medium">Anexo atual: {existingFormAttachment.nome}</p>
                      {formAttachmentHref ? (
                        <a
                          href={formAttachmentHref}
                          target="_blank"
                          rel="noreferrer"
                          className="mt-1 inline-flex items-center gap-2 text-sm text-primary hover:underline"
                        >
                          <ExternalLinkIcon className="size-4" />
                          Abrir anexo atual
                        </a>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              </div>
              <div className="mt-4">
                {!formAttachment && !existingFormAttachment ? (
                  <div className="rounded-2xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
                    Sem anexo neste passo, a despesa ficará marcada como pendente de anexo até o envio do comprovante.
                  </div>
                ) : (
                  <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-100">
                    {formAttachment
                      ? "O comprovante será enviado junto com o lançamento."
                      : "Se salvar sem trocar o arquivo, o anexo atual será mantido."}
                  </div>
                )}
              </div>
          </div>

          <DialogFooter className="border-t border-border/60 px-6 py-4">
            <Button
              variant="outline"
              onClick={() => {
                setFormOpen(false);
                setFormState(initialFormState);
                setFormAttachment(null);
                setExistingFormAttachment(null);
              }}
            >
              Cancelar
            </Button>
            <Button
              onClick={() => saveMutation.mutate({ values: formState, attachment: formAttachment })}
              disabled={!canSubmitForm || saveMutation.isPending}
            >
              {saveMutation.isPending ? "Salvando..." : formState.id ? "Salvar alterações" : "Lançar despesa"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={!!uploadTarget}
        onOpenChange={(open) => {
          if (!open) {
            setUploadTarget(null);
            setUploadFile(null);
          }
        }}
      >
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{uploadTarget?.anexo ? "Substituir anexo" : "Anexar comprovante"}</DialogTitle>
            <DialogDescription>
              {uploadTarget?.descricao || "Selecione o comprovante da despesa."}
            </DialogDescription>
          </DialogHeader>

          {uploadTarget?.anexo ? (
            <div className="rounded-2xl border border-border/60 bg-card/50 px-4 py-3 text-sm">
              <p className="font-medium">Anexo atual: {uploadTarget.anexo.nome}</p>
              {uploadHref ? (
                <a
                  href={uploadHref}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-1 inline-flex items-center gap-2 text-sm text-primary hover:underline"
                >
                  <ExternalLinkIcon className="size-4" />
                  Abrir anexo atual
                </a>
              ) : null}
            </div>
          ) : (
            <div className="rounded-2xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">
              Esta despesa ainda está pendente de anexo.
            </div>
          )}

          <FileUploadDropzone
            accept={comprovanteAccept}
            file={uploadFile}
            onUpload={setUploadFile}
            isProcessing={uploadMutation.isPending}
            emptyTitle="Selecione o comprovante da despesa"
            emptyDescription="PDF, PNG ou JPG com até 10 MB"
          />

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setUploadTarget(null);
                setUploadFile(null);
              }}
            >
              Cancelar
            </Button>
            <Button
              disabled={!uploadTarget || !uploadFile || uploadMutation.isPending}
              onClick={() => {
                if (!uploadTarget || !uploadFile) {
                  return;
                }
                uploadMutation.mutate({ id: uploadTarget.id, file: uploadFile });
              }}
            >
              {uploadMutation.isPending ? "Enviando..." : "Salvar anexo"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog
        open={!!deleteTarget}
        onOpenChange={(open) => {
          if (!open) {
            setDeleteTarget(null);
            setDeleteConfirmed(false);
          }
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogMedia className="bg-rose-500/10 text-rose-200">
              <Trash2Icon className="size-8" />
            </AlertDialogMedia>
            <AlertDialogTitle>Excluir despesa</AlertDialogTitle>
            <AlertDialogDescription>
              {deleteTarget ? (
                <>
                  A despesa <strong>{deleteTarget.descricao}</strong> será removida da listagem
                  ativa da competência atual.
                </>
              ) : (
                "Confirme a exclusão da despesa selecionada."
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>

          <div className="space-y-4 rounded-2xl border border-border/60 bg-card/60 p-4">
            {deleteTarget ? (
              <>
                <div className="space-y-1 text-sm">
                  <p className="font-medium">{deleteTarget.categoria}</p>
                  <p className="text-muted-foreground">{formatCurrency(deleteTarget.valor)}</p>
                  <p className="text-muted-foreground">
                    Lançada em {formatDate(deleteTarget.data_despesa)}
                  </p>
                </div>
                <label className="flex items-start gap-3 text-sm text-muted-foreground">
                  <Checkbox
                    checked={deleteConfirmed}
                    onCheckedChange={(checked) => setDeleteConfirmed(Boolean(checked))}
                  />
                  <span>
                    Confirmo que revisei esta despesa e desejo excluí-la.
                  </span>
                </label>
              </>
            ) : null}
          </div>

          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              disabled={!deleteTarget || !deleteConfirmed || deleteMutation.isPending}
              onClick={(event) => {
                if (!deleteTarget || !deleteConfirmed) {
                  event.preventDefault();
                  return;
                }
                deleteMutation.mutate(deleteTarget.id, {
                  onSuccess: () => {
                    setDeleteTarget(null);
                    setDeleteConfirmed(false);
                  },
                });
              }}
            >
              Excluir despesa
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
