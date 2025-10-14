/**
 * API Client com Auto-refresh de Tokens
 *
 * Features:
 * - Adiciona JWT automaticamente nos requests
 * - Auto-refresh em caso de 401
 * - Interceptors de erro
 * - Toast de feedback (integração com useToast)
 */

export interface ApiClientConfig {
  baseURL: string;
  onUnauthorized?: () => void;
  onError?: (error: ApiError) => void;
}

export interface ApiError {
  status: number;
  message: string;
  code?: string;
  details?: any;
}

export interface ApiResponse<T = any> {
  data?: T;
  error?: ApiError;
}

class ApiClient {
  private baseURL: string;
  private accessToken: string | null = null;
  private refreshToken: string | null = null;
  private isRefreshing = false;
  private refreshSubscribers: ((token: string) => void)[] = [];
  private onUnauthorized?: () => void;
  private onError?: (error: ApiError) => void;

  constructor(config: ApiClientConfig) {
    this.baseURL = config.baseURL;
    this.onUnauthorized = config.onUnauthorized;
    this.onError = config.onError;

    // Tenta recuperar tokens do localStorage
    if (typeof window !== 'undefined') {
      this.accessToken = localStorage.getItem('access_token');
      this.refreshToken = localStorage.getItem('refresh_token');
    }
  }

  /**
   * Define tokens de autenticação
   */
  setTokens(accessToken: string, refreshToken: string) {
    this.accessToken = accessToken;
    this.refreshToken = refreshToken;

    if (typeof window !== 'undefined') {
      localStorage.setItem('access_token', accessToken);
      localStorage.setItem('refresh_token', refreshToken);
    }
  }

  /**
   * Remove tokens (logout)
   */
  clearTokens() {
    this.accessToken = null;
    this.refreshToken = null;

    if (typeof window !== 'undefined') {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
    }
  }

  /**
   * Retorna access token atual
   */
  getAccessToken(): string | null {
    return this.accessToken;
  }

  /**
   * Adiciona subscriber para aguardar refresh
   */
  private subscribeTokenRefresh(callback: (token: string) => void) {
    this.refreshSubscribers.push(callback);
  }

  /**
   * Notifica todos subscribers após refresh
   */
  private onTokenRefreshed(token: string) {
    this.refreshSubscribers.forEach((callback) => callback(token));
    this.refreshSubscribers = [];
  }

