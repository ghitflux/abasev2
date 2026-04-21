/** @jest-environment jsdom */

import { cookies } from "next/headers";
import { refreshWithBackend } from "@/lib/auth/backend";

jest.mock("next/server", () => ({
  NextResponse: class MockNextResponse {
    status: number;
    headers: Headers;
    cookies: { set: jest.Mock };
    body: unknown;

    constructor(body: unknown, init?: { status?: number; headers?: HeadersInit }) {
      this.status = init?.status ?? 200;
      this.headers = new Headers(init?.headers);
      this.cookies = { set: jest.fn() };
      this.body = body;
    }
  },
}));

jest.mock("next/headers", () => ({
  cookies: jest.fn(),
}));

jest.mock("@/lib/auth/backend", () => ({
  refreshWithBackend: jest.fn(),
}));

jest.mock("@/lib/auth/session", () => ({
  getAccessCookieOptions: jest.fn(() => ({})),
  getRefreshCookieOptions: jest.fn(() => ({})),
}));

const mockedCookies = jest.mocked(cookies);
const mockedRefreshWithBackend = jest.mocked(refreshWithBackend);

describe("proxyRequestForPath", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    jest.clearAllMocks();
    mockedCookies.mockResolvedValue({
      get: () => undefined,
    } as never);
    mockedRefreshWithBackend.mockResolvedValue(null);
    global.fetch = jest.fn().mockResolvedValue(
      {
        status: 200,
        headers: {
          get: (name: string) =>
            name.toLowerCase() === "content-type" ? "application/json" : null,
        },
        arrayBuffer: async () => new Uint8Array([123, 125]).buffer,
      },
    ) as typeof global.fetch;
  });

  afterAll(() => {
    global.fetch = originalFetch;
  });

  it("preserva parametros repetidos da query ao encaminhar para o backend", async () => {
    const { proxyRequestForPath } = await import("@/app/api/_proxy");
    const request = {
      method: "GET",
      url: "http://localhost:3000/api/backend/contratos?page=1&status_renovacao=apto_a_renovar&status_renovacao=pendente_termo_agente",
      headers: new Headers(),
    } as unknown as Request;

    const response = await proxyRequestForPath(request, ["contratos"]);

    expect(response.status).toBe(200);
    expect(global.fetch).toHaveBeenCalledTimes(1);

    const [target] = jest.mocked(global.fetch).mock.calls[0] ?? [];
    expect(target).toBeInstanceOf(URL);

    const proxiedUrl = target as URL;
    expect(proxiedUrl.pathname).toBe("/api/v1/contratos/");
    expect(proxiedUrl.searchParams.getAll("status_renovacao")).toEqual([
      "apto_a_renovar",
      "pendente_termo_agente",
    ]);
    expect(proxiedUrl.searchParams.get("page")).toBe("1");
  });

  it("nao encaminha body ao reconstruir respostas 204", async () => {
    global.fetch = jest.fn().mockResolvedValue(
      {
        status: 204,
        headers: {
          get: () => null,
        },
        arrayBuffer: async () => new Uint8Array().buffer,
      },
    ) as typeof global.fetch;

    const { proxyRequestForPath } = await import("@/app/api/_proxy");
    const request = {
      method: "POST",
      url: "http://localhost:3000/api/backend/importacao/arquivo-retorno/46/cancelar",
      headers: new Headers(),
      arrayBuffer: async () => new Uint8Array().buffer,
      text: async () => "",
      formData: async () => new FormData(),
    } as unknown as Request;

    const response = await proxyRequestForPath(request, [
      "importacao",
      "arquivo-retorno",
      "46",
      "cancelar",
    ]);

    expect(response.status).toBe(204);
    expect(response.body).toBeNull();
  });
});
