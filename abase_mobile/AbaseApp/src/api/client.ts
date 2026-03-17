import axios, { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from 'axios';
import * as SecureStore from 'expo-secure-store';

// Android emulator: 10.0.2.2 aponta para localhost da máquina host
// Para dispositivo físico na mesma rede: use o IP da máquina
// Para produção: https://www.abasepiaui.com/api/v1
export const API_BASE_URL = 'http://192.168.3.8:8000/api/v1';

const SECURE_STORE_KEY = '@Abase:authState';

export interface StoredAuth {
  accessToken: string;
  refreshToken: string;
}

export async function getStoredAuth(): Promise<StoredAuth | null> {
  try {
    const raw = await SecureStore.getItemAsync(SECURE_STORE_KEY);
    return raw ? (JSON.parse(raw) as StoredAuth) : null;
  } catch {
    return null;
  }
}

export async function setStoredAuth(auth: StoredAuth): Promise<void> {
  await SecureStore.setItemAsync(SECURE_STORE_KEY, JSON.stringify(auth));
}

export async function clearStoredAuth(): Promise<void> {
  await SecureStore.deleteItemAsync(SECURE_STORE_KEY);
}

// ---------------------------------------------------------------------------
// Axios instance
// ---------------------------------------------------------------------------
const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  },
});

// Request interceptor — injeta o access token
apiClient.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
  const auth = await getStoredAuth();
  if (auth?.accessToken) {
    config.headers.set('Authorization', `Bearer ${auth.accessToken}`);
  }
  return config;
});

// Flag para evitar loop infinito no refresh
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (token: string) => void;
  reject: (error: unknown) => void;
}> = [];

function processQueue(error: unknown, token: string | null) {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token as string);
    }
  });
  failedQueue = [];
}

// Response interceptor — tenta refresh no 401
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        // Aguarda o refresh em andamento
        return new Promise((resolve, reject) => {
          failedQueue.push({
            resolve: (token) => {
              originalRequest.headers.set('Authorization', `Bearer ${token}`);
              resolve(apiClient(originalRequest));
            },
            reject,
          });
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const auth = await getStoredAuth();
        if (!auth?.refreshToken) throw new Error('No refresh token');

        const { data } = await axios.post(`${API_BASE_URL}/auth/refresh/`, {
          refresh: auth.refreshToken,
        });

        const newAuth: StoredAuth = {
          accessToken: data.access,
          refreshToken: data.refresh ?? auth.refreshToken,
        };
        await setStoredAuth(newAuth);

        processQueue(null, newAuth.accessToken);
        originalRequest.headers.set('Authorization', `Bearer ${newAuth.accessToken}`);
        return apiClient(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        await clearStoredAuth();
        // O AuthContext irá detectar e redirecionar para o login
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  },
);

export default apiClient;