  /**
   * Renova access token usando refresh token
   */
  private async refreshAccessToken(): Promise<string | null> {
    if (!this.refreshToken) {
      return null;
    }

    try {
      const response = await fetch(`${this.baseURL}/api/v1/auth/refresh`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          refresh_token: this.refreshToken,
        }),
      });

      if (!response.ok) {
        throw new Error('Refresh failed');
      }

      const data = await response.json();
      const newAccessToken = data.access_token;

      this.accessToken = newAccessToken;
      if (typeof window !== 'undefined') {
        localStorage.setItem('access_token', newAccessToken);
      }

      return newAccessToken;
    } catch (error) {
      // Refresh falhou, fazer logout
      this.clearTokens();
      if (this.onUnauthorized) {
        this.onUnauthorized();
      }
      return null;
    }
  }

  /**
   * Faz request com retry automático em caso de 401
   */
  private async fetchWithRetry<T = any>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<ApiResponse<T>> {
    const url = `${this.baseURL}${endpoint}`;

    // Adiciona token se disponível
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string>),
    };

    if (this.accessToken) {
      headers['Authorization'] = `Bearer ${this.accessToken}`;
    }

    try {
      let response = await fetch(url, {
        ...options,
        headers,
      });

      // Se 401, tentar refresh
      if (response.status === 401 && this.refreshToken) {
        // Se já está refreshing, aguardar
        if (this.isRefreshing) {
          return new Promise((resolve) => {
            this.subscribeTokenRefresh(async (token) => {
              // Retry com novo token
              const retryResponse = await fetch(url, {
                ...options,
                headers: {
                  ...headers,
                  Authorization: `Bearer ${token}`,
                },
              });

              const result = await this.processResponse<T>(retryResponse);
              resolve(result);
            });
          });
        }

        // Iniciar refresh
        this.isRefreshing = true;
        const newToken = await this.refreshAccessToken();
        this.isRefreshing = false;

        if (newToken) {
          // Notificar subscribers
          this.onTokenRefreshed(newToken);

          // Retry request com novo token
          response = await fetch(url, {
            ...options,
            headers: {
              ...headers,
              Authorization: `Bearer ${newToken}`,
            },
          });
        } else {
          // Refresh falhou
          const error: ApiError = {
            status: 401,
            message: 'Sessão expirada. Faça login novamente.',
            code: 'session_expired',
          };

          if (this.onError) {
            this.onError(error);
          }

          return { error };
        }
      }

      return await this.processResponse<T>(response);
    } catch (error) {
      const apiError: ApiError = {
        status: 0,
        message: error instanceof Error ? error.message : 'Erro de conexão',
        code: 'network_error',
      };

      if (this.onError) {
        this.onError(apiError);
      }

      return { error: apiError };
    }
  }

  /**
   * Processa resposta da API
   */
  private async processResponse<T>(response: Response): Promise<ApiResponse<T>> {
    const contentType = response.headers.get('content-type');
    const isJson = contentType?.includes('application/json');

    if (response.ok) {
      if (response.status === 204) {
        // No content
        return { data: undefined };
      }

      const data = isJson ? await response.json() : await response.text();
      return { data };
    }

    // Erro
    let errorData: any;
    try {
      errorData = isJson ? await response.json() : await response.text();
    } catch {
      errorData = null;
    }

    const error: ApiError = {
      status: response.status,
      message: errorData?.message || errorData?.error || response.statusText,
      code: errorData?.code || errorData?.error,
      details: errorData?.details,
    };

    if (this.onError && response.status !== 401) {
      this.onError(error);
    }

    return { error };
  }

  /**
   * GET request
   */
  async get<T = any>(endpoint: string, options?: RequestInit): Promise<ApiResponse<T>> {
    return this.fetchWithRetry<T>(endpoint, {
      ...options,
      method: 'GET',
    });
  }

  /**
   * POST request
   */
  async post<T = any>(
    endpoint: string,
    body?: any,
    options?: RequestInit
  ): Promise<ApiResponse<T>> {
    return this.fetchWithRetry<T>(endpoint, {
      ...options,
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  /**
   * PUT request
   */
  async put<T = any>(
    endpoint: string,
    body?: any,
    options?: RequestInit
  ): Promise<ApiResponse<T>> {
    return this.fetchWithRetry<T>(endpoint, {
      ...options,
      method: 'PUT',
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  /**
   * PATCH request
   */
  async patch<T = any>(
    endpoint: string,
    body?: any,
    options?: RequestInit
  ): Promise<ApiResponse<T>> {
    return this.fetchWithRetry<T>(endpoint, {
      ...options,
      method: 'PATCH',
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  /**
   * DELETE request
   */
  async delete<T = any>(endpoint: string, options?: RequestInit): Promise<ApiResponse<T>> {
    return this.fetchWithRetry<T>(endpoint, {
      ...options,
      method: 'DELETE',
    });
  }

  /**
   * Upload de arquivo
   */
  async upload<T = any>(
    endpoint: string,
    file: File,
    additionalData?: Record<string, any>
  ): Promise<ApiResponse<T>> {
    const formData = new FormData();
    formData.append('file', file);

    if (additionalData) {
      Object.entries(additionalData).forEach(([key, value]) => {
        formData.append(key, String(value));
      });
    }

    const headers: HeadersInit = {};
    if (this.accessToken) {
      headers['Authorization'] = `Bearer ${this.accessToken}`;
    }

    const url = `${this.baseURL}${endpoint}`;

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers,
        body: formData,
      });

      return await this.processResponse<T>(response);
    } catch (error) {
      const apiError: ApiError = {
        status: 0,
        message: error instanceof Error ? error.message : 'Erro no upload',
        code: 'upload_error',
      };

      if (this.onError) {
        this.onError(apiError);
      }

      return { error: apiError };
    }
  }
}

// Instância global (será configurada no AuthProvider)
let apiClientInstance: ApiClient | null = null;

/**
 * Cria instância do API client
 */
export function createApiClient(config: ApiClientConfig): ApiClient {
  apiClientInstance = new ApiClient(config);
  return apiClientInstance;
}

/**
 * Retorna instância global do API client
 */
export function getApiClient(): ApiClient {
  if (!apiClientInstance) {
    throw new Error('API Client não inicializado. Use createApiClient() primeiro.');
  }
  return apiClientInstance;
}

export { ApiClient };
export default ApiClient;
