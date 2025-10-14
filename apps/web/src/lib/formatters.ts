/**
 * Utility functions for formatting data
 */

/**
 * Format CPF with mask
 */
export function formatCPF(cpf: string): string {
  if (!cpf) return '';
  
  // Remove all non-numeric characters
  const numbers = cpf.replace(/\D/g, '');
  
  // Apply CPF mask: 000.000.000-00
  if (numbers.length <= 3) {
    return numbers;
  } else if (numbers.length <= 6) {
    return `${numbers.slice(0, 3)}.${numbers.slice(3)}`;
  } else if (numbers.length <= 9) {
    return `${numbers.slice(0, 3)}.${numbers.slice(3, 6)}.${numbers.slice(6)}`;
  } else {
    return `${numbers.slice(0, 3)}.${numbers.slice(3, 6)}.${numbers.slice(6, 9)}-${numbers.slice(9, 11)}`;
  }
}

/**
 * Remove CPF mask
 */
export function unformatCPF(cpf: string): string {
  return cpf.replace(/\D/g, '');
}

/**
 * Format CNPJ with mask
 */
export function formatCNPJ(cnpj: string): string {
  if (!cnpj) return '';
  
  // Remove all non-numeric characters
  const numbers = cnpj.replace(/\D/g, '');
  
  // Apply CNPJ mask: 00.000.000/0000-00
  if (numbers.length <= 2) {
    return numbers;
  } else if (numbers.length <= 5) {
    return `${numbers.slice(0, 2)}.${numbers.slice(2)}`;
  } else if (numbers.length <= 8) {
    return `${numbers.slice(0, 2)}.${numbers.slice(2, 5)}.${numbers.slice(5)}`;
  } else if (numbers.length <= 12) {
    return `${numbers.slice(0, 2)}.${numbers.slice(2, 5)}.${numbers.slice(5, 8)}/${numbers.slice(8)}`;
  } else {
    return `${numbers.slice(0, 2)}.${numbers.slice(2, 5)}.${numbers.slice(5, 8)}/${numbers.slice(8, 12)}-${numbers.slice(12, 14)}`;
  }
}

/**
 * Remove CNPJ mask
 */
export function unformatCNPJ(cnpj: string): string {
  return cnpj.replace(/\D/g, '');
}

/**
 * Format phone number with mask
 */
export function formatPhone(phone: string): string {
  if (!phone) return '';
  
  // Remove all non-numeric characters
  const numbers = phone.replace(/\D/g, '');
  
  // Apply phone mask: (00) 00000-0000 or (00) 0000-0000
  if (numbers.length <= 2) {
    return numbers;
  } else if (numbers.length <= 6) {
    return `(${numbers.slice(0, 2)}) ${numbers.slice(2)}`;
  } else if (numbers.length <= 10) {
    return `(${numbers.slice(0, 2)}) ${numbers.slice(2, 6)}-${numbers.slice(6)}`;
  } else {
    return `(${numbers.slice(0, 2)}) ${numbers.slice(2, 7)}-${numbers.slice(7, 11)}`;
  }
}

/**
 * Remove phone mask
 */
export function unformatPhone(phone: string): string {
  return phone.replace(/\D/g, '');
}

/**
 * Format currency (Brazilian Real)
 */
export function formatCurrency(value: number | string): string {
  if (value === null || value === undefined || value === '') return 'R$ 0,00';
  
  const numValue = typeof value === 'string' ? parseFloat(value) : value;
  
  if (isNaN(numValue)) return 'R$ 0,00';
  
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  }).format(numValue);
}

/**
 * Format number with Brazilian locale
 */
