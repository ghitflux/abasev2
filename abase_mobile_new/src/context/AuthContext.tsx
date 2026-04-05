import React, { createContext, useContext, useEffect, useState } from 'react';
import * as SecureStore from 'expo-secure-store';
import type { User, Roles, Bootstrap, AuthPayload } from '@/types';
import {
  SESSION_KEY,
  clearStoredTokens,
  persistTokens,
  readValidStoredTokens,
} from '@/services/api/session';
import { setApiAccessToken } from '@/services/api/client';

type AuthState = {
  user: User | null;
  token: string | null;
  refreshToken: string | null;
  roles: Roles;
  bootstrap: Bootstrap | null;
};

type AuthContextType = AuthState & {
  loadingAuth: boolean;
  login: (data: AuthPayload) => Promise<void>;
  logout: () => Promise<void>;
  getToken: () => string | null;
  isLoggedIn: () => boolean;
};

const AuthContext = createContext<AuthContextType>({} as AuthContextType);

// Armazenamos access/refresh token, user e roles no SecureStore.
// Bootstrap é re-fetchado pelo app em /api/v1/app/me/.

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [state, setState] = useState<AuthState>({
    user: null,
    token: null,
    refreshToken: null,
    roles: [],
    bootstrap: null,
  });
  const [loadingAuth, setLoadingAuth] = useState(true);

  // Rehidrata sessão ao iniciar
  useEffect(() => {
    (async () => {
      try {
        const [{ accessToken, refreshToken }, sessionRaw] = await Promise.all([
          readValidStoredTokens(),
          SecureStore.getItemAsync(SESSION_KEY),
        ]);

        if (accessToken && refreshToken) {
          setApiAccessToken(accessToken);
          const session = sessionRaw ? (JSON.parse(sessionRaw) as { user: User; roles: Roles }) : null;
          setState({
            token: accessToken,
            refreshToken,
            user: session?.user ?? null,
            roles: session?.roles ?? [],
            bootstrap: null, // será re-fetchado pelo app quando necessário
          });
        }
      } catch {
        // falha silenciosa — usuário precisará fazer login novamente
      } finally {
        setLoadingAuth(false);
      }
    })();
  }, []);

  const login = async (data: AuthPayload) => {
    setApiAccessToken(data.token);
    const next: AuthState = {
      user: data.user,
      token: data.token,
      refreshToken: data.refreshToken ?? null,
      roles: data.roles || [],
      bootstrap: data.bootstrap || null,
    };
    setState(next);
    // Persiste token e sessão separadamente para respeitar limite de 2KB
    await Promise.all([
      persistTokens(data.token, data.refreshToken ?? null),
      SecureStore.setItemAsync(
        SESSION_KEY,
        JSON.stringify({ user: data.user, roles: data.roles || [] }),
      ).catch(() => {}),
    ]);
  };

  const logout = async () => {
    setApiAccessToken(null);
    setState({ user: null, token: null, refreshToken: null, roles: [], bootstrap: null });
    await Promise.all([
      clearStoredTokens(),
      SecureStore.deleteItemAsync(SESSION_KEY).catch(() => {}),
    ]);
  };

  const getToken = () => state.token;
  const isLoggedIn = () => !!state.token && !!state.user;

  return (
    <AuthContext.Provider value={{ ...state, loadingAuth, login, logout, getToken, isLoggedIn }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
