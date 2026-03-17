const onlyDigits = (value = "") => value.replace(/\D/g, "");

export function normalizeUppercaseAscii(value = "") {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toUpperCase();
}

export function maskCPF(value = "") {
  const digits = onlyDigits(value).slice(0, 11);
  return digits
    .replace(/^(\d{3})(\d)/, "$1.$2")
    .replace(/^(\d{3})\.(\d{3})(\d)/, "$1.$2.$3")
    .replace(/\.(\d{3})(\d)/, ".$1-$2");
}

export function maskCNPJ(value = "") {
  const digits = onlyDigits(value).slice(0, 14);
  return digits
    .replace(/^(\d{2})(\d)/, "$1.$2")
    .replace(/^(\d{2})\.(\d{3})(\d)/, "$1.$2.$3")
    .replace(/\.(\d{3})(\d)/, ".$1/$2")
    .replace(/(\d{4})(\d)/, "$1-$2");
}

export function maskCPFCNPJ(value = "") {
  const digits = onlyDigits(value);
  return digits.length <= 11 ? maskCPF(digits) : maskCNPJ(digits);
}

export function maskPhone(value = "") {
  const digits = onlyDigits(value).slice(0, 11);
  if (!digits) {
    return "";
  }

  const ddd = digits.slice(0, 2);
  const subscriber = digits.slice(2);

  if (digits.length <= 2) {
    return `(${ddd}`;
  }

  if (digits.length <= 10) {
    const prefix = subscriber.slice(0, 4);
    const suffix = subscriber.slice(4, 8);
    return suffix ? `(${ddd}) ${prefix}-${suffix}` : `(${ddd}) ${prefix}`;
  }

  const prefix = subscriber.slice(0, 1);
  const middle = subscriber.slice(1, 5);
  const suffix = subscriber.slice(5, 9);
  return suffix
    ? `(${ddd}) ${prefix} ${middle}-${suffix}`
    : middle
      ? `(${ddd}) ${prefix} ${middle}`
      : `(${ddd}) ${prefix}`;
}

export function maskPixKey(value = "") {
  const normalized = normalizeUppercaseAscii(value);
  const digits = onlyDigits(normalized);
  const hasAt = normalized.includes("@");
  const hasPhoneMarkers =
    normalized.includes("(") ||
    normalized.includes(")") ||
    normalized.startsWith("+");
  const hasCpfMarkers =
    normalized.includes(".") &&
    normalized.includes("-") &&
    !normalized.includes("/");
  const hasCnpjMarkers = normalized.includes("/");
  const looksNumeric = /^[0-9()./\-\s+]+$/.test(normalized);

  if (!normalized) {
    return "";
  }

  if (hasAt) {
    return normalized;
  }

  if (hasCnpjMarkers || digits.length > 11) {
    return maskCNPJ(digits);
  }

  if (hasCpfMarkers) {
    return maskCPF(digits);
  }

  if (hasPhoneMarkers) {
    return maskPhone(digits);
  }

  if (looksNumeric && digits.length === 11) {
    return validateCPF(digits) ? maskCPF(digits) : maskPhone(digits);
  }

  if (looksNumeric && digits.length === 10) {
    return maskPhone(digits);
  }

  return normalized;
}

export function maskCEP(value = "") {
  return onlyDigits(value).slice(0, 8).replace(/^(\d{5})(\d)/, "$1-$2");
}

export function maskDate(value = "") {
  const digits = onlyDigits(value).slice(0, 8);
  if (digits.length <= 2) {
    return digits;
  }
  if (digits.length <= 4) {
    return `${digits.slice(0, 2)}/${digits.slice(2)}`;
  }
  return `${digits.slice(0, 2)}/${digits.slice(2, 4)}/${digits.slice(4)}`;
}

export function maskMonthYear(value = "") {
  const digits = onlyDigits(value).slice(0, 6);
  if (digits.length <= 2) {
    return digits;
  }
  return `${digits.slice(0, 2)}/${digits.slice(2)}`;
}

export function maskCurrency(value: number | string = 0) {
  const cents =
    typeof value === "number" ? Math.max(value, 0) : Number(onlyDigits(value));
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format((Number.isNaN(cents) ? 0 : cents) / 100);
}

export function unmaskCurrency(value = "") {
  const cents = Number(onlyDigits(value));
  return Number.isNaN(cents) ? 0 : cents;
}

export function validateCPF(value = "") {
  const cpf = onlyDigits(value);
  if (cpf.length !== 11 || /^(\d)\1{10}$/.test(cpf)) {
    return false;
  }

  let sum = 0;
  for (let index = 0; index < 9; index += 1) {
    sum += Number(cpf[index]) * (10 - index);
  }

  let digit = (sum * 10) % 11;
  if (digit === 10) digit = 0;
  if (digit !== Number(cpf[9])) return false;

  sum = 0;
  for (let index = 0; index < 10; index += 1) {
    sum += Number(cpf[index]) * (11 - index);
  }

  digit = (sum * 10) % 11;
  if (digit === 10) digit = 0;
  return digit === Number(cpf[10]);
}

export function validateCNPJ(value = "") {
  const cnpj = onlyDigits(value);
  if (cnpj.length !== 14 || /^(\d)\1{13}$/.test(cnpj)) {
    return false;
  }

  const calculateDigit = (base: string, factors: number[]) => {
    const sum = base
      .split("")
      .reduce((total, digit, index) => total + Number(digit) * factors[index], 0);
    const remainder = sum % 11;
    return remainder < 2 ? 0 : 11 - remainder;
  };

  const firstDigit = calculateDigit(cnpj.slice(0, 12), [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]);
  const secondDigit = calculateDigit(cnpj.slice(0, 12) + String(firstDigit), [
    6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2,
  ]);

  return cnpj.endsWith(`${firstDigit}${secondDigit}`);
}

export { onlyDigits };