export function formatNumber(value: number | string, decimals: number = 2): string {
  if (value === null || value === undefined || value === '') return '0,00';
  
  const numValue = typeof value === 'string' ? parseFloat(value) : value;
  
  if (isNaN(numValue)) return '0,00';
  
  return new Intl.NumberFormat('pt-BR', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(numValue);
}

/**
 * Format percentage
 */
export function formatPercentage(value: number | string, decimals: number = 1): string {
  if (value === null || value === undefined || value === '') return '0,0%';
  
  const numValue = typeof value === 'string' ? parseFloat(value) : value;
  
  if (isNaN(numValue)) return '0,0%';
  
  return new Intl.NumberFormat('pt-BR', {
    style: 'percent',
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(numValue / 100);
}

/**
 * Format date to Brazilian format
 */
export function formatDate(date: Date | string | null | undefined): string {
  if (!date) return '';
  
  const dateObj = typeof date === 'string' ? new Date(date) : date;
  
  if (isNaN(dateObj.getTime())) return '';
  
  return new Intl.DateTimeFormat('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }).format(dateObj);
}

/**
 * Format date and time to Brazilian format
 */
export function formatDateTime(date: Date | string | null | undefined): string {
  if (!date) return '';
  
  const dateObj = typeof date === 'string' ? new Date(date) : date;
  
  if (isNaN(dateObj.getTime())) return '';
  
  return new Intl.DateTimeFormat('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(dateObj);
}

/**
 * Format date to ISO string for form inputs
 */
export function formatDateForInput(date: Date | string | null | undefined): string {
  if (!date) return '';
  
  const dateObj = typeof date === 'string' ? new Date(date) : date;
  
  if (isNaN(dateObj.getTime())) return '';
  
  return dateObj.toISOString().split('T')[0];
}

/**
 * Format relative time (e.g., "2 horas atrás")
 */
export function formatRelativeTime(date: Date | string | null | undefined): string {
  if (!date) return '';
  
  const dateObj = typeof date === 'string' ? new Date(date) : date;
  
  if (isNaN(dateObj.getTime())) return '';
  
  const now = new Date();
  const diffInSeconds = Math.floor((now.getTime() - dateObj.getTime()) / 1000);
  
  if (diffInSeconds < 60) {
    return 'agora mesmo';
  }
  
  const diffInMinutes = Math.floor(diffInSeconds / 60);
  if (diffInMinutes < 60) {
    return `${diffInMinutes} minuto${diffInMinutes > 1 ? 's' : ''} atrás`;
  }
  
  const diffInHours = Math.floor(diffInMinutes / 60);
  if (diffInHours < 24) {
    return `${diffInHours} hora${diffInHours > 1 ? 's' : ''} atrás`;
  }
  
  const diffInDays = Math.floor(diffInHours / 24);
  if (diffInDays < 30) {
    return `${diffInDays} dia${diffInDays > 1 ? 's' : ''} atrás`;
  }
  
  const diffInMonths = Math.floor(diffInDays / 30);
  if (diffInMonths < 12) {
    return `${diffInMonths} mês${diffInMonths > 1 ? 'es' : ''} atrás`;
  }
  
  const diffInYears = Math.floor(diffInMonths / 12);
  return `${diffInYears} ano${diffInYears > 1 ? 's' : ''} atrás`;
}

/**
 * Format file size
 */
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 Bytes';
  
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * Format status text
 */
export function formatStatus(status: string): string {
  const statusMap: Record<string, string> = {
    // Cadastro statuses
    'RASCUNHO': 'Rascunho',
    'SUBMETIDO': 'Submetido',
    'EM_ANALISE': 'Em Análise',
    'APROVADO': 'Aprovado',
    'PENDENTE': 'Pendente',
    'CANCELADO': 'Cancelado',
    'PAGAMENTO_PENDENTE': 'Pagamento Pendente',
    'PAGAMENTO_RECEBIDO': 'Pagamento Recebido',
    'CONTRATO_GERADO': 'Contrato Gerado',
    'ENVIADO_ASSINATURA': 'Enviado para Assinatura',
    'ASSINADO': 'Assinado',
    'CONCLUIDO': 'Concluído',
    
    // Generic statuses
    'ACTIVE': 'Ativo',
    'INACTIVE': 'Inativo',
    'PENDING': 'Pendente',
    'COMPLETED': 'Concluído',
    'FAILED': 'Falhou',
    'CANCELLED': 'Cancelado',
  };
  
  return statusMap[status.toUpperCase()] || status;
}

/**
 * Format name (capitalize first letter of each word)
 */
export function formatName(name: string): string {
  if (!name) return '';
  
  return name
    .toLowerCase()
    .split(' ')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

/**
 * Truncate text with ellipsis
 */
export function truncateText(text: string, maxLength: number): string {
  if (!text || text.length <= maxLength) return text;
  
  return text.slice(0, maxLength).trim() + '...';
}

/**
 * Format CEP (Brazilian postal code)
 */
export function formatCEP(cep: string): string {
  if (!cep) return '';
  
  // Remove all non-numeric characters
  const numbers = cep.replace(/\D/g, '');
  
  // Apply CEP mask: 00000-000
  if (numbers.length <= 5) {
    return numbers;
  } else {
    return `${numbers.slice(0, 5)}-${numbers.slice(5, 8)}`;
  }
}

/**
 * Remove CEP mask
 */
export function unformatCEP(cep: string): string {
  return cep.replace(/\D/g, '');
}
