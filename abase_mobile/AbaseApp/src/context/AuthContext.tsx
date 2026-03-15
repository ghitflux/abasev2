import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';

import { login as apiLogin, logout as apiLogout } from '../api/auth';
import {
  clearStoredAuth,
  getStoredAuth,
  setStoredAuth,
} from '../api/client';
import type { User } from '../types';

interface AuthContextValue {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  /** Login por CPF ou email */
  login: (cpfOrEmail: string, password: string, useCpf?: boolean) => Promise<void>;
  logout: () => Promise<void>;
  hasRole: (...roles: string[]) => boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Restaura sessão salva ao abrir o app
  useEffect(() => {
    (async () => {
      try {
        const auth = await getStoredAuth();
        if (auth) {
          // Tenta buscar os dados do usuário do token armazenado
          // O token já será injetado pelo interceptor do apiClient
          const { default: apiClient } = await import('../api/client');
          const { data } = await apiClient.get('/auth/me/');
          setUser(data);
        }
      } catch {
        await clearStoredAuth();
      } finally {
        setIsLoading(false);
      }
    })();
  }, []);

  const login = useCallback(
    async (cpfOrEmail: string, password: string, useCpf = true) => {
      const payload = useCpf
        ? { cpf: cpfOrEmail, password }
        : { email: cpfOrEmail, password };

      const response = await apiLogin(payload);

      await setStoredAuth({
        accessToken: response.access,
        refreshToken: response.refresh,
      });

      setUser(response.user);
    },
    [],
  );

  const logout = useCallback(async () => {
    try {
      const auth = await getStoredAuth();
      if (auth?.refreshToken) {
        await apiLogout(auth.refreshToken);
      }
    } finally {
      await clearStoredAuth();
      setUser(null);
    }
  }, []);

  const hasRole = useCallback(
    (...roles: string[]) => {
      if (!user) return false;
      return roles.some((r) => user.roles.includes(r));
    },
    [user],
  );

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isAuthenticated: !!user,
      isLoading,
      login,
      logout,
      hasRole,
    }),
    [user, isLoading, login, logout, hasRole],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth deve ser usado dentro de <AuthProvider>');
  return ctx;
}
