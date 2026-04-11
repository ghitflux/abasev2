import { apiFetch, extractApiErrorMessage } from "./client";

describe("extractApiErrorMessage", () => {
  it("extracts nested serializer errors", () => {
    expect(
      extractApiErrorMessage({
        contratos: [
          {
            cycles: {
              parcelas: [{}, { data_vencimento: ["Data inválida."] }],
            },
          },
        ],
      }),
    ).toBe("Data inválida.");
  });

  it("ignores html payloads", () => {
    expect(extractApiErrorMessage("<html><body>Erro interno</body></html>")).toBeNull();
  });
});

describe("apiFetch", () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
    jest.restoreAllMocks();
  });

  it("surfaces plain text backend errors instead of the generic fallback", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      headers: {
        get: (name: string) => (name === "content-type" ? "text/plain" : null),
      },
      text: async () => "Não foi possível salvar o layout.",
    } as Response);

    await expect(
      apiFetch("admin-overrides/associados/1/save-all/", {
        method: "POST",
        body: { motivo: "teste" },
      }),
    ).rejects.toThrow("Não foi possível salvar o layout.");
  });
});
