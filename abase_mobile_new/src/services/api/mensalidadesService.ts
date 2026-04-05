import { get } from './client';
import { ENDPOINTS } from './constants';
import { onlyDigits } from '@/utils/format';

export type MensalidadeItem = {
  id?: number | string;
  numero?: number;
  valor: number;
  referencia?: string;
  previsao?: string;
  pago_em?: string;
  status?: string;
  titulo?: string;
  status_code?: string;
  observacao?: string;
  contrato_id?: number;
  contrato_codigo?: string;
  source?: string;
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

export type MensalidadeCycle = {
  id: string;
  contrato_id?: number;
  contrato_codigo?: string;
  numero?: number;
  status?: string;
  status_visual_slug?: string;
  status_visual_label?: string;
  valor_total?: number;
  primeira_competencia_ciclo?: string;
  ultima_competencia_ciclo?: string;
  resumo_referencias?: string;
  items: MensalidadeItem[];
};

export type MensalidadesResponse = {
  items: MensalidadeItem[];
  cycles: MensalidadeCycle[];
  meses_nao_pagos: MensalidadeItem[];
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
  return /(ok|recebid|descontad|liquidad|quitad|pago|paga)/i.test(raw);
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

function normalizeReference(ref?: string | null): string | undefined {
  const value = String(ref ?? '').trim();
  if (!value) return undefined;
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return value.slice(0, 7);
  if (/^\d{4}-\d{2}$/.test(value)) return value;
  return value;
}

function mapParcela(p: any): MensalidadeItem {
  const ano = p?.ref_ano ?? p?.ano;
  const mes = p?.ref_mes ?? p?.mes;
  const mm = mes ? String(mes).padStart(2, '0') : undefined;
  const status = p?.status ?? p?.situacao ?? p?.st ?? p?.status_parcela ?? undefined;
  const status_code = p?.status_code != null ? String(p.status_code) : undefined;
  const referencia =
    ano && mm
      ? `${ano}-${mm}`
      : normalizeReference(p?.referencia_mes ?? p?.referencia ?? p?.ref);

  const obj: MensalidadeItem = {
    id: p?.id,
    numero: p?.numero != null ? Number(p.numero) : undefined,
    valor: Number(p?.valor ?? p?.parcela_valor ?? 0),
    referencia,
    previsao: ymdToDMY(p?.previsao_data ?? p?.previsao ?? p?.data_previsao ?? p?.data_vencimento),
    pago_em: ymdToDMY(p?.pago_em ?? p?.descontado_em ?? p?.data_pagamento ?? p?.data_desconto),
    status,
    titulo: p?.label ?? p?.titulo ?? undefined,
    status_code,
    observacao: p?.observacao ?? undefined,
    contrato_id: p?.contrato_id != null ? Number(p.contrato_id) : undefined,
    contrato_codigo: p?.contrato_codigo ?? undefined,
    source: p?.source ?? undefined,
  };

  if (isMensalidadePaga(obj) && !obj.pago_em && obj.previsao) {
    obj.pago_em = obj.previsao;
    obj.previsao = undefined;
  }

  return obj;
}

function buildResumo(items: MensalidadeItem[]): MensalidadesResumo {
  const total_ciclo = items.reduce((sum, item) => sum + (Number(item.valor) || 0), 0);
  const concluidas = items.filter(isMensalidadePaga).length;
  const total = items.length;
  const pct = total > 0 ? Math.round((concluidas * 100) / total) : 0;
  return { total_ciclo, concluidas, total, pct };
}

function mapCycle(cycle: any, index: number): MensalidadeCycle {
  const items = Array.isArray(cycle?.parcelas) ? cycle.parcelas.map(mapParcela) : [];
  return {
    id: String(cycle?.id ?? `cycle-${index}`),
    contrato_id: cycle?.contrato_id != null ? Number(cycle.contrato_id) : undefined,
    contrato_codigo: cycle?.contrato_codigo ?? undefined,
    numero: cycle?.numero != null ? Number(cycle.numero) : undefined,
    status: cycle?.status ?? undefined,
    status_visual_slug: cycle?.status_visual_slug ?? undefined,
    status_visual_label: cycle?.status_visual_label ?? undefined,
    valor_total: Number(cycle?.valor_total ?? 0),
    primeira_competencia_ciclo: normalizeReference(cycle?.primeira_competencia_ciclo),
    ultima_competencia_ciclo: normalizeReference(cycle?.ultima_competencia_ciclo),
    resumo_referencias: cycle?.resumo_referencias ?? undefined,
    items,
  };
}

function buildFallbackCycle(items: MensalidadeItem[], resumo?: MensalidadesResumoFull | null): MensalidadeCycle | null {
  if (!items.length) return null;
  const referencias = items
    .map((item) => item.referencia)
    .filter((value): value is string => Boolean(value))
    .sort();
  return {
    id: 'legacy-cycle',
    numero: 1,
    status_visual_label: 'Ciclo',
    valor_total: Number(resumo?.total_ciclo ?? buildResumo(items).total_ciclo ?? 0),
    primeira_competencia_ciclo: referencias[0],
    ultima_competencia_ciclo: referencias[referencias.length - 1],
    resumo_referencias: referencias
      .map((value) => {
        const [year, month] = value.split('-');
        return `${month}/${year}`;
      })
      .join(', '),
    items,
  };
}

function normalize(json: any): MensalidadesResponse {
  const legacyItems = json && Array.isArray(json.parcelas)
    ? (json.parcelas as any[]).map(mapParcela)
    : Array.isArray(json)
      ? (json as any[]).map(mapParcela)
      : json && Array.isArray(json.items)
        ? (json.items as any[]).map(mapParcela)
        : json && Array.isArray(json.data)
          ? (json.data as any[]).map(mapParcela)
          : [];

  const cyclesFromApi = json && Array.isArray(json.ciclos)
    ? (json.ciclos as any[]).map(mapCycle).filter((cycle) => cycle.items.length > 0)
    : [];
  const fallbackCycle = !cyclesFromApi.length ? buildFallbackCycle(legacyItems, json?.resumo) : null;
  const cycles = cyclesFromApi.length ? cyclesFromApi : fallbackCycle ? [fallbackCycle] : [];
  const items = legacyItems.length ? legacyItems : cycles.flatMap((cycle) => cycle.items);
  const meses_nao_pagos = json && Array.isArray(json.meses_nao_pagos)
    ? (json.meses_nao_pagos as any[]).map(mapParcela)
    : [];

  return {
    items,
    cycles,
    meses_nao_pagos,
    resumo: json?.resumo ?? buildResumo(items),
    proximo_ciclo: json?.proximo_ciclo ?? null,
    refinanciamento: json?.refinanciamento ?? null,
  };
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

  const json = await get<any>(ENDPOINTS.appMensalidades, queryParams);
  return normalize(json);
}

export async function getMeuPerfil(): Promise<any | null> {
  try {
    return await get<any>(ENDPOINTS.appMe);
  } catch {
    return null;
  }
}
