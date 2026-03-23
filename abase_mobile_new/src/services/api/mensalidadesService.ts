import { get } from './client';
import { ENDPOINTS } from './constants';
import { onlyDigits } from '@/utils/format';

export type MensalidadeItem = {
  valor: number;
  referencia?: string;
  previsao?: string;
  pago_em?: string;
  status?: string;
  titulo?: string;
  status_code?: string;
};

export type MensalidadesResumo = {
  prazo?: number;
  parcelas_pagas?: number;
  percentual_pago?: number;
  concluidas?: number;
  total?: number;
  pct?: number;
  total_ciclo?: number;
  mensalidade?: number;
};

export type MensalidadesResumoFull = MensalidadesResumo & {
  ref_from?: string;
  ref_to?: string;
  mensalidade?: number;
};

export type MensalidadesResponse = {
  items: MensalidadeItem[];
  resumo?: MensalidadesResumoFull;
  proximo_ciclo?: {
    ref_from?: string;
    ref_to?: string;
    prazo?: number;
    parcelas_pagas?: number;
    percentual_pago?: number;
  } | null;
  refinanciamento?: {
    exists?: boolean;
    cycle_key?: string | null;
    ref1?: string | null;
    ref2?: string | null;
    ref3?: string | null;
  } | null;
};

export function isMensalidadePaga(it: Pick<MensalidadeItem, 'status' | 'status_code'>): boolean {
  const raw = String(it.status_code ?? it.status ?? '').trim().toLowerCase();
  if (!raw) return false;
  if (raw === '1' || raw === '4') return true;
  return /(ok|recebid|descontad|pago|paga)/i.test(raw);
}

function ymdToDMY(s?: string | null): string | undefined {
  const v = (s ?? '').trim();
  if (!v) return undefined;
  if (/^\d{4}-\d{2}-\d{2}$/.test(v)) {
    const [Y, M, D] = v.split('-');
    return `${D}/${M}/${Y}`;
  }
  return v;
}

function mapParcela(p: any): MensalidadeItem {
  const ano = p?.ref_ano ?? p?.ano;
  const mes = p?.ref_mes ?? p?.mes;
  const mm = mes ? String(mes).padStart(2, '0') : undefined;
  const status = p?.status ?? p?.situacao ?? p?.st ?? p?.status_parcela ?? undefined;
  const status_code = p?.status_code != null ? String(p.status_code) : undefined;

  const obj: MensalidadeItem = {
    valor: Number(p?.valor ?? p?.parcela_valor ?? 0),
    referencia: ano && mm ? `${ano}-${mm}` : (p?.referencia || p?.ref || undefined),
    previsao: ymdToDMY(p?.previsao_data ?? p?.previsao ?? p?.data_previsao),
    pago_em: ymdToDMY(p?.pago_em ?? p?.descontado_em ?? p?.data_pagamento ?? p?.data_desconto),
    status,
    titulo: p?.label ?? p?.titulo ?? undefined,
    status_code,
  };

  if (isMensalidadePaga(obj)) {
    if (!obj.pago_em && obj.previsao) {
      obj.pago_em = obj.previsao;
      obj.previsao = undefined;
    }
  }

  return obj;
}

function normalize(json: any): MensalidadesResponse {
  const makeResumo = (items: MensalidadeItem[]): MensalidadesResumo => {
    const total_ciclo = items.reduce((s, it) => s + (Number(it.valor) || 0), 0);
    const concluidas = items.filter(isMensalidadePaga).length;
    const total = items.length;
    const pct = total > 0 ? Math.round((concluidas * 100) / total) : 0;
    return { total_ciclo, concluidas, total, pct };
  };

  if (json && Array.isArray(json.parcelas)) {
    const items = (json.parcelas as any[]).map(mapParcela);
    return { items, resumo: { ...makeResumo(items), ...(json.resumo || {}) } };
  }
  if (Array.isArray(json)) {
    const items = (json as any[]).map(mapParcela);
    return { items, resumo: makeResumo(items) };
  }
  if (json && Array.isArray(json.items)) {
    const items = (json.items as any[]).map(mapParcela);
    return { items, resumo: json.resumo ?? makeResumo(items) };
  }
  if (json && Array.isArray(json.data)) {
    const items = (json.data as any[]).map(mapParcela);
    return { items, resumo: json.resumo ?? makeResumo(items) };
  }
  return { items: [] };
}

export async function getMensalidades(params: {
  cpf: string;
  ref_from?: string;
  ref_to?: string;
}): Promise<MensalidadesResponse> {
  const queryParams: Record<string, string> = {
    cpf: onlyDigits(params.cpf),
  };
  if (params.ref_from) queryParams.ref_from = params.ref_from;
  if (params.ref_to) queryParams.ref_to = params.ref_to;

  try {
    const json = await get<any>(ENDPOINTS.mensalidadesCiclo, queryParams);
    return normalize(json);
  } catch {
    const json = await get<any>(ENDPOINTS.mensalidades, queryParams);
    return normalize(json);
  }
}

export async function getMeuPerfil(): Promise<any | null> {
  try {
    return await get<any>(ENDPOINTS.me);
  } catch {
    return null;
  }
}
