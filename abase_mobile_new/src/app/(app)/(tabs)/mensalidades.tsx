import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, ActivityIndicator,
  RefreshControl, TouchableOpacity,
} from 'react-native';
import { Calendar, Receipt } from 'lucide-react-native';
import ProgressBar from '@/components/ProgressBar';
import { moneyBR } from '@/utils/format';
import { useAuth } from '@/context/AuthContext';
import {
  getMensalidades, getMeuPerfil, MensalidadesResponse, MensalidadeItem, isMensalidadePaga,
} from '@/services/api/mensalidadesService';

const onlyDigits = (s?: string | null) => (s ?? '').replace(/\D+/g, '');

const MESES_PT = [
  'janeiro','fevereiro','março','abril','maio','junho',
  'julho','agosto','setembro','outubro','novembro','dezembro',
];

function monthTitleFromRef(ref?: string, fallback?: string) {
  if (ref && /^\d{4}-\d{2}$/.test(ref)) {
    const [y, m] = ref.split('-').map((n) => parseInt(n, 10));
    const nome = MESES_PT[(m - 1) as number] || ref;
    return `${nome.charAt(0).toUpperCase()}${nome.slice(1)} ${y}`;
  }
  return fallback || '-';
}

function rangeTitle(fromYm?: string | null, toYm?: string | null) {
  if (!fromYm || !toYm) return null;
  return `${monthTitleFromRef(fromYm)} até ${monthTitleFromRef(toYm)}`;
}

function parseYm(ym: string): { y: number; m: number } | null {
  if (!/^\d{4}-\d{2}$/.test(ym)) return null;
  const [Y, M] = ym.split('-').map((n) => parseInt(n, 10));
  if (!Y || !M) return null;
  return { y: Y, m: M };
}

function addMonthsYm(ym: string, add: number): string {
  const p = parseYm(ym);
  if (!p) return ym;
  let y = p.y, m = p.m + add;
  while (m > 12) { m -= 12; y += 1; }
  while (m < 1) { m += 12; y -= 1; }
  return `${String(y).padStart(4, '0')}-${String(m).padStart(2, '0')}`;
}

function dmyFromYm(ym: string, dia: number): string {
  const p = parseYm(ym);
  if (!p) return '-';
  const d = Math.max(1, Math.min(31, dia));
  return `${String(d).padStart(2,'0')}/${String(p.m).padStart(2,'0')}/${String(p.y)}`;
}

function clampPct(v: number) {
  if (!Number.isFinite(v)) return 0;
  return Math.max(0, Math.min(100, Math.round(v)));
}

function YellowProgressBar({ value }: { value: number }) {
  const v = clampPct(value);
  return (
    <View style={s.yTrack}>
      <View style={[s.yFill, { width: `${v}%` }]} />
    </View>
  );
}

type CycleBlock = {
  id: string; kind: 'done' | 'future'; title: string; subtitle?: string;
  prazo: number; pagas: number; pct: number; totalCiclo: number;
  items: MensalidadeItem[]; ref_from?: string; ref_to?: string;
};

