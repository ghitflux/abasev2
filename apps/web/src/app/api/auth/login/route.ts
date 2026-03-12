import { NextResponse } from "next/server";

import { loginWithBackend } from "@/lib/auth/backend";
import { AUTH_COOKIES } from "@/lib/auth/constants";
import {
  accessCookieOptions,
  refreshCookieOptions,
  serializeUser,
  userCookieOptions,
} from "@/lib/auth/session";

function clearSessionCookies(response: NextResponse) {
  response.cookies.delete(AUTH_COOKIES.accessToken);
  response.cookies.delete(AUTH_COOKIES.refreshToken);
  response.cookies.delete(AUTH_COOKIES.user);
  return response;
}

export async function POST(request: Request) {
  try {
    const { email, password } = await request.json();
    const payload = await loginWithBackend(email, password);

    const response = clearSessionCookies(NextResponse.json({ user: payload.user }));
    response.cookies.set(AUTH_COOKIES.accessToken, payload.access, accessCookieOptions);
    response.cookies.set(AUTH_COOKIES.refreshToken, payload.refresh, refreshCookieOptions);
    response.cookies.set(AUTH_COOKIES.user, serializeUser(payload.user), userCookieOptions);
    return response;
  } catch (error) {
    return clearSessionCookies(
      NextResponse.json(
        {
          message: error instanceof Error ? error.message : "Falha ao autenticar.",
        },
        { status: 400 },
      ),
    );
  }
}
