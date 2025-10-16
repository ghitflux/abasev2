"use client";

import React from 'react';
import { Chip } from '@heroui/react';
import { cn } from '../../utils/cn';
import {
  CheckCircle,
  XCircle,
  AlertCircle,
  Clock,
  RefreshCw,
  FileText,
  Send,
  Edit,
  Check,
  Rocket,
} from '../../icons';

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
  icon?: React.ReactNode;
}> = {
  // Generic statuses
  success: { color: 'success', label: 'Sucesso', icon: <CheckCircle className="w-3 h-3" /> },
  warning: { color: 'warning', label: 'Atenção', icon: <AlertCircle className="w-3 h-3" /> },
  danger: { color: 'danger', label: 'Erro', icon: <XCircle className="w-3 h-3" /> },
  primary: { color: 'primary', label: 'Principal' },
  secondary: { color: 'secondary', label: 'Secundário' },
  default: { color: 'default', label: 'Padrão' },

  // Business statuses
  pending: { color: 'warning', label: 'Pendente', icon: <Clock className="w-3 h-3" /> },
  approved: { color: 'success', label: 'Aprovado', icon: <CheckCircle className="w-3 h-3" /> },
  rejected: { color: 'danger', label: 'Rejeitado', icon: <XCircle className="w-3 h-3" /> },
  cancelled: { color: 'danger', label: 'Cancelado', icon: <XCircle className="w-3 h-3" /> },
  completed: { color: 'success', label: 'Concluído', icon: <Check className="w-3 h-3" /> },
  in_progress: { color: 'primary', label: 'Em Andamento', icon: <RefreshCw className="w-3 h-3" /> },

  // Cadastro specific statuses
  RASCUNHO: { color: 'default', label: 'Rascunho', icon: <Edit className="w-3 h-3" /> },
  SUBMETIDO: { color: 'primary', label: 'Submetido', icon: <Send className="w-3 h-3" /> },
  EM_ANALISE: { color: 'warning', label: 'Em Análise', icon: <RefreshCw className="w-3 h-3" /> },
  APROVADO: { color: 'success', label: 'Aprovado', icon: <CheckCircle className="w-3 h-3" /> },
  PENDENTE: { color: 'warning', label: 'Pendente', icon: <Clock className="w-3 h-3" /> },
  CANCELADO: { color: 'danger', label: 'Cancelado', icon: <XCircle className="w-3 h-3" /> },
  PAGAMENTO_PENDENTE: { color: 'warning', label: 'Pagamento Pendente', icon: <Clock className="w-3 h-3" /> },
  PAGAMENTO_RECEBIDO: { color: 'primary', label: 'Pagamento Recebido', icon: <Check className="w-3 h-3" /> },
  CONTRATO_GERADO: { color: 'primary', label: 'Contrato Gerado', icon: <FileText className="w-3 h-3" /> },
  ENVIADO_ASSINATURA: { color: 'primary', label: 'Enviado para Assinatura', icon: <Send className="w-3 h-3" /> },
  ASSINADO: { color: 'success', label: 'Assinado', icon: <CheckCircle className="w-3 h-3" /> },
  CONCLUIDO: { color: 'success', label: 'Concluído', icon: <Rocket className="w-3 h-3" /> },
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
    icon: undefined
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
        startContent={displayIcon}
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
      startContent={displayIcon}
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
