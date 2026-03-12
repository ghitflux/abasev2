function normalizeUrl(value?: string) {
  return value?.replace(/\/$/, "");
}

export const API_BASE_URL =
  normalizeUrl(process.env.INTERNAL_API_URL) ??
  normalizeUrl(process.env.NEXT_PUBLIC_API_URL) ??
  "http://127.0.0.1:8001/api/v1";

export const BACKEND_BASE_URL = API_BASE_URL.replace(/\/api\/v1$/, "");
