import { NextResponse, type NextRequest } from "next/server";

import { AUTH_COOKIES } from "@/lib/auth/constants";

const PUBLIC_PATHS = ["/login"];

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const accessToken = request.cookies.get(AUTH_COOKIES.accessToken)?.value;
  const refreshToken = request.cookies.get(AUTH_COOKIES.refreshToken)?.value;
  const hasSession = Boolean(accessToken || refreshToken);
  const isApiRoute = pathname.startsWith("/api");
  const isAuthPage = PUBLIC_PATHS.some((path) => pathname.startsWith(path));

  if (isApiRoute) {
    if (!accessToken) {
      return NextResponse.next();
    }

    const headers = new Headers(request.headers);
    headers.set("Authorization", `Bearer ${accessToken}`);
    return NextResponse.next({ request: { headers } });
  }

  if (!hasSession && !isAuthPage) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)"],
};
