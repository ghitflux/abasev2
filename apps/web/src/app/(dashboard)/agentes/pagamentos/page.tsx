"use client";

import * as React from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import {
  BadgeCheckIcon,
  BriefcaseBusinessIcon,
  HandCoinsIcon,
  PaperclipIcon,
} from "lucide-react";
import { toast } from "sonner";

import type {
  PagamentoAgenteItem,
  PagamentoAgenteNotificacoes,
  PagamentoAgenteResumo,
  PaginatedPagamentosAgenteResponse,
} from "@/lib/api/types";
import { apiFetch } from "@/lib/api/client";
import { parseMonthValue } from "@/lib/date-value";
import { formatCurrency } from "@/lib/formatters";
import { exportPaginatedRouteReport } from "@/lib/reports";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { usePermissions } from "@/hooks/use-permissions";
import { useRouteTransition } from "@/providers/route-transition-provider";
import CalendarCompetencia from "@/components/custom/calendar-competencia";
import {
  ASSOCIADO_STATUS_OPTIONS,
  buildPagamentoColumns,
  EMPTY_RESUMO,
  NUMERO_CICLOS_OPTIONS,
  PAGAMENTO_INICIAL_OPTIONS,
  PagamentoExpandido,
  PRESET_OPTIONS,
  resolveCount,
  STATUS_OPTIONS,
} from "@/components/pagamentos/pagamentos-shared";
import DataTable from "@/components/shared/data-table";
import ExportButton from "@/components/shared/export-button";
import { MetricCardSkeleton } from "@/components/shared/page-skeletons";
import StatsCard from "@/components/shared/stats-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export default function PagamentosPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { startRouteTransition } = useRouteTransition();
  const { hasRole, status } = usePermissions();
  const shouldRedirectToTesouraria =
    status === "authenticated" && (hasRole("ADMIN") || hasRole("TESOUREIRO"));

  const [search, setSearch] = React.useState("");
  const [statusFiltro, setStatusFiltro] = React.useState("todos");
  const [mes, setMes] = React.useState("");
  const [agente, setAgente] = React.useState("");
  const [associadoStatus, setAssociadoStatus] = React.useState("todos");
  const [pagamentoInicialStatus, setPagamentoInicialStatus] = React.useState("todos");
  const [numeroCiclos, setNumeroCiclos] = React.useState("todos");
  const [preset, setPreset] = React.useState("todos");
  const [dataInicio, setDataInicio] = React.useState("");
  const [dataFim, setDataFim] = React.useState("");
  const [pageSize, setPageSize] = React.useState("15");
  const [page, setPage] = React.useState(1);
  const [isExporting, setIsExporting] = React.useState(false);

  const debouncedSearch = useDebouncedValue(search, 300);
  const debouncedAgente = useDebouncedValue(agente, 300);
  const markedUnreadCountRef = React.useRef(0);

  React.useEffect(() => {
    if (!shouldRedirectToTesouraria) {
      return;
    }
    startRouteTransition("/tesouraria/pagamentos");
    router.replace("/tesouraria/pagamentos");
  }, [router, shouldRedirectToTesouraria, startRouteTransition]);

  const query = useQuery({
    queryKey: [
      "agente-pagamentos",
      page,
      pageSize,
      debouncedSearch,
      statusFiltro,
      mes,
      debouncedAgente,
      associadoStatus,
      pagamentoInicialStatus,
      numeroCiclos,
      preset,
      dataInicio,
      dataFim,
    ],
    queryFn: () =>
      apiFetch<PaginatedPagamentosAgenteResponse>("agente/pagamentos", {
        query: {
          page,
          page_size: Number(pageSize),
          search: debouncedSearch || undefined,
          status: statusFiltro === "todos" ? undefined : statusFiltro,
          mes: mes || undefined,
          agente: debouncedAgente || undefined,
          associado_status: associadoStatus === "todos" ? undefined : associadoStatus,
          pagamento_inicial_status:
            pagamentoInicialStatus === "todos" ? undefined : pagamentoInicialStatus,
          numero_ciclos: numeroCiclos === "todos" ? undefined : numeroCiclos,
          preset: preset === "todos" ? undefined : preset,
          data_inicio: dataInicio || undefined,
          data_fim: dataFim || undefined,
        },
      }),
    enabled: !shouldRedirectToTesouraria,
  });

  const notificacoesQuery = useQuery({
    queryKey: ["agente-pagamentos-notificacoes"],
    enabled: status === "authenticated" && hasRole("AGENTE") && !shouldRedirectToTesouraria,
    queryFn: () =>
      apiFetch<PagamentoAgenteNotificacoes>("agente/pagamentos/notificacoes"),
  });

  React.useEffect(() => {
    const unreadCount = notificacoesQuery.data?.unread_count ?? 0;
    if (!unreadCount || unreadCount === markedUnreadCountRef.current) {
      if (!unreadCount) {
        markedUnreadCountRef.current = 0;
      }
      return;
    }

    markedUnreadCountRef.current = unreadCount;
    void apiFetch<{ marked_count: number }>("agente/pagamentos/notificacoes/marcar-lidas", {
      method: "POST",
    }).then(() => {
      void queryClient.invalidateQueries({
        queryKey: ["agente-pagamentos-notificacoes"],
      });
    });
  }, [notificacoesQuery.data?.unread_count, queryClient]);

  const rows = query.data?.results ?? [];
  const resumo: PagamentoAgenteResumo = {
    total: resolveCount(query.data?.resumo?.total ?? EMPTY_RESUMO.total),
    efetivados: resolveCount(query.data?.resumo?.efetivados ?? EMPTY_RESUMO.efetivados),
    com_anexos: resolveCount(query.data?.resumo?.com_anexos ?? EMPTY_RESUMO.com_anexos),
    parcelas_pagas: resolveCount(query.data?.resumo?.parcelas_pagas ?? EMPTY_RESUMO.parcelas_pagas),
    parcelas_total: resolveCount(query.data?.resumo?.parcelas_total ?? EMPTY_RESUMO.parcelas_total),
  };
  const totalPages = Math.max(1, Math.ceil((query.data?.count ?? 0) / Number(pageSize)));
  const columns = React.useMemo(() => buildPagamentoColumns(), []);

  const handleExport = React.useCallback(
    async (format: "csv" | "pdf" | "excel" | "xlsx") => {
      if (format !== "pdf" && format !== "xlsx") {
        return;
      }

      setIsExporting(true);
      try {
        await exportPaginatedRouteReport<PagamentoAgenteItem>({
          route: "/agentes/pagamentos",
          format,
          sourcePath: "agente/pagamentos",
          sourceQuery: {
            search: debouncedSearch || undefined,
            status: statusFiltro === "todos" ? undefined : statusFiltro,
            mes: mes || undefined,
            agente: debouncedAgente || undefined,
            associado_status: associadoStatus === "todos" ? undefined : associadoStatus,
            pagamento_inicial_status:
              pagamentoInicialStatus === "todos" ? undefined : pagamentoInicialStatus,
            numero_ciclos: numeroCiclos === "todos" ? undefined : numeroCiclos,
            preset: preset === "todos" ? undefined : preset,
            data_inicio: dataInicio || undefined,
            data_fim: dataFim || undefined,
          },
          mapRow: (row) => ({
            contrato_codigo: row.contrato_codigo,
            nome: row.nome,
            agente_nome: row.agente_nome,
            data_solicitacao: row.data_solicitacao,
            status_visual_label: row.status_visual_label,
            pagamento_inicial_status_label: row.pagamento_inicial_status_label,
            pagamento_inicial_valor: row.pagamento_inicial_valor,
            cancelamento_tipo: row.cancelamento_tipo ?? "",
            cancelamento_motivo: row.cancelamento_motivo ?? "",
          }),
        });
      } catch (error) {
        toast.error(error instanceof Error ? error.message : "Falha ao exportar pagamentos.");
      } finally {
        setIsExporting(false);
      }
    },
    [
      associadoStatus,
      dataFim,
      dataInicio,
      debouncedAgente,
      debouncedSearch,
      mes,
      numeroCiclos,
      pagamentoInicialStatus,
      preset,
      statusFiltro,
    ],
  );

  if (shouldRedirectToTesouraria) {
    return <div className="min-h-[40vh]" />;
  }

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {query.isLoading && !query.data ? (
          Array.from({ length: 4 }).map((_, index) => <MetricCardSkeleton key={index} />)
        ) : (
          <>
            <StatsCard
              title="Contratos com repasse"
              value={resolveCount(resumo.total).toLocaleString("pt-BR")}
              delta={`${resolveCount(resumo.efetivados).toLocaleString("pt-BR")} efetivados no recorte`}
              icon={BriefcaseBusinessIcon}
              tone="neutral"
            />
            <StatsCard
              title="Efetivados"
              value={resolveCount(resumo.efetivados).toLocaleString("pt-BR")}
              delta="Pagamentos iniciais já confirmados"
              icon={BadgeCheckIcon}
              tone="positive"
            />
            <StatsCard
              title="Com anexos"
              value={resolveCount(resumo.com_anexos).toLocaleString("pt-BR")}
              delta="Contratos com evidência disponível"
              icon={PaperclipIcon}
              tone="neutral"
            />
            <StatsCard
              title="Parcelas pagas"
              value={`${resolveCount(resumo.parcelas_pagas).toLocaleString("pt-BR")}/${resolveCount(resumo.parcelas_total).toLocaleString("pt-BR")}`}
              delta={`${Math.max(resolveCount(resumo.parcelas_total) - resolveCount(resumo.parcelas_pagas), 0).toLocaleString("pt-BR")} ainda pendentes`}
              icon={HandCoinsIcon}
              tone="positive"
            />
          </>
        )}
      </section>

      <section className="grid gap-3 rounded-[1.75rem] border border-border/60 bg-card/50 p-4 xl:grid-cols-[minmax(0,1.3fr)_repeat(6,minmax(0,0.72fr))_auto_auto]">
        <Input
          value={search}
          onChange={(event) => {
            setSearch(event.target.value);
            setPage(1);
          }}
          placeholder="Nome, CPF, matrícula ou código do contrato..."
          className="rounded-2xl border-border/60 bg-card/60"
        />
        <Input
          value={agente}
          onChange={(event) => {
            setAgente(event.target.value);
            setPage(1);
          }}
          placeholder="Filtrar por agente"
          className="rounded-2xl border-border/60 bg-card/60"
        />
        <Select
          value={statusFiltro}
          onValueChange={(value) => {
            setStatusFiltro(value);
            setPage(1);
          }}
        >
          <SelectTrigger className="rounded-2xl bg-card/60">
            <SelectValue placeholder="Todos status" />
          </SelectTrigger>
          <SelectContent>
            {STATUS_OPTIONS.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select
          value={associadoStatus}
          onValueChange={(value) => {
            setAssociadoStatus(value);
            setPage(1);
          }}
        >
          <SelectTrigger className="rounded-2xl bg-card/60">
            <SelectValue placeholder="Status do associado" />
          </SelectTrigger>
          <SelectContent>
            {ASSOCIADO_STATUS_OPTIONS.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select
          value={preset}
          onValueChange={(value) => {
            setPreset(value);
            setPage(1);
          }}
        >
          <SelectTrigger className="rounded-2xl bg-card/60">
            <SelectValue placeholder="Fila operacional" />
          </SelectTrigger>
          <SelectContent>
            {PRESET_OPTIONS.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select
          value={pagamentoInicialStatus}
          onValueChange={(value) => {
            setPagamentoInicialStatus(value);
            setPage(1);
          }}
        >
          <SelectTrigger className="rounded-2xl bg-card/60">
            <SelectValue placeholder="Pagamento inicial" />
          </SelectTrigger>
          <SelectContent>
            {PAGAMENTO_INICIAL_OPTIONS.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select
          value={numeroCiclos}
          onValueChange={(value) => {
            setNumeroCiclos(value);
            setPage(1);
          }}
        >
          <SelectTrigger className="rounded-2xl bg-card/60">
            <SelectValue placeholder="Número de ciclos" />
          </SelectTrigger>
          <SelectContent>
            {NUMERO_CICLOS_OPTIONS.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <CalendarCompetencia
          value={parseMonthValue(mes)}
          onChange={(value) => {
            setMes(`${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}`);
            setPage(1);
          }}
          className="rounded-2xl"
        />
        <Input
          type="date"
          value={dataInicio}
          onChange={(event) => {
            setDataInicio(event.target.value);
            setPage(1);
          }}
          className="rounded-2xl border-border/60 bg-card/60"
        />
        <Input
          type="date"
          value={dataFim}
          onChange={(event) => {
            setDataFim(event.target.value);
            setPage(1);
          }}
          className="rounded-2xl border-border/60 bg-card/60"
        />
        <Select
          value={pageSize}
          onValueChange={(value) => {
            setPageSize(value);
            setPage(1);
          }}
        >
          <SelectTrigger className="rounded-2xl bg-card/60">
            <SelectValue placeholder="15" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="15">15 / página</SelectItem>
            <SelectItem value="30">30 / página</SelectItem>
            <SelectItem value="50">50 / página</SelectItem>
          </SelectContent>
        </Select>
        <Button onClick={() => setPage(1)}>Aplicar</Button>
        <Button
          variant="outline"
          onClick={() => {
            setSearch("");
            setStatusFiltro("todos");
            setMes("");
            setAgente("");
            setAssociadoStatus("todos");
            setPagamentoInicialStatus("todos");
            setNumeroCiclos("todos");
            setPreset("todos");
            setDataInicio("");
            setDataFim("");
            setPageSize("15");
            setPage(1);
          }}
        >
          Limpar
        </Button>
        <ExportButton
          disabled={isExporting}
          label={isExporting ? "Exportando..." : "Exportar"}
          onExport={(format) => void handleExport(format)}
        />
      </section>

      {query.isError ? (
        <div className="rounded-[1.75rem] border border-destructive/40 bg-destructive/10 px-6 py-5 text-sm text-destructive">
          {query.error instanceof Error
            ? query.error.message
            : "Falha ao carregar pagamentos do agente."}
        </div>
      ) : (
        <DataTable
          data={rows}
          columns={columns}
          renderExpanded={(row) => <PagamentoExpandido row={row} />}
          currentPage={page}
          totalPages={totalPages}
          onPageChange={setPage}
          emptyMessage="Nenhum contrato encontrado para os filtros informados."
          loading={query.isLoading}
          skeletonRows={6}
        />
      )}
    </div>
  );
}
