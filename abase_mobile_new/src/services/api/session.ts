import * as SecureStore from 'expo-secure-store';

export const ACCESS_TOKEN_KEY = 'Abase.token';
export const REFRESH_TOKEN_KEY = 'Abase.refresh';
export const SESSION_KEY = 'Abase.session';

function looksLikeJwt(value?: string | null) {
  return typeof value === 'string' && value.split('.').length === 3;
}

export async function getStoredAccessToken() {
  return SecureStore.getItemAsync(ACCESS_TOKEN_KEY);
}

export async function getStoredRefreshToken() {
  return SecureStore.getItemAsync(REFRESH_TOKEN_KEY);
}

export async function persistTokens(accessToken: string, refreshToken?: string | null) {
  await SecureStore.setItemAsync(ACCESS_TOKEN_KEY, accessToken).catch(() => {});
  if (refreshToken) {
    await SecureStore.setItemAsync(REFRESH_TOKEN_KEY, refreshToken).catch(() => {});
  } else {
    await SecureStore.deleteItemAsync(REFRESH_TOKEN_KEY).catch(() => {});
  }
}

export async function clearStoredTokens() {
  await Promise.all([
    SecureStore.deleteItemAsync(ACCESS_TOKEN_KEY).catch(() => {}),
    SecureStore.deleteItemAsync(REFRESH_TOKEN_KEY).catch(() => {}),
    SecureStore.deleteItemAsync(SESSION_KEY).catch(() => {}),
  ]);
}

export async function readValidStoredTokens() {
  const [accessToken, refreshToken] = await Promise.all([
    getStoredAccessToken(),
    getStoredRefreshToken(),
  ]);

  if (looksLikeJwt(accessToken) && looksLikeJwt(refreshToken)) {
    return { accessToken, refreshToken };
  }

  if (accessToken || refreshToken) {
    await clearStoredTokens();
  }

  return { accessToken: null, refreshToken: null };
}
