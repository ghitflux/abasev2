import axios, {
  AxiosError,
  type AxiosRequestConfig,
  type InternalAxiosRequestConfig,
} from 'axios';
import { ENDPOINTS, BASE_URL } from './constants';
import {
  ACCESS_TOKEN_KEY as TOKEN_KEY,
  REFRESH_TOKEN_KEY,
  clearStoredTokens,
  getStoredAccessToken,
  getStoredRefreshToken,
  persistTokens,
} from './session';

type RetriableConfig = InternalAxiosRequestConfig & { _retry?: boolean };

export { TOKEN_KEY, REFRESH_TOKEN_KEY };

export const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 30_000,
  headers: {
    Accept: 'application/json',
    'Content-Type': 'application/json',
  },
});

const refreshClient = axios.create({
  baseURL: BASE_URL,
  timeout: 30_000,
  headers: {
    Accept: 'application/json',
    'Content-Type': 'application/json',
  },
});

let refreshPromise: Promise<string | null> | null = null;

function isAuthUrl(url?: string) {
  const value = String(url || '');
  return value.includes('/auth/login/') || value.includes('/auth/refresh/');
}

async function refreshAccessToken() {
  if (refreshPromise) return refreshPromise;

  refreshPromise = (async () => {
    const refreshToken = await getStoredRefreshToken();
    if (!refreshToken) return null;

    try {
      const response = await refreshClient.post<{ access?: string; refresh?: string }>(
        ENDPOINTS.authRefresh,
        { refresh: refreshToken },
      );
      const accessToken = response.data?.access ?? null;
      if (!accessToken) {
        await clearStoredTokens();
        return null;
      }
      await persistTokens(accessToken, response.data?.refresh ?? refreshToken);
      return accessToken;
    } catch {
      await clearStoredTokens();
      return null;
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

apiClient.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
  try {
    const token = await getStoredAccessToken();
    if (token) {
      config.headers = config.headers ?? {};
      (config.headers as Record<string, string>).Authorization = `Bearer ${token}`;
    }
  } catch {
    // ignora falha de leitura
  }
  return config;
});

apiClient.interceptors.response.use(
  (res) => res,
  async (error: AxiosError<any>) => {
    const originalRequest = error.config as RetriableConfig | undefined;

    if (
      error.response?.status === 401 &&
      originalRequest &&
      !originalRequest._retry &&
      !isAuthUrl(originalRequest.url)
    ) {
      originalRequest._retry = true;
      const nextAccessToken = await refreshAccessToken();
      if (nextAccessToken) {
        originalRequest.headers = originalRequest.headers ?? {};
        (originalRequest.headers as Record<string, string>).Authorization =
          `Bearer ${nextAccessToken}`;
        return apiClient(originalRequest as AxiosRequestConfig);
      }
    }

    const data = error.response?.data;
    const msg =
      (typeof data === 'object' &&
        (data?.detail ||
          data?.message ||
          data?.error ||
          data?.non_field_errors?.[0])) ||
      error.message ||
      'Erro de rede. Verifique sua conexão.';

    return Promise.reject(new Error(msg));
  },
);

export async function get<T>(url: string, params?: Record<string, any>): Promise<T> {
  const res = await apiClient.get<T>(url, { params });
  return res.data;
}

export async function post<T>(url: string, data?: any): Promise<T> {
  const res = await apiClient.post<T>(url, data);
  return res.data;
}

export async function postForm<T>(url: string, formData: FormData): Promise<T> {
  const res = await apiClient.post<T>(url, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return res.data;
}
