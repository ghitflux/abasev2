const ISO_DATE_ONLY_RE = /^(\d{4})-(\d{2})-(\d{2})$/;
const ISO_MONTH_ONLY_RE = /^(\d{4})-(\d{2})$/;
const APP_TIME_ZONE = "America/Fortaleza";

function getFormatter(options: Intl.DateTimeFormatOptions) {
  return new Intl.DateTimeFormat("pt-BR", {
    timeZone: APP_TIME_ZONE,
    ...options,
  });
}

const DATE_FORMATTER = getFormatter({
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
});

const DATETIME_FORMATTER = getFormatter({
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

const MONTH_YEAR_FORMATTER = getFormatter({
  month: "short",
  year: "numeric",
});

const LONG_MONTH_YEAR_FORMATTER = getFormatter({
  month: "long",
  year: "numeric",
});

function parseDisplayDate(value: string | Date) {
  if (value instanceof Date) return value;

  const isoDateMatch = ISO_DATE_ONLY_RE.exec(value);
  if (isoDateMatch) {
    return new Date(
      Number(isoDateMatch[1]),
      Number(isoDateMatch[2]) - 1,
      Number(isoDateMatch[3]),
      12,
      0,
      0,
      0,
    );
  }

  const isoMonthMatch = ISO_MONTH_ONLY_RE.exec(value);
  if (isoMonthMatch) {
    return new Date(
      Number(isoMonthMatch[1]),
      Number(isoMonthMatch[2]) - 1,
      1,
      12,
      0,
      0,
      0,
    );
  }

  return new Date(value);
}

function getPart(
  formatter: Intl.DateTimeFormat,
  value: Date,
  type: Intl.DateTimeFormatPartTypes,
) {
  return formatter.formatToParts(value).find((part) => part.type === type)?.value ?? "";
}

function formatShortMonth(value: Date) {
  return getPart(MONTH_YEAR_FORMATTER, value, "month").replace(".", "").toLowerCase();
}

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
  const date = parseDisplayDate(value);
  if (Number.isNaN(date.getTime())) return fallback;
  const day = getPart(DATE_FORMATTER, date, "day");
  const month = getPart(DATE_FORMATTER, date, "month");
  const year = getPart(DATE_FORMATTER, date, "year");
  return `${day}/${month}/${year}`;
}

export function formatDateTime(value?: string | Date | null, fallback = "-") {
  if (!value) return fallback;
  const date = parseDisplayDate(value);
  if (Number.isNaN(date.getTime())) return fallback;
  const day = getPart(DATETIME_FORMATTER, date, "day");
  const month = getPart(DATETIME_FORMATTER, date, "month");
  const year = getPart(DATETIME_FORMATTER, date, "year");
  const hour = getPart(DATETIME_FORMATTER, date, "hour");
  const minute = getPart(DATETIME_FORMATTER, date, "minute");
  return `${day}/${month}/${year} ${hour}:${minute}`;
}

export function formatMonthYear(value?: string | Date | null, fallback = "-") {
  if (!value) return fallback;
  const date = parseDisplayDate(value);
  if (Number.isNaN(date.getTime())) return fallback;
  const year = getPart(MONTH_YEAR_FORMATTER, date, "year");
  return `${formatShortMonth(date)}/${year}`;
}

export function formatLongMonthYear(value?: string | Date | null, fallback = "-") {
  if (!value) return fallback;
  const date = parseDisplayDate(value);
  if (Number.isNaN(date.getTime())) return fallback;
  return LONG_MONTH_YEAR_FORMATTER.format(date).toLowerCase();
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
