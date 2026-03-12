import { format } from "date-fns";
import { ptBR } from "date-fns/locale";

export function formatCurrency(value?: number | string | null) {
  const numeric =
    typeof value === "number"
      ? value
      : value
        ? Number.parseFloat(String(value))
        : 0;

  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(Number.isNaN(numeric) ? 0 : numeric);
}

export function formatDate(value?: string | Date | null, fallback = "-") {
  if (!value) return fallback;
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return fallback;
  return format(date, "dd/MM/yyyy", { locale: ptBR });
}

export function formatDateTime(value?: string | Date | null, fallback = "-") {
  if (!value) return fallback;
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return fallback;
  return format(date, "dd/MM/yyyy HH:mm", { locale: ptBR });
}

export function formatMonthYear(value?: string | Date | null, fallback = "-") {
  if (!value) return fallback;
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return fallback;
  return format(date, "MMM/yyyy", { locale: ptBR });
}

export function formatLongMonthYear(value?: string | Date | null, fallback = "-") {
  if (!value) return fallback;
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return fallback;
  return format(date, "MMMM 'de' yyyy", { locale: ptBR });
}

export function formatMetricDelta(value: number) {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(1)}% vs mês anterior`;
}

export function decimalToCents(value?: string | number | null) {
  if (value === null || value === undefined || value === "") return null;
  const numeric = typeof value === "number" ? value : Number.parseFloat(String(value));
  if (Number.isNaN(numeric)) return null;
  return Math.round(numeric * 100);
}

export function centsToDecimal(value?: number | null) {
  if (value === null || value === undefined) return "0.00";
  return (value / 100).toFixed(2);
}
