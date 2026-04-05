import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { AlertTriangle, Calendar, Receipt } from 'lucide-react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import ProgressBar from '@/components/ProgressBar';
import { moneyBR } from '@/utils/format';
import { useAuth } from '@/context/AuthContext';
import {
  getMensalidades,
  getMeuPerfil,
  isMensalidadePaga,
  MensalidadeCycle,
  MensalidadeItem,
  MensalidadesResponse,
} from '@/services/api/mensalidadesService';

const onlyDigits = (s?: string | null) => (s ?? '').replace(/\D+/g, '');

const MESES_PT = [
  'janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho',
  'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro',
];

function monthTitleFromRef(ref?: string, fallback?: string) {
  if (ref && /^\d{4}-\d{2}$/.test(ref)) {
    const [y, m] = ref.split('-').map((n) => parseInt(n, 10));
    const nome = MESES_PT[(m - 1) as number] || ref;
    return `${nome.charAt(0).toUpperCase()}${nome.slice(1)} ${y}`;
  }
  return fallback || '-';
}

function clampPct(v: number) {
  if (!Number.isFinite(v)) return 0;
  return Math.max(0, Math.min(100, Math.round(v)));
}

function normalizeStatus(value?: string | null) {
  return String(value ?? '').trim().toLowerCase();
}

function isInadimplente(item: MensalidadeItem) {
  const raw = normalizeStatus(item.status ?? item.status_code);
  if (!raw) return false;
  if (isMensalidadePaga(item)) return false;
  return !/(quitad|liquidad|regulariz)/i.test(raw);
}

function statusLabel(item: MensalidadeItem) {
  const raw = normalizeStatus(item.status ?? item.status_code);
  if (isMensalidadePaga(item)) return 'Descontada';
  if (raw.includes('nao_descontado')) return 'Não descontada';
  if (raw.includes('em_aberto')) return 'Em aberto';
  if (raw.includes('em_previsao')) return 'Em previsão';
  if (raw.includes('inadimpl')) return 'Inadimplente';
  if (raw.includes('quitad')) return 'Quitada';
  return item.status || 'Pendente';
}

function buildCycleTitle(cycle: MensalidadeCycle) {
  return cycle.numero ? `Ciclo ${cycle.numero}` : 'Ciclo';
}

function buildCycleSubtitle(cycle: MensalidadeCycle) {
  const parts = [cycle.contrato_codigo, cycle.resumo_referencias].filter(Boolean);
  return parts.join(' • ') || 'Sem referências';
}

function cycleStats(cycle?: MensalidadeCycle | null) {
  const items = cycle?.items ?? [];
  const pagas = items.filter(isMensalidadePaga).length;
  const prazo = items.length;
  const pct = prazo > 0 ? clampPct((pagas * 100) / prazo) : 0;
  const totalCiclo = cycle?.valor_total && cycle.valor_total > 0
    ? cycle.valor_total
    : items.reduce((sum, item) => sum + (Number(item.valor) || 0), 0);
  return { pagas, prazo, pct, totalCiclo };
}

function paymentLine(item: MensalidadeItem) {
  if (isMensalidadePaga(item)) {
    return item.pago_em ? `Descontado em ${item.pago_em}` : 'Descontado';
  }
  if (item.previsao) return `Previsão: ${item.previsao}`;
  return 'Aguardando baixa';
}

