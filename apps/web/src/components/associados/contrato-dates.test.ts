import {
  calculateContratoDates,
  formatMonthYear,
  getMonthlyChargeDate,
} from "./contrato-dates";

describe("contrato-dates", () => {
  it("calcula a primeira mensalidade um mes apos a averbacao quando aprovado apos o dia cinco", () => {
    const approvalDate = new Date(2026, 2, 11);

    const result = calculateContratoDates(approvalDate);

    expect(result.dataPrimeiraMensalidade).toEqual(new Date(2026, 4, 5));
    expect(result.mesAverbacao).toEqual(new Date(2026, 3, 1));
  });

  it("usa a data de fallback quando a aprovacao nao foi informada", () => {
    const result = calculateContratoDates(undefined, new Date(2026, 2, 11));

    expect(result.dataAprovacao).toEqual(new Date(2026, 2, 11));
    expect(result.dataPrimeiraMensalidade).toEqual(new Date(2026, 4, 5));
  });

  it("mantem a averbacao no mesmo mes quando aprovado ate o dia cinco", () => {
    const result = calculateContratoDates(new Date(2026, 2, 5));

    expect(result.mesAverbacao).toEqual(new Date(2026, 2, 1));
    expect(result.dataPrimeiraMensalidade).toEqual(new Date(2026, 3, 5));
  });

  it("usa sempre o dia cinco para a cobranca mensal", () => {
    const chargeDate = getMonthlyChargeDate(new Date(2026, 7, 1));

    expect(chargeDate).toEqual(new Date(2026, 7, 5));
    expect(formatMonthYear(chargeDate)).toBe("08/2026");
  });
});
