export const ROLES = [
  "ADMIN",
  "AGENTE",
  "ANALISTA",
  "COORDENADOR",
  "TESOUREIRO",
] as const;

export type Role = (typeof ROLES)[number];

export const ESTEIRA_STATUS = [
  "cadastro",
  "analise",
  "coordenacao",
  "tesouraria",
  "concluido",
  "pendencia",
] as const;

export type EsteiraStatus = (typeof ESTEIRA_STATUS)[number];

export const IMPORTACAO_STATUS = [
  "pendente",
  "processando",
  "concluido",
  "erro",
] as const;

export type ImportacaoStatus = (typeof IMPORTACAO_STATUS)[number];
