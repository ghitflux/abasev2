import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { logoutWithBackend } from "@/lib/auth/backend";
import { AUTH_COOKIES } from "@/lib/auth/constants";

export async function POST() {
  const cookieStore = await cookies();
  const refreshToken = cookieStore.get(AUTH_COOKIES.refreshToken)?.value;

  if (refreshToken) {
    await logoutWithBackend(refreshToken);
  }

  const response = NextResponse.json({ ok: true });
  response.cookies.delete(AUTH_COOKIES.accessToken);
  response.cookies.delete(AUTH_COOKIES.refreshToken);
  response.cookies.delete(AUTH_COOKIES.user);
  return response;
}
