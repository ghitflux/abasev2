export function startOfLocalDay(value: Date) {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate());
}

export function parseIsoDate(value?: string | null) {
  if (!value) {
    return undefined;
  }

  const [year, month, day] = value.split("-").map(Number);
  if (!year || !month || !day) {
    return undefined;
  }

  return new Date(year, month - 1, day);
}

export function addMonths(date: Date, months: number) {
  const monthIndex = date.getMonth() + months;
  const year = date.getFullYear() + Math.floor(monthIndex / 12);
  const month = ((monthIndex % 12) + 12) % 12;
  const lastDay = new Date(year, month + 1, 0).getDate();
  return new Date(year, month, Math.min(date.getDate(), lastDay));
}

export function getMonthlyChargeDate(monthDate: Date, targetDay = 5) {
  return startOfLocalDay(new Date(monthDate.getFullYear(), monthDate.getMonth(), targetDay));
}

export function calculateContratoDates(approvalDate?: Date, fallbackDate?: Date) {
  const baseDate = approvalDate
    ? startOfLocalDay(approvalDate)
    : fallbackDate
      ? startOfLocalDay(fallbackDate)
      : undefined;

  if (!baseDate) {
    return {
      dataAprovacao: undefined,
      dataPrimeiraMensalidade: undefined,
      mesAverbacao: undefined,
    };
  }

  const mesBase = new Date(baseDate.getFullYear(), baseDate.getMonth(), 1);
  const mesAverbacao =
    baseDate.getDate() <= 5 ? mesBase : addMonths(mesBase, 1);
  const mesPrimeiraMensalidade = addMonths(mesAverbacao, 1);
  const dataPrimeiraMensalidade = getMonthlyChargeDate(mesPrimeiraMensalidade);

  return {
    dataAprovacao: baseDate,
    dataPrimeiraMensalidade,
    mesAverbacao,
  };
}

export function formatMonthYear(value?: Date) {
  if (!value) {
    return "";
  }

  return `${String(value.getMonth() + 1).padStart(2, "0")}/${value.getFullYear()}`;
}
