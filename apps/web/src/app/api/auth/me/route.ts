import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { getCurrentUser, refreshWithBackend } from "@/lib/auth/backend";
import { AUTH_COOKIES } from "@/lib/auth/constants";
import {
  getAccessCookieOptions,
  getRefreshCookieOptions,
  getUserCookieOptions,
  serializeUser,
} from "@/lib/auth/session";

function clearSessionCookies(response: NextResponse) {
  response.cookies.delete(AUTH_COOKIES.accessToken);
  response.cookies.delete(AUTH_COOKIES.refreshToken);
  response.cookies.delete(AUTH_COOKIES.user);
  return response;
}

export async function GET(request: Request) {
  try {
    const cookieStore = await cookies();
    const accessToken = cookieStore.get(AUTH_COOKIES.accessToken)?.value;
    const refreshToken = cookieStore.get(AUTH_COOKIES.refreshToken)?.value;

    let nextAccessToken = accessToken;
    let nextRefreshToken = refreshToken;
    let shouldPersistSession = false;

    if (!nextAccessToken && nextRefreshToken) {
      const refreshed = await refreshWithBackend(nextRefreshToken);
      nextAccessToken = refreshed?.access;
      nextRefreshToken = refreshed?.refresh ?? nextRefreshToken;
      shouldPersistSession = Boolean(refreshed?.access);
    }

    if (!nextAccessToken) {
      return clearSessionCookies(
        NextResponse.json({ message: "Sessão não encontrada." }, { status: 401 }),
      );
    }

    let user = await getCurrentUser(nextAccessToken);
    if (!user && nextRefreshToken) {
      const refreshed = await refreshWithBackend(nextRefreshToken);
      if (refreshed?.access) {
        nextAccessToken = refreshed.access;
        nextRefreshToken = refreshed.refresh ?? nextRefreshToken;
        shouldPersistSession = true;
        user = await getCurrentUser(nextAccessToken);
      }
    }

    if (!user) {
      return clearSessionCookies(
        NextResponse.json({ message: "Sessão inválida." }, { status: 401 }),
      );
    }

    const response = NextResponse.json({ user });
    if (shouldPersistSession || accessToken !== nextAccessToken) {
      response.cookies.set(
        AUTH_COOKIES.accessToken,
        nextAccessToken,
        getAccessCookieOptions(request),
      );
    }
    if (nextRefreshToken && (shouldPersistSession || refreshToken !== nextRefreshToken)) {
      response.cookies.set(
        AUTH_COOKIES.refreshToken,
        nextRefreshToken,
        getRefreshCookieOptions(request),
      );
    }
    response.cookies.set(
      AUTH_COOKIES.user,
      serializeUser(user),
      getUserCookieOptions(request),
    );
    return response;
  } catch {
    return clearSessionCookies(
      NextResponse.json({ message: "Sessão indisponível." }, { status: 401 }),
    );
  }
}
