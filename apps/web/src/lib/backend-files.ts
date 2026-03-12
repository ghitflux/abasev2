import { BACKEND_BASE_URL } from "@/lib/env";

export function buildBackendFileUrl(path?: string | null) {
  if (!path) {
    return "#";
  }

  if (path.startsWith("http://") || path.startsWith("https://")) {
    try {
      const url = new URL(path);
      return `${BACKEND_BASE_URL}${url.pathname}${url.search}`;
    } catch {
      return path;
    }
  }

  return path.startsWith("/") ? `${BACKEND_BASE_URL}${path}` : `${BACKEND_BASE_URL}/${path}`;
}
