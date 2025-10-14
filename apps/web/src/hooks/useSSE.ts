"use client";
import { useEffect, useRef } from "react";

export function useSSE(url: string, onMessage: (data: string) => void) {
  const ref = useRef<EventSource | null>(null);

  useEffect(() => {
    const es = new EventSource(url);
    ref.current = es;
    es.onmessage = (event) => onMessage(event.data);
    es.onerror = () => {
      // errors are logged in devtools; keep silent to avoid noisy UI
    };

    return () => {
      es.close();
    };
  }, [url, onMessage]);

  return ref;
}
