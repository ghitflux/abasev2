"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@abase/ui";

export interface SSEEvent {
  type: string;
  data: any;
  timestamp: string;
  user_id?: string;
}

export interface SSEEventHandlers {
  [eventType: string]: (data: any) => void;
}

export function useSSEEvents(
  eventHandlers: SSEEventHandlers,
  options: {
    autoReconnect?: boolean;
    reconnectInterval?: number;
    maxReconnectAttempts?: number;
    showNotifications?: boolean;
  } = {}
) {
  const { user } = useAuth();
  const { addToast } = useToast();
  const [isConnected, setIsConnected] = useState(false);
  const [reconnectAttempts, setReconnectAttempts] = useState(0);
  
  const {
    autoReconnect = true,
    reconnectInterval = 3000,
    maxReconnectAttempts = 5,
    showNotifications = true,
  } = options;

  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const isConnectingRef = useRef(false);

  const connect = useCallback(() => {
    if (isConnectingRef.current || !user) return;

    try {
      isConnectingRef.current = true;
      
      // Close existing connection
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }

      // Create new connection
      const baseURL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const eventSource = new EventSource(`${baseURL}/api/v1/sse`);
      eventSourceRef.current = eventSource;

      eventSource.onopen = () => {
        console.log('SSE connected');
        setIsConnected(true);
        setReconnectAttempts(0);
        isConnectingRef.current = false;
      };

      eventSource.onmessage = (event) => {
        try {
          const sseEvent: SSEEvent = JSON.parse(event.data);
          
          // Handle specific event types
          if (eventHandlers[sseEvent.type]) {
            eventHandlers[sseEvent.type](sseEvent.data);
          }

          // Show notifications for important events
          if (showNotifications) {
            handleEventNotification(sseEvent);
          }
        } catch (error) {
          console.error('Error parsing SSE event:', error);
        }
      };

      eventSource.onerror = (error) => {
        console.error('SSE error:', error);
        setIsConnected(false);
        isConnectingRef.current = false;
        
        // Auto-reconnect if enabled
        if (autoReconnect && reconnectAttempts < maxReconnectAttempts) {
          const nextAttempt = reconnectAttempts + 1;
          setReconnectAttempts(nextAttempt);
          
          console.log(`SSE reconnecting in ${reconnectInterval}ms (attempt ${nextAttempt}/${maxReconnectAttempts})`);
          
          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, reconnectInterval);
        } else if (reconnectAttempts >= maxReconnectAttempts) {
          console.error('SSE max reconnection attempts reached');
          if (showNotifications) {
            addToast({
              type: 'error',
              title: 'Conexão perdida',
              description: 'Não foi possível reconectar ao servidor. Recarregue a página.',
            });
          }
        }
      };

    } catch (error) {
      console.error('Error creating SSE connection:', error);
      isConnectingRef.current = false;
    }
  }, [user, eventHandlers, autoReconnect, reconnectInterval, maxReconnectAttempts, reconnectAttempts, showNotifications, addToast]);

  const disconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    
    setIsConnected(false);
    isConnectingRef.current = false;
  }, []);

  const handleEventNotification = (event: SSEEvent) => {
    const notifications: Record<string, { title: string; description: string; type: 'success' | 'info' | 'warning' | 'error' }> = {
      'CADASTRO_CRIADO': {
        title: 'Novo Cadastro',
        description: 'Um novo cadastro foi criado',
        type: 'info'
      },
      'CADASTRO_SUBMETIDO': {
        title: 'Cadastro Submetido',
        description: 'Um cadastro foi enviado para análise',
        type: 'info'
      },
      'CADASTRO_APROVADO': {
        title: 'Cadastro Aprovado',
        description: 'Um cadastro foi aprovado',
        type: 'success'
      },
      'CADASTRO_PENDENTE': {
        title: 'Cadastro Pendente',
        description: 'Um cadastro precisa de correções',
        type: 'warning'
      },
      'CADASTRO_CANCELADO': {
        title: 'Cadastro Cancelado',
        description: 'Um cadastro foi cancelado',
        type: 'error'
      },
      'PAGAMENTO_RECEBIDO': {
        title: 'Pagamento Recebido',
        description: 'Um pagamento foi registrado',
        type: 'success'
      },
      'CONTRATO_GERADO': {
        title: 'Contrato Gerado',
        description: 'Um contrato foi gerado',
        type: 'info'
      },
      'CONTRATO_ASSINADO': {
        title: 'Contrato Assinado',
        description: 'Um contrato foi assinado',
        type: 'success'
      },
      'CADASTRO_CONCLUIDO': {
        title: 'Cadastro Concluído',
        description: 'Um cadastro foi finalizado',
        type: 'success'
      }
    };

    const notification = notifications[event.type];
    if (notification) {
      addToast({
        type: notification.type,
        title: notification.title,
        description: notification.description,
      });
    }
  };

  // Connect on mount and when user changes
  useEffect(() => {
    if (user) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [user, connect, disconnect]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  return {
    isConnected,
    reconnectAttempts,
    connect,
    disconnect,
  };
}

// Hook específico para cadastros
export function useCadastrosSSE(refreshCallback: () => void) {
  const eventHandlers: SSEEventHandlers = {
    'CADASTRO_CRIADO': refreshCallback,
    'CADASTRO_SUBMETIDO': refreshCallback,
    'CADASTRO_APROVADO': refreshCallback,
    'CADASTRO_PENDENTE': refreshCallback,
    'CADASTRO_CANCELADO': refreshCallback,
    'CADASTRO_CONCLUIDO': refreshCallback,
  };

  return useSSEEvents(eventHandlers, {
    autoReconnect: true,
    reconnectInterval: 3000,
    maxReconnectAttempts: 5,
    showNotifications: true,
  });
}

// Hook específico para análise
export function useAnaliseSSE(refreshCallback: () => void) {
  const eventHandlers: SSEEventHandlers = {
    'CADASTRO_SUBMETIDO': refreshCallback,
    'CADASTRO_APROVADO': refreshCallback,
    'CADASTRO_PENDENTE': refreshCallback,
    'CADASTRO_CANCELADO': refreshCallback,
  };

  return useSSEEvents(eventHandlers, {
    autoReconnect: true,
    reconnectInterval: 3000,
    maxReconnectAttempts: 5,
    showNotifications: true,
  });
}

// Hook específico para tesouraria
export function useTesourariaSSE(refreshCallback: () => void) {
  const eventHandlers: SSEEventHandlers = {
    'CADASTRO_APROVADO': refreshCallback,
    'PAGAMENTO_RECEBIDO': refreshCallback,
    'CONTRATO_GERADO': refreshCallback,
    'CONTRATO_ASSINADO': refreshCallback,
    'CADASTRO_CONCLUIDO': refreshCallback,
  };

  return useSSEEvents(eventHandlers, {
    autoReconnect: true,
    reconnectInterval: 3000,
    maxReconnectAttempts: 5,
    showNotifications: true,
  });
}

