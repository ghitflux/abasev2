import { API_BASE_URL } from "@/lib/env";
import type { AuthUser } from "@/types/auth";

type LoginResponse = {
  access: string;
  refresh: string;
  user: AuthUser;
};

type RefreshResponse = {
  access: string;
  refresh?: string;
};

export async function loginWithBackend(email: string, password: string) {
  const response = await fetch(`${API_BASE_URL}/auth/login/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
    cache: "no-store",
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail =
      payload?.detail ??
      payload?.non_field_errors?.[0] ??
      payload?.message ??
      "Falha ao autenticar.";
    throw new Error(detail);
  }

  return (await response.json()) as LoginResponse;
}

export async function refreshWithBackend(refresh: string) {
  const response = await fetch(`${API_BASE_URL}/auth/refresh/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh }),
    cache: "no-store",
  });

  if (!response.ok) {
    return null;
  }

  return (await response.json()) as RefreshResponse;
}

export async function getCurrentUser(accessToken: string) {
  const response = await fetch(`${API_BASE_URL}/auth/me/`, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    return null;
  }

  return (await response.json()) as AuthUser;
}

export async function logoutWithBackend(refresh: string) {
  await fetch(`${API_BASE_URL}/auth/logout/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh }),
    cache: "no-store",
  }).catch(() => null);
}
