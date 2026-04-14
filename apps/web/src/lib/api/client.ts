"use client";

import axios from "axios";

type QueryValue =
  | string
  | number
  | boolean
  | null
  | undefined
  | Array<string | number | boolean>;

type ApiFetchOptions = {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  query?: Record<string, QueryValue>;
  body?: unknown;
  formData?: FormData;
  onUploadProgress?: (progress: {
    loaded: number;
    total: number | null;
    percent: number;
  }) => void;
};

function buildQuery(query?: Record<string, QueryValue>) {
  const searchParams = new URLSearchParams();

  Object.entries(query ?? {}).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") {
      return;
    }

    if (Array.isArray(value)) {
      value.forEach((item) => searchParams.append(key, String(item)));
      return;
    }

    searchParams.set(key, String(value));
  });

  const queryString = searchParams.toString();
  return queryString ? `?${queryString}` : "";
}

function isHtmlLikePayload(value: string) {
  const normalized = value.trim().toLowerCase();
  return normalized.startsWith("<!doctype") || normalized.startsWith("<html") || normalized.startsWith("<body");
}

function parseErrorPayload(raw: string, contentType: string) {
  const normalized = raw.trim();
  if (!normalized) {
    return null;
  }

  if (contentType.includes("application/json") || normalized.startsWith("{") || normalized.startsWith("[")) {
    try {
      return JSON.parse(normalized);
    } catch {
      return normalized;
    }
  }

  return normalized;
}

export function extractApiErrorMessage(
  payload: unknown,
  visited = new Set<object>(),
): string | null {
  if (typeof payload === "string" && payload.trim() && !isHtmlLikePayload(payload)) {
    return payload.trim();
  }

  if (Array.isArray(payload)) {
    for (const item of payload) {
      const message = extractApiErrorMessage(item, visited);
      if (message) {
        return message;
      }
    }
    return null;
  }

  if (!payload || typeof payload !== "object") {
    return null;
  }

  if (visited.has(payload as object)) {
    return null;
  }

  visited.add(payload as object);

  const record = payload as Record<string, unknown>;
  const directMessage = record.detail ?? record.message;
  const normalizedDirectMessage = extractApiErrorMessage(directMessage, visited);
  if (normalizedDirectMessage) {
    return normalizedDirectMessage;
  }

  const nonFieldErrors = record.non_field_errors;
  const normalizedNonFieldErrors = extractApiErrorMessage(nonFieldErrors, visited);
  if (normalizedNonFieldErrors) {
    return normalizedNonFieldErrors;
  }

  for (const value of Object.values(record)) {
    const message = extractApiErrorMessage(value, visited);
    if (message) {
      return message;
    }
  }

  return null;
}

export async function apiFetch<T>(path: string, options: ApiFetchOptions = {}) {
  const { method = "GET", query, body, formData, onUploadProgress } = options;
  const url = `/api/backend/${path.replace(/^\/+/, "")}${buildQuery(query)}`;
  const headers = new Headers();

  if (!formData) {
    headers.set("Content-Type", "application/json");
  }

  if (onUploadProgress) {
    const response = await axios.request<T>({
      url,
      method,
      data: formData ?? body,
      withCredentials: true,
      headers: Object.fromEntries(headers.entries()),
      onUploadProgress: (event) => {
        const total = typeof event.total === "number" ? event.total : null;
        const percent = total ? Math.min(100, Math.round((event.loaded / total) * 100)) : 0;
        onUploadProgress({
          loaded: event.loaded,
          total,
          percent,
        });
      },
      validateStatus: () => true,
    });

    if (response.status < 200 || response.status >= 300) {
      const detail = extractApiErrorMessage(response.data) ?? "Falha ao processar a requisição.";
      throw new Error(detail);
    }

    return response.data;
  }

  const response = await fetch(url, {
    method,
    headers,
    body: formData ?? (body === undefined ? undefined : JSON.stringify(body)),
    credentials: "include",
    cache: "no-store",
  });

  if (!response.ok) {
    const contentType = response.headers.get("content-type") ?? "";
    const rawPayload = await response.text().catch(() => "");
    const payload = parseErrorPayload(rawPayload, contentType);
    const detail = extractApiErrorMessage(payload) ?? "Falha ao processar a requisição.";
    throw new Error(detail);
  }

  // 204 No Content / 205 Reset Content — no body to parse
  if (response.status === 204 || response.status === 205) {
    return null as T;
  }

  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    return (await response.json()) as T;
  }

  return (await response.text()) as T;
}