export default function MensalidadesScreen() {
  const { user } = useAuth();
  const insets = useSafeAreaInsets();

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cpf, setCpf] = useState('');
  const [resp, setResp] = useState<MensalidadesResponse | null>(null);
  const [selectedCycleId, setSelectedCycleId] = useState<string>('');

  const load = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      const fromCtx =
        onlyDigits((user as any)?.cpf_cnpj) || onlyDigits((user as any)?.documento)
        || onlyDigits((user as any)?.cpf) || onlyDigits((user as any)?.pessoa?.documento);
      let doc = fromCtx || '';

      if (!doc) {
        const me = await getMeuPerfil();
        doc = onlyDigits(me?.agente?.cpf_cnpj)
          || onlyDigits(me?.pessoa?.documento)
          || onlyDigits(me?.cpf_cnpj)
          || '';
      }

      setCpf(doc);
      if (!doc) throw new Error('Não foi possível determinar seu CPF. Faça login novamente.');

      const data = await getMensalidades({ cpf: doc });
      setResp(data);
    } catch (e: any) {
      setResp(null);
      setError(e?.message || 'Falha ao carregar mensalidades.');
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    load();
  }, [load]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await load();
    } finally {
      setRefreshing(false);
    }
  }, [load]);

  const cycles = useMemo(() => resp?.cycles ?? [], [resp]);

  useEffect(() => {
    if (!cycles.length) {
      if (selectedCycleId) setSelectedCycleId('');
      return;
    }
    if (!cycles.some((cycle) => cycle.id === selectedCycleId)) {
      setSelectedCycleId(cycles[0].id);
    }
  }, [cycles, selectedCycleId]);

  const selectedCycle = useMemo(
    () => cycles.find((cycle) => cycle.id === selectedCycleId) || cycles[0] || null,
    [cycles, selectedCycleId],
  );
  const selectedStats = useMemo(() => cycleStats(selectedCycle), [selectedCycle]);
  const inadimplentes = useMemo(
    () => (resp?.meses_nao_pagos ?? []).filter(isInadimplente),
    [resp],
  );

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
      contentContainerStyle={{
        paddingHorizontal: 16,
        paddingTop: 16 + Math.max(insets.top - 12, 0) * 0.15,
        paddingBottom: 24 + insets.bottom,
        gap: 14,
      }}
      scrollIndicatorInsets={{ top: insets.top, bottom: insets.bottom }}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
    >
      <Text style={s.title}>Mensalidades</Text>

      {error ? (
        <View style={s.card}>
          <Text style={[s.muted, { marginBottom: 6 }]}>Não foi possível carregar as mensalidades.</Text>
          <Text style={[s.muted, { fontSize: 12 }]}>{error}</Text>
        </View>
      ) : null}

      {inadimplentes.length > 0 ? (
        <View style={s.cardAlert}>
          <View style={s.rowBetween}>
            <Text style={s.cardTitle}>Mensalidades inadimplentes</Text>
            <View style={s.pillDanger}>
              <Text style={s.pillTextDanger}>{inadimplentes.length}</Text>
            </View>
          </View>
          <Text style={[s.muted, { marginTop: 8 }]}>
            Competências em atraso ou não descontadas no histórico do associado.
          </Text>

          <View style={{ marginTop: 12, gap: 10 }}>
            {inadimplentes.map((item, index) => (
              <View key={`inad-${item.id ?? item.referencia ?? index}`} style={s.alertItem}>
                <View style={s.rowBetween}>
                  <Text style={s.itemTitle}>{monthTitleFromRef(item.referencia, item.titulo)}</Text>
                  <Text style={s.alertValue}>{moneyBR(Number(item.valor || 0))}</Text>
                </View>
                <View style={{ marginTop: 8, gap: 6 }}>
                  <View style={s.iconLine}>
                    <AlertTriangle size={18} color="#fca5a5" style={{ marginRight: 8 }} />
                    <Text style={s.lineDanger}>{statusLabel(item)}</Text>
                  </View>
                  {item.observacao ? (
                    <Text style={s.muted}>{item.observacao}</Text>
                  ) : null}
                  {item.contrato_codigo ? (
                    <Text style={s.muted}>Contrato: {item.contrato_codigo}</Text>
                  ) : null}
                </View>
              </View>
            ))}
          </View>
        </View>
      ) : null}

      {selectedCycle ? (
        <View style={s.card}>
          <View style={s.rowBetween}>
            <Text style={s.cardTitle}>Progresso do ciclo</Text>
            <Text style={s.bold}>{selectedStats.pct}%</Text>
          </View>
          <Text style={[s.muted, { marginTop: 8 }]}>
            {buildCycleTitle(selectedCycle)} • <Text style={s.bold}>{buildCycleSubtitle(selectedCycle)}</Text>
          </Text>
          <Text style={[s.muted, { marginTop: 6 }]}>
            {selectedStats.pagas}/{selectedStats.prazo} mensalidades descontadas
          </Text>
          <View style={{ marginTop: 10 }}>
            <ProgressBar progress={selectedStats.pct} />
          </View>
          <Text style={[s.muted, { marginTop: 10 }]}>
            Total do ciclo: <Text style={s.bold}>{moneyBR(selectedStats.totalCiclo)}</Text>
          </Text>
        </View>
      ) : null}

      {cycles.length > 0 ? (
        <>
          <Text style={[s.muted, { marginTop: 4 }]}>Ciclos</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false}>
            <View style={{ flexDirection: 'row', gap: 10 }}>
              {cycles.map((cycle) => {
                const active = cycle.id === selectedCycle?.id;
                const stats = cycleStats(cycle);
                return (
                  <TouchableOpacity
                    key={cycle.id}
                    onPress={() => setSelectedCycleId(cycle.id)}
                    style={[s.cycleChip, active ? s.cycleChipActive : null]}
                  >
                    <Text style={[s.cycleChipTitle, active ? s.cycleChipTitleActive : null]}>
                      {buildCycleTitle(cycle)}
                    </Text>
                    <Text style={[s.cycleChipSub, active ? s.cycleChipSubActive : null]}>
                      {buildCycleSubtitle(cycle)}
                    </Text>
                    <Text style={[s.cycleChipMeta, active ? s.cycleChipMetaActive : null]}>
                      {stats.pagas}/{stats.prazo} ({stats.pct}%)
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>
          </ScrollView>

          <Text style={[s.muted, { marginTop: 10 }]}>
            Mensalidades do ciclo: <Text style={s.bold}>{selectedCycle ? buildCycleTitle(selectedCycle) : '-'}</Text>
          </Text>

          {(selectedCycle?.items ?? []).map((item, index) => {
            const ok = isMensalidadePaga(item);
            return (
              <View key={`${selectedCycle?.id ?? 'cycle'}-${item.id ?? item.referencia ?? index}`} style={s.item}>
                <View style={s.rowBetween}>
                  <Text style={s.itemTitle}>{monthTitleFromRef(item.referencia, item.titulo)}</Text>
                  <View style={ok ? s.pillOk : s.pillWarning}>
                    <Text style={ok ? s.pillTextOk : s.pillText}>
                      {ok ? 'DESCONTADA' : 'A DESCONTAR'}
                    </Text>
                  </View>
                </View>
                <Text style={s.valor}>{moneyBR(Number(item.valor || 0))}</Text>
                <View style={{ marginTop: 8, gap: 6 }}>
                  <View style={s.iconLine}>
                    <Calendar size={18} color={ok ? '#22c55e' : '#94a3b8'} style={{ marginRight: 8 }} />
                    <Text style={ok ? s.lineOk : s.line}>{paymentLine(item)}</Text>
                  </View>
                  <View style={s.iconLine}>
                    <Receipt size={18} color="#94a3b8" style={{ marginRight: 8 }} />
                    <Text style={s.line}>Desconto em folha</Text>
                  </View>
                  {item.observacao ? (
                    <Text style={s.muted}>{item.observacao}</Text>
                  ) : null}
                </View>
              </View>
            );
          })}
        </>
      ) : !error ? (
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
  cardAlert: {
    backgroundColor: 'rgba(127, 29, 29, 0.36)',
    borderWidth: 1,
    borderColor: 'rgba(248, 113, 113, 0.35)',
    padding: 16,
    borderRadius: 16,
  },
  alertItem: {
    backgroundColor: 'rgba(15, 23, 42, 0.55)',
    borderRadius: 14,
    padding: 14,
    borderWidth: 1,
    borderColor: 'rgba(248, 113, 113, 0.16)',
  },
  cardTitle: { color: '#e5e7eb', fontWeight: '800', fontSize: 16 },
  rowBetween: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  muted: { color: '#94a3b8' },
  mutedSmall: { color: '#94a3b8', marginTop: 8, fontSize: 12 },
  bold: { color: '#e5e7eb', fontWeight: '800' },
  item: { backgroundColor: '#111827', padding: 16, borderRadius: 16 },
  itemTitle: { color: '#e5e7eb', fontWeight: '800', fontSize: 18, flex: 1, paddingRight: 8 },
  valor: { color: '#fff', fontSize: 26, fontWeight: '900', marginTop: 6 },
  alertValue: { color: '#fecaca', fontWeight: '800', fontSize: 16 },
  pillWarning: {
    backgroundColor: '#f59e0b22',
    borderWidth: 1,
    borderColor: '#f59e0b55',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 999,
  },
  pillText: { color: '#f59e0b', fontWeight: '800', fontSize: 12 },
  pillOk: {
    backgroundColor: '#22c55e22',
    borderWidth: 1,
    borderColor: '#22c55e55',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 999,
  },
  pillTextOk: { color: '#22c55e', fontWeight: '800', fontSize: 12 },
  pillDanger: {
    backgroundColor: 'rgba(248, 113, 113, 0.18)',
    borderWidth: 1,
    borderColor: 'rgba(248, 113, 113, 0.35)',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
  },
  pillTextDanger: { color: '#fecaca', fontWeight: '800', fontSize: 12 },
  line: { color: '#94a3b8' },
  lineOk: { color: '#22c55e', fontWeight: '700' },
  lineDanger: { color: '#fecaca', fontWeight: '700' },
  iconLine: { flexDirection: 'row', alignItems: 'center' },
  cycleChip: {
    width: 232,
    backgroundColor: '#0f172a',
    borderRadius: 16,
    padding: 12,
    borderWidth: 1,
    borderColor: 'rgba(148,163,184,.18)',
  },
  cycleChipActive: { borderColor: '#22d3ee66', backgroundColor: 'rgba(34,211,238,.08)' },
  cycleChipTitle: { color: '#e5e7eb', fontWeight: '900', fontSize: 14 },
  cycleChipTitleActive: { color: '#e5e7eb' },
  cycleChipSub: { color: '#94a3b8', marginTop: 6, fontSize: 12 },
  cycleChipSubActive: { color: '#cbd5e1' },
  cycleChipMeta: { color: '#94a3b8', marginTop: 6, fontSize: 12, fontWeight: '700' },
  cycleChipMetaActive: { color: '#e5e7eb' },
});
