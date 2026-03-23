import { get, post } from './client';
import { ENDPOINTS, BASE_URL } from './constants';
import { fetchPendencias, type DocIssue } from './pendenciasService';

export const OPEN_ISSUE_STATUSES = new Set(['open', 'waiting_user', 'received', 'rejected']);

function normalize(val?: string | null) {
  return String(val || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();
}

function pad2(n: number) { return n < 10 ? `0${n}` : String(n); }

const MONTHS_PT = [
  'janeiro','fevereiro','março','abril','maio','junho',
  'julho','agosto','setembro','outubro','novembro','dezembro',
];

function parseISODate(d?: string | null): Date | null {
  if (!d) return null;
  const s = String(d).trim();
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (m) {
    const dt = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
    return isNaN(dt.getTime()) ? null : dt;
  }
  const ym = s.match(/^(\d{4})-(\d{2})$/);
  if (ym) {
    const dt = new Date(Number(ym[1]), Number(ym[2]) - 1, 1);
    return isNaN(dt.getTime()) ? null : dt;
  }
  const dt = new Date(s);
  return isNaN(dt.getTime()) ? null : dt;
}

function brDate(d: Date) {
  return `${pad2(d.getDate())}/${pad2(d.getMonth() + 1)}/${d.getFullYear()}`;
}

function monthYear(d: Date) {
  const m = MONTHS_PT[d.getMonth()];
  return `${m.charAt(0).toUpperCase()}${m.slice(1)} de ${d.getFullYear()}`;
}

function addMonths(d: Date, m: number) {
  const lastDay = new Date(d.getFullYear(), d.getMonth() + m + 1, 0).getDate();
  return new Date(d.getFullYear(), d.getMonth() + m, Math.min(d.getDate(), lastDay));
}

function toAbsUrl(maybe: any): string | null {
  const s = String(maybe || '').trim();
  if (!s) return null;
  if (/^https?:\/\//i.test(s)) return s;
  const origin = BASE_URL.match(/^https?:\/\/[^/]+/i)?.[0] ?? '';
  if (!origin) return null;
  return s.startsWith('/') ? `${origin}${s}` : `${origin}/${s}`;
}

export type ParcelaResumo = {
  index: number;
  dateISO: string;
  dateLabel: string;
  monthLabel: string;
  amount: number;
};

export type EsperaResumo = {
  exists: boolean;
  status: string;
  status_norm: string;
  aprovado: boolean;
  complete: boolean;
  hasOpenIssues: boolean;
  openIssues: DocIssue[];
  dados: {
    limiteDisponivel: number | null;
    limiteDeterminado: number | null;
    mensalidade: number | null;
    prazo: number | null;
    dataPrimeira: string | null;
    mesAverbacaoLabel: string | null;
    doacaoAssociado: number | null;
    diaCobranca: number | null;
    schedule: ParcelaResumo[];
  };
  permissions?: { auxilio1: boolean; auxilio2: boolean };
  aceiteTermos: boolean;
  termos?: {
    adesaoUrl: string | null;
    antecipacaoUrl: string | null;
    adesaoUserUploaded: boolean;
    antecipacaoUserUploaded: boolean;
  };
  liberado1?: boolean;
  liberado2?: boolean;
};

const COMPLETE_SET = new Set([
  'em analise','em-analise','em_analise','analise','em análise',
  'enviado','enviada','recebido','recebida','em avaliacao','avaliacao',
  'em avaliação','em revisao','em revisão','em processamento','aprovado','aprovada',
]);

function isLiberadoLike(s?: string | null) {
  const n = normalize(s);
  return n.includes('liber') || n.includes('aprov') || n.includes('ativ') || n.includes('finaliz') || n.includes('conclu');
}

export async function getEsperaResumo(): Promise<EsperaResumo> {
  const status = await get<any>(ENDPOINTS.appCadastro);
  const st = (status as any)?.status ?? 'Pendente';
  const norm = normalize(st);
  const exists = !!(status as any)?.exists;

  let complete = Boolean((status as any)?.complete);
  if (!complete) complete = COMPLETE_SET.has(norm);

  const aprovado = norm === 'aprovado' || norm === 'aprovada';
  const cad = (status as any)?.cadastro ?? (status as any);

  const mensalidade = cad?.contrato_mensalidade != null ? Number(cad.contrato_mensalidade) : null;
  const prazo = cad?.contrato_prazo_meses != null ? Number(cad.contrato_prazo_meses) : null;
  const doacaoAssociado = cad?.contrato_doacao_associado ?? null;

  let firstCharge = parseISODate(cad?.contrato_data_envio_primeira);
  if (!firstCharge) {
    const mesAverb = parseISODate(cad?.contrato_mes_averbacao);
    if (mesAverb) firstCharge = new Date(mesAverb.getFullYear(), mesAverb.getMonth(), 5);
  }
  if (!firstCharge) {
    const apr = parseISODate(cad?.contrato_data_aprovacao);
    if (apr) firstCharge = new Date(apr.getFullYear(), apr.getMonth() + 1, 5);
  }

  const mesAverb = parseISODate(cad?.contrato_mes_averbacao);
  const mesAverbacaoLabel = mesAverb ? monthYear(mesAverb) : null;
  const diaCobranca = firstCharge ? firstCharge.getDate() : null;

  const schedule: ParcelaResumo[] = [];
  if (firstCharge && mensalidade != null && Number.isFinite(mensalidade)) {
    const len = Math.min(Math.max(3, prazo ?? 3), 60);
    for (let i = 0; i < len; i++) {
      const d = addMonths(firstCharge, i);
      schedule.push({
        index: i + 1,
        dateISO: `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`,
        dateLabel: brDate(d),
        monthLabel: monthYear(d),
        amount: mensalidade,
      });
    }
  }

  let openIssues: DocIssue[] = [];
  try {
    const pend = await fetchPendencias();
    openIssues = (pend?.issues || []).filter((i) => OPEN_ISSUE_STATUSES.has(normalize(i.status)));
  } catch { /* silencioso */ }

  const aceiteTermos = Boolean(
    (status as any)?.aceite_termos ?? (status as any)?.aceiteTermos ?? cad?.aceite_termos,
  );
  const termosRaw = (status as any)?.termos || {};

  const adesaoUrl =
    toAbsUrl(termosRaw.adesao_admin_url) ??
    toAbsUrl(termosRaw.termo_adesao_url) ??
    toAbsUrl(cad?.termo_adesao_admin_path) ?? null;

  const antecipacaoUrl =
    toAbsUrl(termosRaw.antecipacao_admin_url) ??
    toAbsUrl(termosRaw.termo_antecipacao_url) ??
    toAbsUrl(cad?.termo_antecipacao_admin_path) ?? null;

  const pRaw1 = (status as any)?.permissions?.auxilio1;
  const pRaw2 = (status as any)?.permissions?.auxilio2;
  const aux1 =
    pRaw1 === true ||
    normalize(typeof pRaw1 === 'string' ? pRaw1 : '') === 'allowed' ||
    (status as any)?.auxilios?.auxilio1?.allowed === true;
  const aux2 =
    pRaw2 === true ||
    normalize(typeof pRaw2 === 'string' ? pRaw2 : '') === 'allowed' ||
    (status as any)?.auxilios?.auxilio2?.allowed === true;

  const aux1StatusText = String(cad?.auxilio1_status ?? (status as any)?.auxilio1_status ?? '');
  const aux2StatusText = String(cad?.auxilio2_status ?? (status as any)?.auxilio2_status ?? '');

  return {
    exists,
    status: st,
    status_norm: norm,
    aprovado,
    complete,
    hasOpenIssues: openIssues.length > 0,
    openIssues,
    dados: {
      limiteDisponivel: cad?.contrato_margem_disponivel ?? null,
      limiteDeterminado: cad?.contrato_valor_antecipacao ?? null,
      mensalidade: mensalidade != null && Number.isFinite(mensalidade) ? mensalidade : null,
      prazo: prazo != null && Number.isFinite(prazo) ? prazo : null,
      dataPrimeira: firstCharge
        ? `${firstCharge.getFullYear()}-${pad2(firstCharge.getMonth() + 1)}-${pad2(firstCharge.getDate())}`
        : null,
      mesAverbacaoLabel,
      doacaoAssociado,
      diaCobranca,
      schedule,
    },
    permissions: { auxilio1: !!aux1, auxilio2: !!aux2 },
    aceiteTermos,
    termos: {
      adesaoUrl,
      antecipacaoUrl,
      adesaoUserUploaded: !!(termosRaw.adesao_user_uploaded ?? false),
      antecipacaoUserUploaded: !!(termosRaw.antecipacao_user_uploaded ?? false),
    },
    liberado1: Boolean(aux1 || isLiberadoLike(aux1StatusText)),
    liberado2: Boolean(aux2 || isLiberadoLike(aux2StatusText)),
  };
}

export async function aceitarTermos(): Promise<any> {
  return post<any>(ENDPOINTS.appTermosAceite, {});
}

export async function solicitarContato(mensagem?: string): Promise<any> {
  return post<any>(ENDPOINTS.appContato, { mensagem: mensagem ?? '' });
}
