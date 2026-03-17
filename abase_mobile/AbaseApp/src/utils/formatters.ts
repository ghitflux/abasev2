/** Formata CPF: 000.000.000-00 */
export function formatCpf(value: string): string {
  const digits = value.replace(/\D/g, '').slice(0, 11);
  return digits
    .replace(/(\d{3})(\d)/, '$1.$2')
    .replace(/(\d{3})(\d)/, '$1.$2')
    .replace(/(\d{3})(\d{1,2})$/, '$1-$2');
}

/** Remove máscara do CPF */
export function cleanCpf(value: string): string {
  return value.replace(/\D/g, '');
}

/** Formata moeda BRL */
export function formatCurrency(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return 'R$ 0,00';
  const num = typeof value === 'string' ? parseFloat(value) : value;
  if (isNaN(num)) return 'R$ 0,00';
  return num.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

/** Formata data ISO para dd/mm/yyyy */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  const [year, month, day] = iso.split('-');
  return `${day}/${month}/${year}`;
}

/** Rótulo legível do status de parcela */
export function statusParcelaLabel(status: string): string {
  const map: Record<string, string> = {
    futuro: 'Futuro',
    em_aberto: 'Em aberto',
    descontado: 'Pago',
    nao_descontado: 'Não descontado',
    cancelado: 'Cancelado',
  };
  return map[status] ?? status;
}

/** Rótulo legível do status do associado */
export function statusAssociadoLabel(status: string): string {
  const map: Record<string, string> = {
    cadastrado: 'Cadastrado',
    em_analise: 'Em análise',
    ativo: 'Ativo',
    pendente: 'Pendente',
    inativo: 'Inativo',
    inadimplente: 'Inadimplente',
  };
  return map[status] ?? status;
}