export default function MensalidadesScreen() {
  const { user } = useAuth();

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cpf, setCpf] = useState('');
  const [resp, setResp] = useState<MensalidadesResponse | null>(null);
  const [selectedCycleId, setSelectedCycleId] = useState<string>('done');

  const load = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      const fromCtx =
        onlyDigits((user as any)?.cpf_cnpj) || onlyDigits((user as any)?.documento) ||
        onlyDigits((user as any)?.cpf) || onlyDigits((user as any)?.pessoa?.documento);
      let doc = fromCtx || '';

      if (!doc) {
        const me = await getMeuPerfil();
        doc = onlyDigits(me?.agente?.cpf_cnpj) || onlyDigits(me?.pessoa?.documento) || onlyDigits(me?.cpf_cnpj) || '';
      }

      setCpf(doc);
      if (!doc) throw new Error('Não foi possível determinar seu CPF. Faça login novamente.');

      const data = await getMensalidades({ cpf: doc });
      setResp(data);
      setSelectedCycleId((cur) => cur || 'done');
    } catch (e: any) {
      setResp(null);
      setError(e?.message || 'Falha ao carregar mensalidades.');
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => { load(); }, [load]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    try { await load(); } finally { setRefreshing(false); }
  }, [load]);

  const itemsDone: MensalidadeItem[] = resp?.items ?? [];

  const donePrazo = useMemo(() => {
    const p = resp?.resumo?.prazo;
    if (typeof p === 'number' && p > 0) return p;
    return itemsDone.length || 0;
  }, [resp, itemsDone]);

  const donePagas = useMemo(() => {
    const p = resp?.resumo?.parcelas_pagas;
    if (typeof p === 'number' && p >= 0) return p;
    return itemsDone.filter(isMensalidadePaga).length;
  }, [resp, itemsDone]);

  const donePct = useMemo(() => {
    const p = resp?.resumo?.percentual_pago ?? resp?.resumo?.pct;
    if (typeof p === 'number' && p >= 0) return clampPct(p);
    return donePrazo > 0 ? clampPct((donePagas * 100) / donePrazo) : 0;
  }, [resp, donePrazo, donePagas]);

  const doneTotalCiclo = useMemo(() => {
    const v = resp?.resumo?.total_ciclo;
    if (typeof v === 'number') return v;
    return itemsDone.reduce((sum, it) => sum + (Number(it.valor) || 0), 0);
  }, [resp, itemsDone]);

  const hasRefi = !!resp?.refinanciamento?.exists;

  const cicloRefiKey = useMemo(() => {
    const ck = resp?.refinanciamento?.cycle_key;
    if (ck && String(ck).trim() !== '') return String(ck);
    const r1 = resp?.refinanciamento?.ref1?.slice(0, 7);
    const r2 = resp?.refinanciamento?.ref2?.slice(0, 7);
    const r3 = resp?.refinanciamento?.ref3?.slice(0, 7);
    const parts = [r1, r2, r3].filter(Boolean);
    return parts.length ? parts.join('|') : null;
  }, [resp]);

  const mensalPrevista = useMemo(() => {
    const m = resp?.resumo?.mensalidade;
    if (typeof m === 'number' && m > 0) return m;
    const vals = itemsDone.map(i => Number(i.valor || 0)).filter(v => v > 0);
    if (vals.length) return vals.reduce((a, b) => a + b, 0) / vals.length;
    return 150;
  }, [resp, itemsDone]);

  const baseNext = useMemo(() => {
    if (resp?.proximo_ciclo?.ref_from && resp?.proximo_ciclo?.ref_to) {
      return {
        ref_from: resp.proximo_ciclo.ref_from, ref_to: resp.proximo_ciclo.ref_to,
        prazo: resp.proximo_ciclo.prazo ?? 3, pagas: resp.proximo_ciclo.parcelas_pagas ?? 0,
        pct: resp.proximo_ciclo.percentual_pago ?? 0,
      };
    }
    const r3 = resp?.refinanciamento?.ref3?.slice(0, 7);
    if (r3) {
      const from = addMonthsYm(r3, 1);
      const to = addMonthsYm(from, 2);
      return { ref_from: from, ref_to: to, prazo: 3, pagas: 0, pct: 0 };
    }
    return null;
  }, [resp]);

  const futureCycles: CycleBlock[] = useMemo(() => {
    if (!baseNext?.ref_from) return [];
    const cycles: CycleBlock[] = [];
    for (let i = 0; i < 3; i++) {
      const from = addMonthsYm(baseNext.ref_from, i * 3);
      const to = addMonthsYm(from, 2);
      const items: MensalidadeItem[] = [0, 1, 2].map((k) => {
        const ym = addMonthsYm(from, k);
        return { valor: mensalPrevista, referencia: ym, previsao: dmyFromYm(ym, 15), status: 'A DESCONTAR', status_code: undefined };
      });
      const pagas = i === 0 ? (baseNext.pagas ?? 0) : 0;
      const pct = i === 0 ? clampPct(baseNext.pct ?? 0) : 0;
      cycles.push({
        id: `future-${i + 1}`, kind: 'future', title: `Ciclo ${i + 1}`,
        subtitle: rangeTitle(from, to) || '-', prazo: 3, pagas, pct,
        totalCiclo: mensalPrevista * 3, items, ref_from: from, ref_to: to,
      });
    }
    return cycles;
  }, [baseNext, mensalPrevista]);

  const cycles: CycleBlock[] = useMemo(() => {
    const done: CycleBlock = {
      id: 'done', kind: 'done', title: 'Ciclo concluído',
      subtitle: cicloRefiKey ? cicloRefiKey.replace(/\|/g, ' | ') : undefined,
      prazo: donePrazo, pagas: donePagas, pct: donePct, totalCiclo: doneTotalCiclo,
      items: itemsDone, ref_from: resp?.resumo?.ref_from, ref_to: resp?.resumo?.ref_to,
    };
    return [done, ...futureCycles];
  }, [cicloRefiKey, donePrazo, donePagas, donePct, doneTotalCiclo, itemsDone, futureCycles, resp]);

  const selectedCycle = useMemo(
    () => cycles.find(c => c.id === selectedCycleId) || cycles[0],
    [cycles, selectedCycleId],
  );

  const focusFuture = useMemo(() => {
    const chosen = cycles.find(c => c.id === selectedCycleId && c.kind === 'future');
    if (chosen) return chosen;
    return cycles.find(c => c.kind === 'future') || null;
  }, [cycles, selectedCycleId]);

  if (loading) {
    return (
      <View style={s.center}>
        <ActivityIndicator />
        <Text style={s.mutedSmall}>Carregando mensalidades...</Text>
      </View>
    );
  }

  return (
    <ScrollView
      style={s.container}
      contentContainerStyle={{ padding: 16, gap: 14 }}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
    >
      <Text style={s.title}>Mensalidades</Text>

      {error ? (
        <View style={s.card}>
          <Text style={[s.muted, { marginBottom: 6 }]}>Não foi possível carregar as mensalidades.</Text>
          <Text style={[s.muted, { fontSize: 12 }]}>{error}</Text>
        </View>
      ) : null}

      {/* Progresso do ciclo concluído */}
      <View style={s.card}>
        <View style={s.rowBetween}>
          <Text style={s.cardTitle}>Progresso do Ciclo</Text>
          <Text style={s.bold}>{donePct}%</Text>
        </View>
        <View style={{ marginTop: 4 }}>
          <Text style={s.muted}>{donePagas}/{donePrazo} concluídas</Text>
        </View>
        <View style={{ marginTop: 10 }}>
          <ProgressBar progress={donePct} />
        </View>
        <Text style={[s.muted, { marginTop: 10 }]}>
          Total do ciclo: <Text style={s.bold}>{moneyBR(doneTotalCiclo)}</Text>
        </Text>
      </View>

      {/* Novo ciclo (refinanciamento) */}
      {hasRefi ? (
        <View style={s.card}>
          <View style={s.rowBetween}>
            <Text style={s.cardTitle}>Novo ciclo</Text>
            <View style={s.pillInfo}>
              <Text style={s.pillTextInfo}>REFINANCIADO</Text>
            </View>
          </View>
          {cicloRefiKey ? (
            <Text style={[s.muted, { marginTop: 8 }]}>
              Ciclo refinanciado: <Text style={s.bold}>{cicloRefiKey}</Text>
            </Text>
          ) : null}
          {focusFuture ? (
            <>
              <Text style={[s.muted, { marginTop: 8 }]}>
                Próximo ciclo: <Text style={s.bold}>{focusFuture.subtitle || '-'}</Text>
              </Text>
              <Text style={[s.muted, { marginTop: 8 }]}>
                Progresso do novo ciclo:{' '}
                <Text style={s.bold}>{focusFuture.pagas}/{focusFuture.prazo}</Text> concluídas ({clampPct(focusFuture.pct)}%)
              </Text>
              <View style={{ marginTop: 10 }}>
                <YellowProgressBar value={focusFuture.pct} />
              </View>
              <Text style={[s.muted, { marginTop: 8, fontSize: 12 }]}>
                Ciclos futuros aparecem como "A DESCONTAR" até você importar o próximo arquivo retorno.
              </Text>
            </>
          ) : (
            <Text style={[s.muted, { marginTop: 8 }]}>
              Refinanciamento detectado, mas não foi possível calcular o próximo ciclo.
            </Text>
          )}
        </View>
      ) : null}

      {/* Seletor de ciclos */}
      <Text style={[s.muted, { marginTop: 6 }]}>Ciclos</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false}>
        <View style={{ flexDirection: 'row', gap: 10 }}>
          {cycles.map((c) => {
            const active = c.id === selectedCycleId;
            return (
              <TouchableOpacity
                key={c.id}
                onPress={() => setSelectedCycleId(c.id)}
                style={[s.cycleChip, active ? s.cycleChipActive : null]}
              >
                <Text style={[s.cycleChipTitle, active ? s.cycleChipTitleActive : null]}>{c.title}</Text>
                <Text style={[s.cycleChipSub, active ? s.cycleChipSubActive : null]}>
                  {c.kind === 'done' ? (c.subtitle ? c.subtitle : 'Ciclo fechado') : (c.subtitle || '-')}
                </Text>
                <Text style={[s.cycleChipMeta, active ? s.cycleChipMetaActive : null]}>
                  {c.pagas}/{c.prazo} ({c.pct}%)
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>
      </ScrollView>

      {/* Lista das mensalidades */}
      <Text style={[s.muted, { marginTop: 10 }]}>
        Mensalidades do ciclo: <Text style={s.bold}>{selectedCycle.title}</Text>
      </Text>

      {selectedCycle.items.map((m, idx) => {
        const ok = isMensalidadePaga(m);
        const calendarText = ok
          ? (m.pago_em ? `Descontado em ${m.pago_em}` : 'Descontado')
          : `Previsão: ${m.previsao || '-'}`;

        return (
          <View key={`${selectedCycle.id}-${idx}`} style={s.item}>
            <View style={s.rowBetween}>
              <Text style={s.itemTitle}>{monthTitleFromRef(m.referencia, m.titulo)}</Text>
              <View style={ok ? s.pillOk : s.pillWarning}>
                <Text style={ok ? s.pillTextOk : s.pillText}>
                  {ok ? 'DESCONTADA' : 'A DESCONTAR'}
                </Text>
              </View>
            </View>
            <Text style={s.valor}>{moneyBR(Number(m.valor || 0))}</Text>
            <View style={{ marginTop: 8, gap: 6 }}>
              <View style={s.iconLine}>
                <Calendar size={18} color={ok ? '#22c55e' : '#94a3b8'} style={{ marginRight: 8 }} />
                <Text style={ok ? s.lineOk : s.line}>{calendarText}</Text>
              </View>
              <View style={s.iconLine}>
                <Receipt size={18} color="#94a3b8" style={{ marginRight: 8 }} />
                <Text style={s.line}>Desconto em folha</Text>
              </View>
            </View>
          </View>
        );
      })}

      {selectedCycle.items.length === 0 && !error ? (
        <View style={s.card}>
          <Text style={s.muted}>Nenhuma mensalidade encontrada para o CPF {cpf || '-'}.</Text>
        </View>
      ) : null}
    </ScrollView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0b0f14' },
  center: { flex: 1, backgroundColor: '#0b0f14', alignItems: 'center', justifyContent: 'center' },
  title: { color: '#e5e7eb', fontSize: 26, fontWeight: '800', marginBottom: 8 },
  card: { backgroundColor: '#111827', padding: 16, borderRadius: 16 },
  cardTitle: { color: '#e5e7eb', fontWeight: '800', fontSize: 16 },
  rowBetween: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  muted: { color: '#94a3b8' },
  mutedSmall: { color: '#94a3b8', marginTop: 8, fontSize: 12 },
  bold: { color: '#e5e7eb', fontWeight: '800' },
  item: { backgroundColor: '#111827', padding: 16, borderRadius: 16 },
  itemTitle: { color: '#e5e7eb', fontWeight: '800', fontSize: 18 },
  valor: { color: '#fff', fontSize: 26, fontWeight: '900', marginTop: 6 },
  pillWarning: { backgroundColor: '#f59e0b22', borderWidth: 1, borderColor: '#f59e0b55', paddingHorizontal: 12, paddingVertical: 6, borderRadius: 999 },
  pillText: { color: '#f59e0b', fontWeight: '800', fontSize: 12 },
  pillOk: { backgroundColor: '#22c55e22', borderWidth: 1, borderColor: '#22c55e55', paddingHorizontal: 12, paddingVertical: 6, borderRadius: 999 },
  pillTextOk: { color: '#22c55e', fontWeight: '800', fontSize: 12 },
  pillInfo: { backgroundColor: '#22d3ee22', borderWidth: 1, borderColor: '#22d3ee55', paddingHorizontal: 12, paddingVertical: 6, borderRadius: 999 },
  pillTextInfo: { color: '#22d3ee', fontWeight: '800', fontSize: 12 },
  line: { color: '#94a3b8' },
  lineOk: { color: '#22c55e', fontWeight: '700' },
  iconLine: { flexDirection: 'row', alignItems: 'center' },
  cycleChip: { width: 210, backgroundColor: '#0f172a', borderRadius: 16, padding: 12, borderWidth: 1, borderColor: 'rgba(148,163,184,.18)' },
  cycleChipActive: { borderColor: '#22d3ee66', backgroundColor: 'rgba(34,211,238,.08)' },
  cycleChipTitle: { color: '#e5e7eb', fontWeight: '900', fontSize: 14 },
  cycleChipTitleActive: { color: '#e5e7eb' },
  cycleChipSub: { color: '#94a3b8', marginTop: 6, fontSize: 12 },
  cycleChipSubActive: { color: '#cbd5e1' },
  cycleChipMeta: { color: '#94a3b8', marginTop: 6, fontSize: 12, fontWeight: '700' },
  cycleChipMetaActive: { color: '#e5e7eb' },
  yTrack: { height: 10, borderRadius: 999, backgroundColor: 'rgba(245, 158, 11, .18)', overflow: 'hidden' },
  yFill: { height: 10, borderRadius: 999, backgroundColor: '#f59e0b' },
});
