import { BACKEND_BASE_URL } from "@/lib/env";

export function buildBackendFileUrl(path?: string | null) {
  if (!path) {
    return "#";
  }

  if (path.startsWith("http://") || path.startsWith("https://")) {
    try {
      const url = new URL(path);
      const normalizedPath = url.pathname.replace(/^\/media\/?/, "");
      if (normalizedPath !== url.pathname.replace(/^\//, "")) {
        return `/api/media/${normalizedPath}${url.search}`;
      }
      return `${BACKEND_BASE_URL}${url.pathname}${url.search}`;
    } catch {
      return path;
    }
  }

  if (path.startsWith("/media/")) {
    return `/api/media/${path.replace(/^\/media\/?/, "")}`;
  }
  if (path.startsWith("media/")) {
    return `/api/media/${path.replace(/^media\/?/, "")}`;
  }

  return `/api/media/${path.replace(/^\/+/, "")}`;
}
