import type { ArquivoRetornoDetail, ArquivoRetornoList } from "@/gen/models";

type NumericLike = number | string | null | undefined;

export type ArquivoRetornoFinanceiroGrupo = {
  esperado?: NumericLike;
  recebido?: NumericLike;
  ok?: number;
  total?: number;
  faltando?: number;
  pendente?: NumericLike;
  percentual?: number;
};

export type ArquivoRetornoFinanceiroResumo = ArquivoRetornoFinanceiroGrupo & {
  mensalidades?: ArquivoRetornoFinanceiroGrupo;
  valores_30_50?: ArquivoRetornoFinanceiroGrupo;
};

export type ArquivoRetornoFinanceiroItem = {
  id: number;
  associado_id?: number | null;
  associado_nome: string;
  agente_responsavel?: string;
  matricula?: string;
  cpf_cnpj: string;
  valor?: NumericLike;
  esperado?: NumericLike;
  recebido?: NumericLike;
  status_code?: string;
  status_label?: string;
  ok: boolean;
  situacao_code: string;
  situacao_label: string;
  orgao_pagto?: string;
  relatorio?: string;
  manual_status?: string | null;
  manual_valor?: NumericLike;
  manual_forma_pagamento?: string | null;
  manual_paid_at?: string | null;
  manual_comprovante_path?: string | null;
  origem_baixa?: string;
  arquivo_referencia?: string | null;
  arquivo_disponivel_localmente?: boolean;
  tipo_referencia?: string;
  categoria?: string;
};

export type ArquivoRetornoFinanceiroPayload = {
  resumo: ArquivoRetornoFinanceiroResumo;
  rows: ArquivoRetornoFinanceiroItem[];
};

export type ArquivoRetornoWithFinanceiro = (ArquivoRetornoList | ArquivoRetornoDetail) & {
  financeiro?: ArquivoRetornoFinanceiroResumo | null;
};

export function getArquivoFinanceiroResumo(
  arquivo?: { financeiro?: ArquivoRetornoFinanceiroResumo | null } | null,
) {
  return arquivo?.financeiro ?? null;
}

export function toFinanceiroNumber(value?: NumericLike) {
  if (typeof value === "number") return Number.isFinite(value) ? value : 0;
  if (typeof value !== "string" || !value.trim()) return 0;

  const normalized = value.includes(",") ? value.replaceAll(".", "").replace(",", ".") : value;
  const parsed = Number.parseFloat(normalized);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function toFinanceiroStatus(situacaoCode?: string | null) {
  if (situacaoCode === "ok") return "concluido";
  if (situacaoCode === "bad") return "cancelado";
  return "pendencia_manual";
}
