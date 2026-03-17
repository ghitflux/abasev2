import { ACCESS_TOKEN_MAX_AGE, REFRESH_TOKEN_MAX_AGE } from "@/lib/auth/constants";
import type { AuthUser } from "@/types/auth";

const baseCookieOptions = {
  httpOnly: true,
  sameSite: "lax" as const,
  path: "/",
};

function resolveRequestProtocol(request?: Pick<Request, "headers" | "url">) {
  const forwardedProtocol = request?.headers
    .get("x-forwarded-proto")
    ?.split(",")[0]
    ?.trim()
    .toLowerCase();

  if (forwardedProtocol) {
    return forwardedProtocol;
  }

  if (!request?.url) {
    return null;
  }

  try {
    return new URL(request.url).protocol.replace(":", "").toLowerCase();
  } catch {
    return null;
  }
}

function shouldUseSecureCookies(request?: Pick<Request, "headers" | "url">) {
  const protocol = resolveRequestProtocol(request);

  if (protocol) {
    return protocol === "https";
  }

  return process.env.NODE_ENV === "production";
}

export function getAccessCookieOptions(request?: Pick<Request, "headers" | "url">) {
  return {
    ...baseCookieOptions,
    secure: shouldUseSecureCookies(request),
    maxAge: ACCESS_TOKEN_MAX_AGE,
  };
}

export function getRefreshCookieOptions(request?: Pick<Request, "headers" | "url">) {
  return {
    ...baseCookieOptions,
    secure: shouldUseSecureCookies(request),
    maxAge: REFRESH_TOKEN_MAX_AGE,
  };
}

export function getUserCookieOptions(request?: Pick<Request, "headers" | "url">) {
  return {
    ...baseCookieOptions,
    secure: shouldUseSecureCookies(request),
    maxAge: REFRESH_TOKEN_MAX_AGE,
  };
}

export function serializeUser(user: AuthUser) {
  return Buffer.from(JSON.stringify(user), "utf-8").toString("base64url");
}

export function deserializeUser(value?: string | null) {
  if (!value) return null;
  try {
    return JSON.parse(Buffer.from(value, "base64url").toString("utf-8")) as AuthUser;
  } catch {
    return null;
  }
}
