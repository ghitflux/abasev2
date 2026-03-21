import {
  formatDate,
  formatDateTime,
  formatLongMonthYear,
  formatMonthYear,
} from "./formatters";

describe("formatters timezone", () => {
  it("renders datetime values in America/Fortaleza", () => {
    expect(formatDateTime("2026-03-21T13:36:00Z")).toBe("21/03/2026 10:36");
  });

  it("keeps date-only values stable", () => {
    expect(formatDate("2026-03-21")).toBe("21/03/2026");
    expect(formatMonthYear("2026-03")).toBe("mar/2026");
    expect(formatLongMonthYear("2026-03")).toBe("março de 2026");
  });
});
