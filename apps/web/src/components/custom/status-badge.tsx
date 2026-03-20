import { badgeVariants } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const STATUS_STYLES: Record<string, string> = {
  ativo: "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/30",
  aprovado: "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/30",
  ciclo_renovado:
    "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/30",
  concluido: "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/30",
  completa: "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/30",
  confirmado: "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/30",
  descontado: "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/30",
  efetivado: "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/30",
  averbacao_confirmada:
    "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/30",
  ligacao_recebida:
    "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/30",
  baixa_efetuada:
    "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/30",
  anexado: "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/30",
  pago: "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/30",
  aberto: "bg-sky-500/15 text-sky-300 ring-1 ring-sky-500/30",
  analise: "bg-sky-500/15 text-sky-300 ring-1 ring-sky-500/30",
  ciclo_iniciado: "bg-sky-500/15 text-sky-300 ring-1 ring-sky-500/30",
  em_analise: "bg-sky-500/15 text-sky-300 ring-1 ring-sky-500/30",
  em_analise_renovacao: "bg-sky-500/15 text-sky-300 ring-1 ring-sky-500/30",
  aprovado_para_renovacao:
    "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/30",
  pendente_apto: "bg-sky-500/15 text-sky-300 ring-1 ring-sky-500/30",
  em_aberto: "bg-amber-500/15 text-amber-300 ring-1 ring-amber-500/30",
  pendente: "bg-amber-500/15 text-amber-300 ring-1 ring-amber-500/30",
  processando: "bg-amber-500/15 text-amber-300 ring-1 ring-amber-500/30",
  pendencia_manual: "bg-amber-500/15 text-amber-300 ring-1 ring-amber-500/30",
  pendenciado: "bg-amber-500/15 text-amber-300 ring-1 ring-amber-500/30",
  congelado: "bg-amber-500/15 text-amber-300 ring-1 ring-amber-500/30",
  aguardando: "bg-amber-500/15 text-amber-300 ring-1 ring-amber-500/30",
  em_andamento: "bg-amber-500/15 text-amber-300 ring-1 ring-amber-500/30",
  futuro: "bg-amber-500/15 text-amber-300 ring-1 ring-amber-500/30",
  em_previsao: "bg-slate-500/15 text-slate-300 ring-1 ring-slate-500/30",
  reenvio_pendente: "bg-amber-500/15 text-amber-300 ring-1 ring-amber-500/30",
  tesouraria: "bg-amber-500/15 text-amber-300 ring-1 ring-amber-500/30",
  inadimplente: "bg-rose-500/15 text-rose-300 ring-1 ring-rose-500/30",
  incompleta: "bg-rose-500/15 text-rose-300 ring-1 ring-rose-500/30",
  nao_descontado: "bg-rose-500/15 text-rose-300 ring-1 ring-rose-500/30",
  nao_encontrado: "bg-rose-500/15 text-rose-300 ring-1 ring-rose-500/30",
  rejeitado: "bg-rose-500/15 text-rose-300 ring-1 ring-rose-500/30",
  erro: "bg-rose-500/15 text-rose-300 ring-1 ring-rose-500/30",
  cancelado: "bg-rose-500/15 text-rose-300 ring-1 ring-rose-500/30",
  bloqueado: "bg-slate-500/15 text-slate-300 ring-1 ring-slate-500/30",
  revertido: "bg-slate-500/15 text-slate-300 ring-1 ring-slate-500/30",
  fechado: "bg-slate-500/15 text-slate-300 ring-1 ring-slate-500/30",
  inativo: "bg-slate-500/15 text-slate-300 ring-1 ring-slate-500/30",
  suspenso: "bg-slate-500/15 text-slate-300 ring-1 ring-slate-500/30",
  desativado: "bg-slate-500/15 text-slate-300 ring-1 ring-slate-500/30",
  apto_a_renovar: "bg-sky-500/15 text-sky-300 ring-1 ring-sky-500/30",
  ciclo_aberto: "bg-sky-500/15 text-sky-300 ring-1 ring-sky-500/30",
};

type StatusBadgeProps = {
  status: string;
  label?: string;
  className?: string;
};

function resolveStatusStyle(status: string) {
  const normalized = status.toLowerCase();
  if (STATUS_STYLES[normalized]) {
    return STATUS_STYLES[normalized];
  }
  if (
    normalized === "contrato_desativado" ||
    normalized === "contrato_encerrado" ||
    normalized.includes("ciclo_desativado")
  ) {
    return "bg-slate-500/15 text-slate-300 ring-1 ring-slate-500/30";
  }
  if (normalized.includes("ciclo_inadimplente")) {
    return "bg-rose-500/15 text-rose-300 ring-1 ring-rose-500/30";
  }
  if (normalized.includes("ciclo_com_pendencia")) {
    return "bg-amber-500/15 text-amber-300 ring-1 ring-amber-500/30";
  }
  if (normalized.includes("ciclo_em_dia")) {
    return "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/30";
  }
  if (
    normalized.startsWith("em_analise") ||
    normalized.startsWith("apto_a_renovar") ||
    normalized.startsWith("ciclo_aberto") ||
    normalized.startsWith("renovacao_em_analise")
  ) {
    return "bg-sky-500/15 text-sky-300 ring-1 ring-sky-500/30";
  }
  return "bg-secondary text-secondary-foreground";
}

export default function StatusBadge({
  status,
  label,
  className,
}: StatusBadgeProps) {
  const normalized = status.toLowerCase();
  return (
    <span
      className={cn(
        badgeVariants({ variant: "secondary" }),
        "rounded-full border-transparent px-2.5 py-1 capitalize",
        resolveStatusStyle(normalized),
        className,
      )}
    >
      {label ?? normalized.replaceAll("__", " + ").replaceAll("_", " ")}
    </span>
  );
}
