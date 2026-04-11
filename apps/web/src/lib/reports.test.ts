import { apiFetch } from "@/lib/api/client";

import { fetchAllPaginatedRows, filterRowsByReportScope } from "./reports";

jest.mock("@/lib/api/client", () => ({
  apiFetch: jest.fn(),
}));

const mockedApiFetch = jest.mocked(apiFetch);

describe("reports helpers", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("filtra timestamps ISO considerando o dia local", () => {
    const rows = [
      {
        id: 1,
        updated_at: "2026-04-11T00:30:00+03:00",
      },
    ];

    const filtered = filterRowsByReportScope({
      rows,
      scope: "day",
      referenceDate: new Date(2026, 3, 10),
      getCandidates: (row) => [row.updated_at],
    });

    expect(filtered).toHaveLength(1);
    expect(filtered[0]?.id).toBe(1);
  });

  it("busca todas as paginas usando o tamanho real retornado pela API", async () => {
    mockedApiFetch
      .mockResolvedValueOnce({
        count: 400,
        next: "/api/v1/recurso?page=2",
        previous: null,
        results: Array.from({ length: 100 }, (_, index) => ({ id: index + 1 })),
      })
      .mockResolvedValueOnce({
        count: 400,
        next: "/api/v1/recurso?page=3",
        previous: "/api/v1/recurso?page=1",
        results: Array.from({ length: 100 }, (_, index) => ({ id: index + 101 })),
      })
      .mockResolvedValueOnce({
        count: 400,
        next: "/api/v1/recurso?page=4",
        previous: "/api/v1/recurso?page=2",
        results: Array.from({ length: 100 }, (_, index) => ({ id: index + 201 })),
      })
      .mockResolvedValueOnce({
        count: 400,
        next: null,
        previous: "/api/v1/recurso?page=3",
        results: Array.from({ length: 100 }, (_, index) => ({ id: index + 301 })),
      });

    const rows = await fetchAllPaginatedRows<{ id: number }>({
      sourcePath: "recurso",
      pageSize: 200,
    });

    expect(rows).toHaveLength(400);
    expect(mockedApiFetch).toHaveBeenCalledTimes(4);
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      1,
      "recurso",
      expect.objectContaining({
        query: expect.objectContaining({
          page: 1,
          page_size: 200,
        }),
      }),
    );
    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      4,
      "recurso",
      expect.objectContaining({
        query: expect.objectContaining({
          page: 4,
          page_size: 200,
        }),
      }),
    );
  });
});
