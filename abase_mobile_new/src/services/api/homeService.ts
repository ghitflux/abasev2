import { get } from './client';
import { ENDPOINTS } from './constants';

export type DocIssue = {
  id: number;
  title?: string | null;
  message?: string | null;
  status: string;
  required_docs?: string[] | null;
  opened_at?: string | null;
  closed_at?: string | null;
};

export const OPEN_ISSUE_STATUSES = new Set(['open', 'waiting_user', 'received', 'rejected']);

function pad2(n: number) { return n < 10 ? `0${n}` : `${n}`; }

const MONTHS_PT = [
  'janeiro','fevereiro','março','abril','maio','junho',
  'julho','agosto','setembro','outubro','novembro','dezembro',
];

export type ProximaRef = {
  mesLabel: string;
  dataLabel: string;
  iso?: string;
} | null;

export function computeNextRef(
  dataAprovacao?: string | null,
  parcelasPagas?: number,
  diaFixo = 15,
): ProximaRef {
  if (!dataAprovacao) return null;
  try {
    const base = new Date(dataAprovacao);
    if (Number.isNaN(base.getTime())) return null;
    const m = parcelasPagas ?? 0;
    const next = new Date(base.getFullYear(), base.getMonth() + m, diaFixo);
    const mesName = MONTHS_PT[next.getMonth()];
    const mesLabel = `${mesName.charAt(0).toUpperCase()}${mesName.slice(1)} ${next.getFullYear()}`;
    const dataLabel = `${pad2(diaFixo)}/${pad2(next.getMonth() + 1)}/${next.getFullYear()}`;
    return {
      mesLabel,
      dataLabel,
      iso: `${next.getFullYear()}-${pad2(next.getMonth() + 1)}-${pad2(diaFixo)}`,
    };
  } catch {
    return null;
  }
}

export async function getHomeIssues(): Promise<{ hasOpenIssues: boolean; openIssues: DocIssue[] }> {
  try {
    const json = await get<any>(ENDPOINTS.appPendencias);
    const all: DocIssue[] = Array.isArray(json?.issues) ? json.issues : [];
    const openIssues = all.filter((it) =>
      OPEN_ISSUE_STATUSES.has(String(it?.status || '').toLowerCase()),
    );
    return { hasOpenIssues: openIssues.length > 0, openIssues };
  } catch {
    return { hasOpenIssues: false, openIssues: [] };
  }
}
