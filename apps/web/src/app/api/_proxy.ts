import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { refreshWithBackend } from "@/lib/auth/backend";
import { AUTH_COOKIES } from "@/lib/auth/constants";
import { getAccessCookieOptions, getRefreshCookieOptions } from "@/lib/auth/session";
import { API_BASE_URL } from "@/lib/env";

type ProxyBody = FormData | string | ArrayBuffer | undefined;

type AuthState = {
  accessToken?: string;
  refreshToken?: string;
  refreshed: boolean;
};

async function buildBody(request: Request) {
  if (request.method === "GET" || request.method === "HEAD") {
    return undefined;
  }

  const contentType = request.headers.get("content-type") ?? "";
  if (contentType.includes("multipart/form-data")) {
    return request.formData();
  }
  if (contentType.includes("application/json")) {
    return request.text();
  }
  return request.arrayBuffer();
}

async function resolveAuthState(forceRefresh = false): Promise<AuthState> {
  const cookieStore = await cookies();
  let accessToken = forceRefresh
    ? undefined
    : cookieStore.get(AUTH_COOKIES.accessToken)?.value;
  let refreshToken = cookieStore.get(AUTH_COOKIES.refreshToken)?.value;
  let refreshed = false;

  if (!accessToken && refreshToken) {
    const payload = await refreshWithBackend(refreshToken);
    if (payload?.access) {
      accessToken = payload.access;
      refreshToken = payload.refresh ?? refreshToken;
      refreshed = true;
    }
  }

  return { accessToken, refreshToken, refreshed };
}

function buildProxyHeaders(request: Request, body: ProxyBody, accessToken?: string) {
  const headers = new Headers(request.headers);
  headers.delete("host");
  headers.delete("connection");
  headers.delete("content-length");

  if (body instanceof FormData) {
    headers.delete("content-type");
  }

  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  } else {
    headers.delete("Authorization");
  }

  return headers;
}

async function forwardRequest(
  request: Request,
  target: URL,
  body: ProxyBody,
  accessToken?: string,
) {
  return fetch(target, {
    method: request.method,
    headers: buildProxyHeaders(request, body, accessToken),
    body,
    cache: "no-store",
    redirect: "manual",
  });
}

export async function proxyRequestForPath(request: Request, path: string[]) {
  const target = new URL(`${API_BASE_URL}/${path.join("/")}/`);
  const incomingUrl = new URL(request.url);
  incomingUrl.searchParams.forEach((value, key) => {
    target.searchParams.set(key, value);
  });

  const body = await buildBody(request);
  let authState = await resolveAuthState();
  let response = await forwardRequest(request, target, body, authState.accessToken);

  if (response.status === 401 && authState.refreshToken) {
    const refreshedAuthState = await resolveAuthState(true);
    if (refreshedAuthState.accessToken) {
      authState = refreshedAuthState;
      response = await forwardRequest(request, target, body, authState.accessToken);
    }
  }

  const nextHeaders = new Headers();
  const contentType = response.headers.get("content-type");
  if (contentType) {
    nextHeaders.set("content-type", contentType);
  }
  const contentDisposition = response.headers.get("content-disposition");
  if (contentDisposition) {
    nextHeaders.set("content-disposition", contentDisposition);
  }

  const payload = await response.arrayBuffer();
  const nextResponse = new NextResponse(payload, {
    status: response.status,
    headers: nextHeaders,
  });

  if (authState.refreshed && authState.accessToken) {
    nextResponse.cookies.set(
      AUTH_COOKIES.accessToken,
      authState.accessToken,
      getAccessCookieOptions(request),
    );
    if (authState.refreshToken) {
      nextResponse.cookies.set(
        AUTH_COOKIES.refreshToken,
        authState.refreshToken,
        getRefreshCookieOptions(request),
      );
    }
  }

  return nextResponse;
}
