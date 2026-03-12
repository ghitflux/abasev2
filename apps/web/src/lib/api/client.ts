"use client";

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

function extractApiErrorMessage(payload: unknown) {
  if (!payload || typeof payload !== "object") {
    return null;
  }

  const record = payload as Record<string, unknown>;
  const directMessage = record.detail ?? record.message;
  if (typeof directMessage === "string" && directMessage.trim()) {
    return directMessage;
  }

  const nonFieldErrors = record.non_field_errors;
  if (
    Array.isArray(nonFieldErrors) &&
    typeof nonFieldErrors[0] === "string" &&
    nonFieldErrors[0].trim()
  ) {
    return nonFieldErrors[0];
  }

  for (const value of Object.values(record)) {
    if (typeof value === "string" && value.trim()) {
      return value;
    }

    if (Array.isArray(value) && typeof value[0] === "string" && value[0].trim()) {
      return value[0];
    }
  }

  return null;
}

export async function apiFetch<T>(path: string, options: ApiFetchOptions = {}) {
  const { method = "GET", query, body, formData } = options;
  const headers = new Headers();

  if (!formData) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`/api/backend/${path.replace(/^\/+/, "")}${buildQuery(query)}`, {
    method,
    headers,
    body: formData ?? (body === undefined ? undefined : JSON.stringify(body)),
    credentials: "include",
    cache: "no-store",
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail = extractApiErrorMessage(payload) ?? "Falha ao processar a requisição.";
    throw new Error(detail);
  }

  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    return (await response.json()) as T;
  }

  return (await response.text()) as T;
}
