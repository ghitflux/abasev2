import { ACCESS_TOKEN_MAX_AGE, REFRESH_TOKEN_MAX_AGE } from "@/lib/auth/constants";
import type { AuthUser } from "@/types/auth";

const secure = process.env.NODE_ENV === "production";

export const accessCookieOptions = {
  httpOnly: true,
  sameSite: "lax" as const,
  secure,
  path: "/",
  maxAge: ACCESS_TOKEN_MAX_AGE,
};

export const refreshCookieOptions = {
  httpOnly: true,
  sameSite: "lax" as const,
  secure,
  path: "/",
  maxAge: REFRESH_TOKEN_MAX_AGE,
};

export const userCookieOptions = {
  httpOnly: true,
  sameSite: "lax" as const,
  secure,
  path: "/",
  maxAge: REFRESH_TOKEN_MAX_AGE,
};

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
