import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, ScrollView, ActivityIndicator, RefreshControl,
} from 'react-native';
import { TrendingUp, CheckCircle, Info, ChevronUp, ChevronDown, Clock } from 'lucide-react-native';
import ProgressBar from '@/components/ProgressBar';
import { moneyBR } from '@/utils/format';
import { useAuth } from '@/context/AuthContext';
import { fetchHome } from '@/services/api/authService';
import type { Bootstrap } from '@/types';
import { getMeuPerfil } from '@/services/api/mensalidadesService';
import { getHistoricoAntecipacoes, HistoricoItem } from '@/services/api/antecipacaoService';

const onlyDigits = (s?: string | null) => (s ?? '').replace(/\D+/g, '');

export default function AntecipacaoScreen() {
  const { token, user } = useAuth();

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [home, setHome] = useState<Bootstrap | null>(null);
  const [cpf, setCpf] = useState('');
  const [histOpen, setHistOpen] = useState(false);
  const [historico, setHistorico] = useState<HistoricoItem[]>([]);

  const resolveCpf = useCallback(async (): Promise<string> => {
    const fromCtx =
      onlyDigits((user as any)?.cpf_cnpj) || onlyDigits((user as any)?.documento) ||
      onlyDigits((user as any)?.cpf) || onlyDigits((user as any)?.pessoa?.documento);
    if (fromCtx) return fromCtx;

    const h = await fetchHome().catch(() => null);
    const fromHome = onlyDigits((h as any)?.pessoa?.documento) || onlyDigits((h as any)?.documento) || '';
    if (fromHome) return fromHome;

    const me = await getMeuPerfil();
    return onlyDigits(me?.agente?.cpf_cnpj) || onlyDigits(me?.pessoa?.documento) || onlyDigits(me?.cpf_cnpj) || '';
  }, [token, user]);

  const load = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      if (!token) throw new Error('Não autenticado.');
      const h = await fetchHome();
      setHome(h);

      const doc = await resolveCpf();
      setCpf(doc);
      if (!doc) throw new Error('Não foi possível determinar seu CPF.');

      const hist = await getHistoricoAntecipacoes({ cpf: doc });
      setHistorico(hist.items || []);
      setHistOpen((open) => (hist.items && hist.items.length > 0 ? true : open));
    } catch (e: any) {
      setError(e?.message || 'Falha ao carregar dados.');
      setHistorico([]);
    } finally {
      setLoading(false);
    }
  }, [token, resolveCpf]);

  useEffect(() => { load(); }, [load]);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    try { await load(); } finally { setRefreshing(false); }
  }, [load]);

  const prazo = home?.resumo?.prazo ?? 0;
  const pagas = home?.resumo?.parcelas_pagas ?? 0;
  const pct = useMemo(() => {
    const p = home?.resumo?.percentual_pago ?? 0;
    if (p > 0) return Math.round(p);
    return prazo > 0 ? Math.round((pagas * 100) / prazo) : 0;
  }, [home, prazo, pagas]);

  const elegivel = !!(home?.resumo?.elegivel_antecipacao);
  const precisa = Math.max(1 - (pagas || 0), 0);

  if (loading) {
    return <View style={s.center}><ActivityIndicator /></View>;
  }

  return (
    <ScrollView
      style={s.container}
      contentContainerStyle={{ padding: 16, gap: 14 }}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}
    >
      <Text style={s.title}>Antecipação</Text>

      <View style={s.card}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
          <TrendingUp size={18} color="#f472b6" />
          <Text style={s.cardTitle}>Antecipação</Text>
        </View>
        <Text style={s.muted}>Solicite a antecipação da sua contribuição</Text>
      </View>

      <View style={s.card}>
        <Text style={s.cardTitle}>Status do Ciclo</Text>
        <Text style={[s.muted, { marginTop: 6 }]}>Progresso</Text>
        <View style={s.rowBetween}>
          <Text style={s.muted}>{pagas}/{prazo} descontadas</Text>
          <Text style={s.muted}>{pct}%</Text>
        </View>
        <View style={{ marginTop: 8 }}>
          <ProgressBar progress={pct} />
        </View>
        <View style={s.tipBox}>
          {elegivel
            ? <CheckCircle size={18} color="#22c55e" style={{ marginRight: 8 }} />
            : <Info size={18} color="#94a3b8" style={{ marginRight: 8 }} />
          }
          <Text style={[s.tipText, elegivel ? s.tipTextOk : null]}>
            {elegivel
              ? 'Você está elegível para solicitar antecipação.'
              : `Complete ${precisa || 1} ciclo para solicitar antecipação.`}
          </Text>
        </View>
      </View>

      <View style={s.card}>
        <TouchableOpacity style={s.rowBetween} onPress={() => setHistOpen(v => !v)}>
          <Text style={s.cardTitle}>Histórico de Solicitações</Text>
          {histOpen ? <ChevronUp size={20} color="#94a3b8" /> : <ChevronDown size={20} color="#94a3b8" />}
        </TouchableOpacity>

        {histOpen && (
          <View style={{ marginTop: 12, gap: 10 }}>
            {historico.length === 0 ? (
              <Text style={s.muted}>Nenhum registro encontrado.</Text>
            ) : (
              historico.map((it, idx) => {
                const st = String(it.status || '').toLowerCase();
                const isAprov = st.includes('aprov') || st.includes('pago');
                return (
                  <View key={idx} style={[s.histItem, isAprov ? s.histItemOk : s.histItemWarn]}>
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, flex: 1 }}>
                      {isAprov
                        ? <CheckCircle size={20} color="#22c55e" />
                        : <Clock size={20} color="#f59e0b" />
                      }
                      <View style={{ flex: 1 }}>
                        <Text style={s.histMoney}>{moneyBR(it.valor || 0)}</Text>
                        <Text style={s.histSub}>{it.data || '—'}</Text>
                      </View>
                    </View>
                    <View style={[s.pill, isAprov ? s.pillOk : s.pillWarn]}>
                      <Text style={[s.pillTxt, isAprov ? s.pillTxtOk : s.pillTxtWarn]}>
                        {isAprov ? 'APROVADO' : (it.status_label || 'PENDENTE').toUpperCase()}
                      </Text>
                    </View>
                  </View>
                );
              })
            )}
          </View>
        )}
      </View>

      {error ? (
        <View style={s.card}>
          <Text style={[s.muted, { fontSize: 12 }]}>{error}</Text>
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
  muted: { color: '#94a3b8' },
  rowBetween: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 6 },
  tipBox: { marginTop: 12, padding: 12, borderRadius: 12, backgroundColor: '#0f172a', borderWidth: 1, borderColor: 'rgba(148,163,184,0.25)', flexDirection: 'row', alignItems: 'center' },
  tipText: { color: '#94a3b8', flex: 1 },
  tipTextOk: { color: '#22c55e', fontWeight: '700' },
  histItem: { borderRadius: 14, padding: 14, flexDirection: 'row', alignItems: 'center', gap: 10, justifyContent: 'space-between' },
  histItemOk: { backgroundColor: 'rgba(34,197,94,0.10)', borderWidth: 1, borderColor: 'rgba(34,197,94,0.35)' },
  histItemWarn: { backgroundColor: 'rgba(245,158,11,0.10)', borderWidth: 1, borderColor: 'rgba(245,158,11,0.35)' },
  histMoney: { color: '#e5e7eb', fontWeight: '900' },
  histSub: { color: '#94a3b8' },
  pill: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 999, borderWidth: 1 },
  pillOk: { backgroundColor: 'rgba(34,197,94,0.15)', borderColor: 'rgba(34,197,94,0.50)' },
  pillWarn: { backgroundColor: 'rgba(245,158,11,0.15)', borderColor: 'rgba(245,158,11,0.50)' },
  pillTxt: { fontWeight: '800', fontSize: 12 },
  pillTxtOk: { color: '#22c55e' },
  pillTxtWarn: { color: '#f59e0b' },
});
