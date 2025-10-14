"use client";

import React from 'react';
import { Chip } from '@heroui/react';
import { cn } from '../../utils/cn';

export type StatusType = 
  | 'success' 
  | 'warning' 
  | 'danger' 
  | 'primary' 
  | 'secondary' 
  | 'default'
  | 'pending'
  | 'approved'
  | 'rejected'
  | 'cancelled'
  | 'completed'
  | 'in_progress';

export interface StatusBadgeProps {
  status: StatusType | string;
  label?: string;
  size?: 'sm' | 'md' | 'lg';
  variant?: 'solid' | 'bordered' | 'light' | 'flat' | 'faded' | 'shadow' | 'dot';
  className?: string;
  showIcon?: boolean;
  customColors?: {
    bg?: string;
    text?: string;
    border?: string;
  };
}

const statusConfig: Record<string, {
  color: 'success' | 'warning' | 'danger' | 'primary' | 'secondary' | 'default';
  label: string;
  icon?: string;
}> = {
  // Generic statuses
  success: { color: 'success', label: 'Sucesso', icon: '✓' },
  warning: { color: 'warning', label: 'Atenção', icon: '⚠' },
  danger: { color: 'danger', label: 'Erro', icon: '✗' },
  primary: { color: 'primary', label: 'Principal', icon: '●' },
  secondary: { color: 'secondary', label: 'Secundário', icon: '●' },
  default: { color: 'default', label: 'Padrão', icon: '●' },
  
  // Business statuses
  pending: { color: 'warning', label: 'Pendente', icon: '⏳' },
  approved: { color: 'success', label: 'Aprovado', icon: '✓' },
  rejected: { color: 'danger', label: 'Rejeitado', icon: '✗' },
  cancelled: { color: 'danger', label: 'Cancelado', icon: '✗' },
  completed: { color: 'success', label: 'Concluído', icon: '✓' },
  in_progress: { color: 'primary', label: 'Em Andamento', icon: '⟳' },
  
  // Cadastro specific statuses
  RASCUNHO: { color: 'default', label: 'Rascunho', icon: '📝' },
  SUBMETIDO: { color: 'primary', label: 'Submetido', icon: '📤' },
  EM_ANALISE: { color: 'warning', label: 'Em Análise', icon: '🔍' },
  APROVADO: { color: 'success', label: 'Aprovado', icon: '✓' },
  PENDENTE: { color: 'warning', label: 'Pendente', icon: '⏳' },
  CANCELADO: { color: 'danger', label: 'Cancelado', icon: '✗' },
  PAGAMENTO_PENDENTE: { color: 'warning', label: 'Pagamento Pendente', icon: '💰' },
  PAGAMENTO_RECEBIDO: { color: 'primary', label: 'Pagamento Recebido', icon: '✓' },
  CONTRATO_GERADO: { color: 'primary', label: 'Contrato Gerado', icon: '📄' },
  ENVIADO_ASSINATURA: { color: 'primary', label: 'Enviado para Assinatura', icon: '✍️' },
  ASSINADO: { color: 'success', label: 'Assinado', icon: '✓' },
  CONCLUIDO: { color: 'success', label: 'Concluído', icon: '🎉' },
};

export function StatusBadge({
  status,
  label,
  size = 'md',
  variant = 'flat',
  className,
  showIcon = true,
  customColors,
}: StatusBadgeProps) {
  const config = statusConfig[status.toUpperCase()] || statusConfig[status.toLowerCase()] || {
    color: 'default' as const,
    label: status,
    icon: '●'
  };

  const displayLabel = label || config.label;
  const displayIcon = showIcon ? config.icon : undefined;

  // Custom colors override
  if (customColors) {
    return (
      <Chip
        size={size}
        variant={variant}
        className={cn(
          customColors.bg && `bg-${customColors.bg}`,
          customColors.text && `text-${customColors.text}`,
          customColors.border && `border-${customColors.border}`,
          className
        )}
        startContent={displayIcon && <span className="text-xs">{displayIcon}</span>}
      >
        {displayLabel}
      </Chip>
    );
  }

  return (
    <Chip
      color={config.color}
      size={size}
      variant={variant}
      className={className}
      startContent={displayIcon && <span className="text-xs">{displayIcon}</span>}
    >
      {displayLabel}
    </Chip>
  );
}

// Convenience components for common statuses
export function PendingBadge(props: Omit<StatusBadgeProps, 'status'>) {
  return <StatusBadge {...props} status="pending" />;
}

export function ApprovedBadge(props: Omit<StatusBadgeProps, 'status'>) {
  return <StatusBadge {...props} status="approved" />;
}

export function RejectedBadge(props: Omit<StatusBadgeProps, 'status'>) {
  return <StatusBadge {...props} status="rejected" />;
}

export function CompletedBadge(props: Omit<StatusBadgeProps, 'status'>) {
  return <StatusBadge {...props} status="completed" />;
}

export function InProgressBadge(props: Omit<StatusBadgeProps, 'status'>) {
  return <StatusBadge {...props} status="in_progress" />;
}
