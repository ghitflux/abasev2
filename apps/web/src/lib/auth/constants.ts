export const AUTH_COOKIES = {
  accessToken: "access_token",
  refreshToken: "refresh_token",
  user: "auth_user",
} as const;

export const ACCESS_TOKEN_MAX_AGE = 60 * 60 * 48;
export const REFRESH_TOKEN_MAX_AGE = 60 * 60 * 24 * 7;
