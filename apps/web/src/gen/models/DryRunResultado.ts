/* Generated manually — do not overwrite with Kubb unless regenerating importacao endpoints. */

export type DryRunValores3050Grupo = {
  count: number;
  valor_total: string;
};

export type DryRunValores3050 = {
  descontaram: DryRunValores3050Grupo;
  nao_descontaram: DryRunValores3050Grupo;
};

export type DryRunMudancaStatus = {
  antes: string;
  depois: string;
  count: number;
};

export type DryRunKpis = {
  total_no_arquivo: number;
  atualizados: number;
  baixa_efetuada: number;
  nao_descontado: number;
  nao_encontrado: number;
  pendencia_manual: number;
  ciclo_aberto: number;
  valor_previsto: string;
  valor_real: string;
  aptos_a_renovar: number;
  valores_30_50: DryRunValores3050;
  mudancas_status_associado: DryRunMudancaStatus[];
  mudancas_status_ciclo: DryRunMudancaStatus[];
};

export type DryRunItemResultado =
  | "baixa_efetuada"
  | "nao_descontado"
  | "nao_encontrado"
  | "pendencia_manual"
  | "ciclo_aberto"
  | "erro";

export type DryRunItemCategoria = "mensalidades" | "valores_30_50" | "outros";

export type DryRunItem = {
  linha_numero: number | null;
  cpf_cnpj: string;
  nome_servidor: string;
  matricula_servidor: string;
  orgao_pagto_nome: string;
  valor_descontado: string;
  status_codigo: string;
  resultado: DryRunItemResultado;
  associado_id: number | null;
  associado_nome: string;
  associado_status_antes: string | null;
  associado_status_depois: string | null;
  ciclo_status_antes: string | null;
  ciclo_status_depois: string | null;
  ficara_apto_renovar: boolean;
  categoria: DryRunItemCategoria;
};

export type DryRunResultado = {
  kpis: DryRunKpis;
  items: DryRunItem[];
};
