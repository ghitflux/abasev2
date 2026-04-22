export const MENSALIDADE_FAIXAS = [
  { value: "ate_100", label: "Até R$ 100" },
  { value: "100_200", label: "R$ 100 a R$ 199,99" },
  { value: "200_300", label: "R$ 200 a R$ 299,99" },
  { value: "300_500", label: "R$ 300 a R$ 499,99" },
  { value: "acima_500", label: "Acima de R$ 500" },
] as const;

export const PARCELAS_PAGAS_FAIXAS = [
  { value: "1_parcela_paga", label: "1 ou mais parcelas pagas" },
  { value: "3_parcelas_pagas", label: "3 ou mais parcelas pagas" },
] as const;
