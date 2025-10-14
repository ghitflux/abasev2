"use client";

import React from 'react';
import { Card, CardBody } from '@heroui/react';
import { cn } from '../../utils/cn';

export interface TimelineEvent {
  id: string;
  title: string;
  description?: string;
  timestamp: Date | string;
  status?: 'completed' | 'current' | 'pending' | 'error';
  icon?: React.ReactNode;
  metadata?: Record<string, any>;
  user?: string;
}

export interface TimelineProps {
  events: TimelineEvent[];
  className?: string;
  showTimestamps?: boolean;
  showUser?: boolean;
  maxHeight?: string;
  variant?: 'default' | 'compact' | 'detailed';
}

export function Timeline({
  events,
  className,
  showTimestamps = true,
  showUser = true,
  maxHeight,
  variant = 'default',
}: TimelineProps) {
  const formatTimestamp = (timestamp: Date | string): string => {
    const date = typeof timestamp === 'string' ? new Date(timestamp) : timestamp;
    return date.toLocaleString('pt-BR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getStatusColor = (status?: string): string => {
    switch (status) {
      case 'completed':
        return 'text-success';
      case 'current':
        return 'text-primary';
      case 'error':
        return 'text-danger';
      case 'pending':
      default:
        return 'text-default-400';
    }
  };

  const getStatusBg = (status?: string): string => {
    switch (status) {
      case 'completed':
        return 'bg-success';
      case 'current':
        return 'bg-primary';
      case 'error':
        return 'bg-danger';
      case 'pending':
      default:
        return 'bg-default-200';
    }
  };

  const getDefaultIcon = (status?: string): React.ReactNode => {
    switch (status) {
      case 'completed':
        return (
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
            <path
              fillRule="evenodd"
              d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
              clipRule="evenodd"
            />
          </svg>
        );
      case 'current':
        return (
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
            <path
              fillRule="evenodd"
              d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z"
              clipRule="evenodd"
            />
          </svg>
        );
      case 'error':
        return (
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
            <path
              fillRule="evenodd"
              d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z"
              clipRule="evenodd"
            />
          </svg>
        );
      default:
        return (
          <div className="w-2 h-2 rounded-full bg-current" />
        );
    }
  };

  if (events.length === 0) {
    return (
      <div className={cn("text-center py-8 text-default-500", className)}>
        <p>Nenhum evento registrado</p>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "space-y-4",
        maxHeight && "overflow-y-auto",
        className
      )}
      style={{ maxHeight }}
    >
      {events.map((event, index) => (
        <div key={event.id} className="flex items-start space-x-4">
          {/* Timeline Line */}
          <div className="flex flex-col items-center">
            {/* Icon */}
            <div
              className={cn(
                "flex items-center justify-center w-8 h-8 rounded-full border-2 transition-colors",
                getStatusBg(event.status),
                event.status === 'completed' && "border-success",
                event.status === 'current' && "border-primary",
                event.status === 'error' && "border-danger",
                (!event.status || event.status === 'pending') && "border-default-200"
              )}
            >
              {event.icon || (
                <span className={cn("text-white", getStatusColor(event.status))}>
                  {getDefaultIcon(event.status)}
                </span>
              )}
            </div>

            {/* Connector Line */}
            {index < events.length - 1 && (
              <div className="w-0.5 h-8 bg-default-200 mt-2" />
            )}
          </div>

          {/* Event Content */}
          <div className="flex-1 min-w-0">
            <Card className="w-full">
              <CardBody className="p-4">
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <h4 className="text-sm font-medium text-default-900">
                      {event.title}
                    </h4>
                    
                    {event.description && (
                      <p className="text-sm text-default-600 mt-1">
                        {event.description}
                      </p>
                    )}

                    {/* Metadata */}
                    {event.metadata && variant === 'detailed' && (
                      <div className="mt-2 space-y-1">
                        {Object.entries(event.metadata).map(([key, value]) => (
                          <div key={key} className="text-xs text-default-500">
                            <span className="font-medium">{key}:</span> {String(value)}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Timestamp and User */}
                  <div className="ml-4 text-right text-xs text-default-500">
                    {showTimestamps && (
                      <div className="font-medium">
                        {formatTimestamp(event.timestamp)}
                      </div>
                    )}
                    {showUser && event.user && (
                      <div className="mt-1">
                        por {event.user}
                      </div>
                    )}
                  </div>
                </div>
              </CardBody>
            </Card>
          </div>
        </div>
      ))}
    </div>
  );
}

// Convenience component for status timeline
export interface StatusTimelineProps {
  status: string;
  events?: TimelineEvent[];
  className?: string;
}

export function StatusTimeline({ status, events = [], className }: StatusTimelineProps) {
  // Default events based on status
  const defaultEvents: TimelineEvent[] = [
    {
      id: 'created',
      title: 'Cadastro Criado',
      description: 'Novo cadastro foi criado no sistema',
      timestamp: new Date(),
      status: 'completed',
    },
  ];

  if (['SUBMETIDO', 'EM_ANALISE', 'APROVADO', 'PENDENTE', 'CANCELADO'].includes(status)) {
    defaultEvents.push({
      id: 'submitted',
      title: 'Submetido para Análise',
      description: 'Cadastro foi enviado para análise',
      timestamp: new Date(),
      status: 'completed',
    });
  }

  if (['APROVADO', 'PAGAMENTO_PENDENTE', 'PAGAMENTO_RECEBIDO', 'CONTRATO_GERADO', 'ENVIADO_ASSINATURA', 'ASSINADO', 'CONCLUIDO'].includes(status)) {
    defaultEvents.push({
      id: 'approved',
      title: 'Aprovado',
      description: 'Cadastro foi aprovado pela análise',
      timestamp: new Date(),
      status: 'completed',
    });
  }

  if (['PAGAMENTO_RECEBIDO', 'CONTRATO_GERADO', 'ENVIADO_ASSINATURA', 'ASSINADO', 'CONCLUIDO'].includes(status)) {
    defaultEvents.push({
      id: 'payment',
      title: 'Pagamento Recebido',
      description: 'Pagamento foi registrado e confirmado',
      timestamp: new Date(),
      status: 'completed',
    });
  }

  if (['CONTRATO_GERADO', 'ENVIADO_ASSINATURA', 'ASSINADO', 'CONCLUIDO'].includes(status)) {
    defaultEvents.push({
      id: 'contract',
      title: 'Contrato Gerado',
      description: 'Contrato foi gerado e está pronto para assinatura',
      timestamp: new Date(),
      status: 'completed',
    });
  }

  if (['ASSINADO', 'CONCLUIDO'].includes(status)) {
    defaultEvents.push({
      id: 'signed',
      title: 'Contrato Assinado',
      description: 'Contrato foi assinado digitalmente',
      timestamp: new Date(),
      status: 'completed',
    });
  }

  if (status === 'CONCLUIDO') {
    defaultEvents.push({
      id: 'completed',
      title: 'Processo Concluído',
      description: 'Cadastro foi finalizado com sucesso',
      timestamp: new Date(),
      status: 'completed',
    });
  }

  // Mark current status
  const currentEventIndex = defaultEvents.findIndex(event => 
    event.id === status.toLowerCase().replace('_', '')
  );
  
  if (currentEventIndex >= 0) {
    defaultEvents[currentEventIndex].status = 'current';
  }

  const allEvents = [...defaultEvents, ...events].sort((a, b) => {
    const dateA = typeof a.timestamp === 'string' ? new Date(a.timestamp) : a.timestamp;
    const dateB = typeof b.timestamp === 'string' ? new Date(b.timestamp) : b.timestamp;
    return dateA.getTime() - dateB.getTime();
  });

  return (
    <Timeline
      events={allEvents}
      className={className}
      variant="detailed"
    />
  );
}
