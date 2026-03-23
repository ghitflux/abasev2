import { get } from './client';
import { ENDPOINTS } from './constants';
import { onlyDigits } from '@/utils/format';

export type CicloStatus = {
  prazo: number;
  parcelas_pagas: number;
  percentual: number;
  elegivel_antecipacao: boolean;
};

export type HistoricoItem = {
  valor: number;
  data?: string;
  status?: string;
  status_label?: string;
};

export type HistoricoResponse = {
  items: HistoricoItem[];
};

function num(v: any): number {
  if (v == null) return 0;
  let s = String(v).replace(/[^\d.,]/g, '');
  if (s.includes('.') && s.includes(',')) s = s.replace(/\./g, '').replace(',', '.');
  else if (s.includes(',')) s = s.replace(',', '.');
  return Number.isFinite(Number(s)) ? Number(s) : 0;
}

function toDMY(iso?: string | null): string | undefined {
  const v = (iso ?? '').trim();
  if (!v) return undefined;
  if (/^\d{4}-\d{2}-\d{2}/.test(v)) {
    const [Y, M, D] = v.slice(0, 10).split('-');
    return `${D}/${M}/${Y}`;
  }
  return v;
}

function statusLabelize(s?: string): { status: string; label: string } {
  const raw = String(s || '').toLowerCase();
  if (raw.includes('pago') || raw.includes('aprov')) return { status: 'aprovado', label: 'Aprovado' };
  if (raw.includes('cancel') || raw.includes('negad') || raw.includes('reprov'))
    return { status: 'reprovado', label: 'Reprovado' };
  if (raw.includes('pend')) return { status: 'pendente', label: 'Pendente' };
  return { status: raw || 'pendente', label: s || 'Pendente' };
}

function normalizeHistorico(json: any): HistoricoResponse {
  const arr: any[] =
    (Array.isArray(json) && json) ||
    (Array.isArray(json?.items) && json.items) ||
    (Array.isArray(json?.data) && json.data) ||
    (Array.isArray(json?.historico) && json.historico) ||
    [];

  const items: HistoricoItem[] = arr.map((r) => {
    const valor = num(r?.valor_pago ?? r?.valor ?? r?.amount ?? 0);
    const data = toDMY(r?.paid_at ?? r?.data_pagamento ?? r?.data_aprovacao ?? r?.created_at);
    const { status, label } = statusLabelize(r?.status ?? r?.situacao ?? r?.status_label ?? '');
    return { valor, data, status, status_label: label };
  });

  return { items };
}

export async function getCicloStatus(): Promise<CicloStatus> {
  const h = await get<any>(ENDPOINTS.home);
  const prazo = Number(h?.resumo?.prazo ?? 0);
  const pagas = Number(h?.resumo?.parcelas_pagas ?? 0);
  let p = Number(h?.resumo?.percentual_pago ?? 0);
  if (!(p > 0) && prazo > 0) p = (pagas * 100) / prazo;
  return {
    prazo,
    parcelas_pagas: pagas,
    percentual: Math.round(p),
    elegivel_antecipacao: Boolean(h?.resumo?.elegivel_antecipacao),
  };
}

export async function getHistoricoAntecipacoes(params?: {
  cpf?: string;
}): Promise<HistoricoResponse> {
  const queryParams: Record<string, string> = {};
  if (params?.cpf) queryParams.cpf = onlyDigits(params.cpf);

  try {
    const json = await get<any>(ENDPOINTS.antecipacaoHistorico, queryParams);
    const norm = normalizeHistorico(json);
    if (norm.items.length > 0) return norm;
  } catch {
    // fallback silencioso
  }

  try {
    const json = await get<any>(ENDPOINTS.v1Antecipacao);
    return normalizeHistorico(json);
  } catch {
    return { items: [] };
  }
}
