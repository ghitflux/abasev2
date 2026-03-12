"use client";

import * as React from "react";

import { useAuthStore } from "@/store/auth-store";

export function useAuth() {
  const user = useAuthStore((state) => state.user);
  const status = useAuthStore((state) => state.status);
  const setLoading = useAuthStore((state) => state.setLoading);
  const setUser = useAuthStore((state) => state.setUser);
  const clear = useAuthStore((state) => state.clear);

  const refresh = React.useCallback(async () => {
    setLoading();
    try {
      const response = await fetch("/api/auth/me", {
        cache: "no-store",
        credentials: "include",
      });

      if (!response.ok) {
        clear();
        return null;
      }

      const payload = await response.json();
      setUser(payload.user);
      return payload.user;
    } catch {
      clear();
      return null;
    }
  }, [clear, setLoading, setUser]);

  React.useEffect(() => {
    if (status === "idle") {
      void refresh();
    }
  }, [refresh, status]);

  return {
    user,
    status,
    isAuthenticated: status === "authenticated",
    refresh,
    clear,
  };
}
