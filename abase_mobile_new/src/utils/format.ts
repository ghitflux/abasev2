// Utils de formatação — migrado do legado

export const onlyDigits = (s: string) => (s || '').replace(/\D+/g, '');
export const looksLikeEmail = (s: string) =>
  /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test((s || '').trim());

// Máscara CPF 000.000.000-00
export const maskCpf = (value: string) => {
  const d = onlyDigits(value).slice(0, 11);
  if (d.length <= 3) return d;
  if (d.length <= 6) return `${d.slice(0, 3)}.${d.slice(3)}`;
  if (d.length <= 9) return `${d.slice(0, 3)}.${d.slice(3, 6)}.${d.slice(6)}`;
  return `${d.slice(0, 3)}.${d.slice(3, 6)}.${d.slice(6, 9)}-${d.slice(9)}`;
};

// Máscara CNPJ 00.000.000/0000-00
export const maskCnpj = (cnpj?: string) => {
  const d = onlyDigits(cnpj || '').slice(0, 14).padStart(14, '0');
  return d.replace(/(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})/, '$1.$2.$3/$4-$5');
};

export const maskCpfHideMiddle = (cpf?: string) =>
  maskCpf(cpf || '').replace(/\d(?=\d{2})/g, '*');

export const maskCnpjHideMiddle = (cnpj?: string) =>
  maskCnpj(cnpj).replace(/\d(?=\d{2})/g, '*');

export const maskDocHideMiddle = (doc?: string) => {
  const d = onlyDigits(doc || '');
  return d.length <= 11 ? maskCpfHideMiddle(d) : maskCnpjHideMiddle(d);
};

// Formato moeda BR
export const moneyBR = (value: number | string | null | undefined) => {
  const n = Number(value ?? 0);
  if (isNaN(n)) return 'R$ 0,00';
  return n.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
};

// Formata telefone BR
export const formatPhoneBR = (raw?: string) => {
  const d = onlyDigits(raw || '');
  if (d.length >= 11) return d.replace(/(\d{2})(\d{1})(\d{4})(\d{4}).*/, '($1) $2 $3-$4');
  if (d.length === 10) return d.replace(/(\d{2})(\d{4})(\d{4}).*/, '($1) $2-$3');
  if (d.length === 9) return d.replace(/(\d{5})(\d{4}).*/, '$1-$2');
  if (d.length === 8) return d.replace(/(\d{4})(\d{4}).*/, '$1-$2');
  return raw || '';
};

// Primeiro nome em maiúsculas
export const firstNameUpper = (fullName?: string) => {
  if (!fullName) return '';
  return fullName.trim().split(/\s+/)[0].toUpperCase();
};

// Formata data BR (YYYY-MM-DD → DD/MM/YYYY)
export const formatDateBR = (iso?: string | null) => {
  if (!iso) return '';
  const parts = iso.slice(0, 10).split('-');
  if (parts.length !== 3) return iso;
  return `${parts[2]}/${parts[1]}/${parts[0]}`;
};

// Mês/ano abreviado (YYYY-MM-DD → MMM/YYYY)
export const formatMonthYear = (iso?: string | null) => {
  if (!iso) return '';
  const d = new Date(iso.slice(0, 10) + 'T00:00:00');
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('pt-BR', { month: 'short', year: 'numeric' });
};
