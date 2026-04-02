import { ACCESS_TOKEN_MAX_AGE, REFRESH_TOKEN_MAX_AGE } from "@/lib/auth/constants";

describe("auth constants", () => {
  it("mantem access token por 48 horas e refresh por 7 dias", () => {
    expect(ACCESS_TOKEN_MAX_AGE).toBe(60 * 60 * 48);
    expect(REFRESH_TOKEN_MAX_AGE).toBe(60 * 60 * 24 * 7);
  });
});
