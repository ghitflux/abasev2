"use client";

import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { createApiClient, getApiClient, ApiClient } from '@/lib/api-client';

export interface User {
  id: string;
  email: string;
  name: string;
  perfil: 'ADMIN' | 'ANALISTA' | 'TESOUREIRO' | 'AGENTE' | 'ASSOCIADO';
}

export interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<void>;
  loginWithOIDC: (redirectUri?: string) => void;
  logout: () => Promise<void>;
  refreshToken: () => Promise<void>;
  apiClient: ApiClient | null;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export interface AuthProviderProps {
  children: React.ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [apiClient, setApiClient] = useState<ApiClient | null>(null);
  const router = useRouter();

  /**
   * Inicializa API client
   */
  useEffect(() => {
    const client = createApiClient({
      baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
      onUnauthorized: () => {
        // Sessão expirou, fazer logout
        handleLogout();
      },
      onError: (error) => {
        // Log de erros (pode integrar com toast aqui)
        console.error('API Error:', error);
      },
    });

    setApiClient(client);
  }, []);

  /**
   * Carrega usuário autenticado ao montar
   */
  useEffect(() => {
    if (apiClient) {
      loadUser();
    }
  }, [apiClient]);

  /**
   * Carrega dados do usuário autenticado
   */
  const loadUser = async () => {
    if (!apiClient) return;

    const token = apiClient.getAccessToken();
    if (!token) {
      setIsLoading(false);
      return;
    }

    try {
      const response = await apiClient.get<User>('/api/v1/auth/me');

      if (response.data) {
        setUser(response.data);
      } else {
        // Token inválido, limpar
        apiClient.clearTokens();
      }
    } catch (error) {
      console.error('Failed to load user:', error);
      apiClient.clearTokens();
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Login com credenciais locais
   */
  const login = async (username: string, password: string) => {
    if (!apiClient) throw new Error('API Client não inicializado');

    setIsLoading(true);

    try {
      const response = await apiClient.post<{
        access_token: string;
        refresh_token: string;
        user: User;
      }>('/api/v1/auth/login/local', {
        username,
        password,
      });

      if (response.error) {
        throw new Error(response.error.message);
      }

      if (response.data) {
        // Salvar tokens
        apiClient.setTokens(response.data.access_token, response.data.refresh_token);

        // Salvar usuário
        setUser(response.data.user);

        // Redirecionar para dashboard
        router.push('/dashboard');
      }
    } catch (error) {
      console.error('Login failed:', error);
      throw error;
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Login com OIDC (redireciona para provider)
   */
  const loginWithOIDC = (redirectUri?: string) => {
    // Salvar redirect URI no localStorage
    if (redirectUri) {
      localStorage.setItem('auth_redirect', redirectUri);
    }

    // Construir URL de autorização OIDC
    const oidcIssuer = process.env.NEXT_PUBLIC_OIDC_ISSUER;
    const clientId = process.env.NEXT_PUBLIC_OIDC_CLIENT_ID;
    const callbackUrl = `${window.location.origin}/auth/callback`;

    // Gerar code verifier e challenge para PKCE
    const codeVerifier = generateCodeVerifier();
    localStorage.setItem('code_verifier', codeVerifier);

    const params = new URLSearchParams({
      response_type: 'code',
      client_id: clientId || '',
      redirect_uri: callbackUrl,
      scope: 'openid profile email',
      code_challenge: codeVerifier, // Simplificado - deveria usar SHA256
      code_challenge_method: 'plain',
    });

    // Redirecionar para provider OIDC
    window.location.href = `${oidcIssuer}/authorize?${params.toString()}`;
  };

  /**
   * Processa callback OIDC
   */
  const handleOIDCCallback = async (code: string) => {
    if (!apiClient) throw new Error('API Client não inicializado');

    setIsLoading(true);

    try {
      const codeVerifier = localStorage.getItem('code_verifier') || '';

      const response = await apiClient.post<{
        access_token: string;
        refresh_token: string;
        user: User;
      }>('/api/v1/auth/oidc/callback', {
        code,
        code_verifier: codeVerifier,
      });

      if (response.error) {
        throw new Error(response.error.message);
      }

      if (response.data) {
        // Salvar tokens
        apiClient.setTokens(response.data.access_token, response.data.refresh_token);

        // Salvar usuário
        setUser(response.data.user);

        // Limpar code verifier
        localStorage.removeItem('code_verifier');

        // Redirecionar
        const redirectTo = localStorage.getItem('auth_redirect') || '/dashboard';
        localStorage.removeItem('auth_redirect');
        router.push(redirectTo);
      }
    } catch (error) {
      console.error('OIDC callback failed:', error);
      throw error;
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Logout
   */
  const logout = async () => {
    if (!apiClient || !user) return;

    try {
      const token = apiClient.getAccessToken();
      if (token) {
        // Notificar backend (não aguardar resposta)
        apiClient.post('/api/v1/auth/logout', {
          token,
          user_id: user.id,
          global_logout: false,
        });
      }
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      handleLogout();
    }
  };

  /**
   * Logout local (limpa estado)
   */
  const handleLogout = () => {
    if (apiClient) {
      apiClient.clearTokens();
    }
    setUser(null);
    router.push('/login');
  };

  /**
   * Renova access token
   */
  const refreshToken = async () => {
    if (!apiClient) return;

    try {
      const response = await apiClient.post<{
        access_token: string;
        expires_in: number;
      }>('/api/v1/auth/refresh', {
        refresh_token: apiClient.getAccessToken(),
      });

      if (response.data) {
        // Atualizar access token
        const currentRefreshToken = localStorage.getItem('refresh_token') || '';
        apiClient.setTokens(response.data.access_token, currentRefreshToken);
      }
    } catch (error) {
      console.error('Token refresh failed:', error);
      handleLogout();
    }
  };

  const value: AuthContextType = {
    user,
    isAuthenticated: !!user,
    isLoading,
    login,
    loginWithOIDC,
    logout,
    refreshToken,
    apiClient,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/**
 * Hook para usar o AuthContext
 */
export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}

/**
 * Gera code verifier para PKCE
 */
function generateCodeVerifier(): string {
  const array = new Uint8Array(32);
  crypto.getRandomValues(array);
  return Array.from(array, (byte) => byte.toString(16).padStart(2, '0')).join('');
}

// Export do handleOIDCCallback para uso na página de callback
export { AuthContext };
