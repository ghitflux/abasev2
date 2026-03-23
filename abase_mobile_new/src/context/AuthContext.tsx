import React, { createContext, useContext, useEffect, useState } from 'react';
import * as SecureStore from 'expo-secure-store';
import type { User, Roles, Bootstrap, AuthPayload } from '@/types';

type AuthState = {
  user: User | null;
  token: string | null;
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

// Armazenamos token, user e roles no SecureStore (respeita limite de 2KB do iOS)
// Bootstrap é re-fetchado no app resume via /api/home
const TOKEN_KEY = '@Abase:token';
const SESSION_KEY = '@Abase:session'; // { user, roles }

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [state, setState] = useState<AuthState>({
    user: null,
    token: null,
    roles: [],
    bootstrap: null,
  });
  const [loadingAuth, setLoadingAuth] = useState(true);

  // Rehidrata sessão ao iniciar
  useEffect(() => {
    (async () => {
      try {
        const [token, sessionRaw] = await Promise.all([
          SecureStore.getItemAsync(TOKEN_KEY),
          SecureStore.getItemAsync(SESSION_KEY),
        ]);
        if (token) {
          const session = sessionRaw ? (JSON.parse(sessionRaw) as { user: User; roles: Roles }) : null;
          setState({
            token,
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
    const next: AuthState = {
      user: data.user,
      token: data.token,
      roles: data.roles || [],
      bootstrap: data.bootstrap || null,
    };
    setState(next);
    // Persiste token e sessão separadamente para respeitar limite de 2KB
    await Promise.all([
      SecureStore.setItemAsync(TOKEN_KEY, data.token).catch(() => {}),
      SecureStore.setItemAsync(
        SESSION_KEY,
        JSON.stringify({ user: data.user, roles: data.roles || [] }),
      ).catch(() => {}),
    ]);
  };

  const logout = async () => {
    setState({ user: null, token: null, roles: [], bootstrap: null });
    await Promise.all([
      SecureStore.deleteItemAsync(TOKEN_KEY).catch(() => {}),
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
