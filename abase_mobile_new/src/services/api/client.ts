// HTTP client com axios + interceptor automático de Bearer token
import axios, { type InternalAxiosRequestConfig } from 'axios';
import * as SecureStore from 'expo-secure-store';
import { BASE_URL } from './constants';

export const TOKEN_KEY = '@Abase:token';

export const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 30_000,
  headers: {
    Accept: 'application/json',
    'Content-Type': 'application/json',
  },
});

// Injeta Bearer token em cada requisição
apiClient.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
  try {
    const token = await SecureStore.getItemAsync(TOKEN_KEY);
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  } catch {
    // ignora falha de leitura
  }
  return config;
});

// Normaliza erros de resposta
apiClient.interceptors.response.use(
  (res) => res,
  (error) => {
    const data = error?.response?.data;
    const msg =
      (typeof data === 'object' && (data?.message || data?.error)) ||
      error?.message ||
      'Erro de rede. Verifique sua conexão.';
    return Promise.reject(new Error(msg));
  },
);

// Helpers tipados
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
