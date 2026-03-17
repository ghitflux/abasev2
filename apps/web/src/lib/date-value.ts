import { format } from "date-fns";

function hasValidDateParts(date: Date, year: number, month: number, day: number) {
  return (
    date.getFullYear() === year &&
    date.getMonth() === month - 1 &&
    date.getDate() === day
  );
}

export function parseDateValue(value?: string | null) {
  if (!value) return undefined;

  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value.trim());
  if (!match) return undefined;

  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const parsed = new Date(year, month - 1, day);

  return hasValidDateParts(parsed, year, month, day) ? parsed : undefined;
}

export function formatDateValue(value?: Date | null) {
  return value ? format(value, "yyyy-MM-dd") : "";
}

export function parseMonthValue(value?: string | null) {
  if (!value) return undefined;

  const match = /^(\d{4})-(\d{2})$/.exec(value.trim());
  if (!match) return undefined;

  const year = Number(match[1]);
  const month = Number(match[2]);
  const parsed = new Date(year, month - 1, 1);

  return parsed.getFullYear() === year && parsed.getMonth() === month - 1 ? parsed : undefined;
}

export function formatMonthValue(value?: Date | null) {
  return value ? format(new Date(value.getFullYear(), value.getMonth(), 1), "yyyy-MM") : "";
}

export function parseDateTimeValue(value?: string | null) {
  if (!value) return undefined;

  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(value.trim());
  if (!match) {
    const fallback = new Date(value);
    return Number.isNaN(fallback.getTime()) ? undefined : fallback;
  }

  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const hours = Number(match[4]);
  const minutes = Number(match[5]);
  const parsed = new Date(year, month - 1, day, hours, minutes, 0, 0);

  return hasValidDateParts(parsed, year, month, day) ? parsed : undefined;
}

export function formatDateTimeValue(value?: Date | string | null) {
  if (!value) return "";
  const parsed = value instanceof Date ? value : parseDateTimeValue(value);
  if (!parsed || Number.isNaN(parsed.getTime())) return "";
  return format(parsed, "yyyy-MM-dd'T'HH:mm");
}
