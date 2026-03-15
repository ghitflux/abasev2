import apiClient from './client';
import type { LoginResponse } from '../types';

export interface LoginPayload {
  cpf?: string;
  email?: string;
  password: string;
}

export async function login(payload: LoginPayload): Promise<LoginResponse> {
  const { data } = await apiClient.post<LoginResponse>('/auth/login/', payload);
  return data;
}

export async function logout(refreshToken: string): Promise<void> {
  try {
    await apiClient.post('/auth/logout/', { refresh: refreshToken });
  } catch {
    // Ignora erros no logout — sempre limpa localmente
  }
}
