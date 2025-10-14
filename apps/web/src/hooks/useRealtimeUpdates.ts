"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useAuth } from "@/contexts/AuthContext";

export interface RealtimeMessage<T = any> {
  channel?: string;
  data: T;
  event?: string;
}

export interface UseRealtimeOptions {
  autoReconnect?: boolean;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
}

export function useRealtimeUpdates<T = any>(
  onMessage: (message: RealtimeMessage<T>) => void,
  options: UseRealtimeOptions = {}
) {
  const { user } = useAuth();
  const [isConnected, setIsConnected] = useState(false);
  const [reconnectAttempts, setReconnectAttempts] = useState(0);

  const {
    autoReconnect = true,
    reconnectInterval = 3000,
    maxReconnectAttempts = 5,
  } = options;

  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const isConnectingRef = useRef(false);

  const connect = useCallback(() => {
    if (isConnectingRef.current || !user) {
      return;
    }

    try {
      isConnectingRef.current = true;

      if (socketRef.current) {
        socketRef.current.close();
      }

      const baseURL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const wsURL = baseURL.replace(/^http/, "ws") + "/api/v1/ws/updates";
      const socket = new WebSocket(wsURL);
      socketRef.current = socket;

      socket.onopen = () => {
        setIsConnected(true);
        setReconnectAttempts(0);
        isConnectingRef.current = false;
      };

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as RealtimeMessage<T>;
          onMessage(data);
        } catch (error) {
          console.error("Erro ao processar mensagem WebSocket", error);
        }
      };

      socket.onclose = () => {
        setIsConnected(false);
        isConnectingRef.current = false;

        if (autoReconnect && reconnectAttempts < maxReconnectAttempts) {
          const nextAttempt = reconnectAttempts + 1;
          setReconnectAttempts(nextAttempt);

          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, reconnectInterval);
        }
      };

      socket.onerror = () => {
        socket.close();
      };
    } catch (error) {
      console.error("Erro ao criar conexão WebSocket", error);
      isConnectingRef.current = false;
    }
  }, [user, onMessage, autoReconnect, reconnectInterval, maxReconnectAttempts, reconnectAttempts]);

  const disconnect = useCallback(() => {
    if (socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
    }

    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    setIsConnected(false);
    isConnectingRef.current = false;
  }, []);

  useEffect(() => {
    if (user) {
      connect();
    }
    return () => {
      disconnect();
    };
  }, [user, connect, disconnect]);

  useEffect(() => () => disconnect(), [disconnect]);

  return {
    isConnected,
    reconnectAttempts,
    connect,
    disconnect,
  };
}
