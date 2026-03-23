import React, { useCallback, useMemo, useState } from 'react';
import {
  ActivityIndicator, Alert, Linking, ScrollView,
  StyleSheet, Text, TouchableOpacity, View,
} from 'react-native';
import { useRouter } from 'expo-router';
import { useFocusEffect } from '@react-navigation/native';
import * as SecureStore from 'expo-secure-store';
import { useAuth } from '@/context/AuthContext';
import { getEsperaResumo, OPEN_ISSUE_STATUSES, type EsperaResumo } from '@/services/api/esperaService';
import { aceitarTermos, solicitarContato } from '@/services/api/cadastroService';

const BG = '#0f172a';
const CARD = '#0b1220';
const INK = '#e5e7eb';
const MUTED = '#94a3b8';
const BORDER = 'rgba(148,163,184,0.25)';
const BRAND = '#22d3ee';
const OK = '#10b981';
const BAD = '#ef4444';

const CONTACT_FLAG_KEY_PREFIX = 'espera:contact:submitted';

function moneyBR(v?: number | null) {
  if (v == null || Number.isNaN(Number(v))) return '—';
  try {
    return new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(Number(v));
  } catch {
    const n = Number(v).toFixed(2).replace('.', ',');
    return `R$ ${n}`.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  }
}

function safe(v: any, fallback = '—') {
  return v == null || (typeof v === 'string' && v.trim() === '') ? fallback : String(v);
}

function pad2(n: number) { return n < 10 ? `0${n}` : String(n); }
function brDate(d: Date) { return `${pad2(d.getDate())}/${pad2(d.getMonth() + 1)}/${d.getFullYear()}`; }

function parseISODateLocal(iso?: string | null): Date | null {
  if (!iso) return null;
  const s = String(iso).trim();
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

function addMonthsClamped(d: Date, m: number) {
  const targetMonth = d.getMonth() + m;
  const lastDay = new Date(d.getFullYear(), targetMonth + 1, 0).getDate();
  return new Date(d.getFullYear(), targetMonth, Math.min(d.getDate(), lastDay));
}

export default function EsperaScreen() {
  const { token, user } = useAuth();
  const router = useRouter();

  const [loading, setLoading] = useState(true);
  const [resumo, setResumo] = useState<EsperaResumo | null>(null);
  const [contactRequested, setContactRequested] = useState(false);

  const contactKey = useMemo(
    () => `${CONTACT_FLAG_KEY_PREFIX}:${user?.id ?? 'anon'}`,
    [user?.id],
  );

  const load = useCallback(async () => {
    if (!token) return;
    try {
      setLoading(true);
      const r = await getEsperaResumo();
      setResumo(r);
      if (!r.complete) {
        router.replace('/(app)/cadastro-associado');
        return;
      }
      if (r.aprovado) {
        router.replace('/(app)/(tabs)');
        return;
      }
    } catch (e: any) {
      Alert.alert('Erro', e?.message || 'Não foi possível carregar o status.');
    } finally {
      setLoading(false);
    }
  }, [token, router]);

  useFocusEffect(
    useCallback(() => {
      let alive = true;
      load().catch(() => {});
      return () => { alive = false; };
    }, [load]),
  );

  useFocusEffect(
    useCallback(() => {
      let alive = true;
      (async () => {
        try {
          const old = await SecureStore.getItemAsync(CONTACT_FLAG_KEY_PREFIX);
          if (old === '1') await SecureStore.deleteItemAsync(CONTACT_FLAG_KEY_PREFIX).catch(() => {});
          const v = await SecureStore.getItemAsync(contactKey);
          if (alive) setContactRequested(v === '1');
        } catch {}
      })();
      return () => { alive = false; };
    }, [contactKey]),
  );

  function openUrl(u?: string | null) {
    if (!u) return;
    Linking.openURL(u).catch(() => Alert.alert('Aviso', 'Não foi possível abrir o arquivo.'));
  }

  const statusTxt = resumo?.status || 'Pendente';
  const statusLow = statusTxt.toLowerCase();
  const statusColor = statusLow === 'aprovado' ? OK : statusLow.includes('reprov') ? BAD : BRAND;

  const dados = resumo?.dados;
  const canAux1 = !!(resumo?.permissions?.auxilio1) || !!(resumo as any)?.auxilios?.auxilio1?.allowed;
  const canAux2 = !!(resumo?.permissions?.auxilio2) || !!(resumo as any)?.auxilios?.auxilio2?.allowed;
  const canAccept = !resumo?.aceiteTermos && !!(resumo?.termos?.adesaoUrl || resumo?.termos?.antecipacaoUrl);

  async function onAceitar() {
    try {
      await aceitarTermos();
      setResumo((prev) => prev ? ({ ...prev, aceiteTermos: true }) : prev);
      Alert.alert('Pronto', 'Seu aceite foi registrado.');
    } catch (e: any) {
      Alert.alert('Erro', e?.message || 'Falha ao registrar aceite.');
    }
  }

  async function onContato() {
    try {
      await solicitarContato();
      await SecureStore.setItemAsync(contactKey, '1').catch(() => {});
      setContactRequested(true);
      Alert.alert('Contato', 'Recebemos seu pedido. Nossa equipe falará com você.');
    } catch (e: any) {
      Alert.alert('Erro', e?.message || 'Não foi possível registrar seu pedido.');
    }
  }

  if (loading) {
    return (
      <View style={[s.screen, { alignItems: 'center', justifyContent: 'center' }]}>
        <ActivityIndicator color={BRAND} />
      </View>
    );
  }

  const baseFirst = parseISODateLocal(dados?.dataPrimeira ?? null);
  const getMensalidadeLabel = (idx: number): string => {
    const sched = dados?.schedule?.[idx];
    if (sched?.dateLabel) return sched.dateLabel;
    if (baseFirst) return brDate(addMonthsClamped(baseFirst, idx));
    return '—';
  };

  const m1 = getMensalidadeLabel(0);
  const m2 = getMensalidadeLabel(1);
  const m3 = getMensalidadeLabel(2);

  const contactDisabled = !(canAux1 || canAux2) || contactRequested;
  const liberadoAny = Boolean((resumo as any)?.liberado1 || (resumo as any)?.liberado2 || canAux1 || canAux2);
  const showPendenciasCard = Boolean(resumo?.hasOpenIssues && !liberadoAny);
  const accepted = !!resumo?.aceiteTermos;

  return (
    <View style={s.screen}>
      <ScrollView contentContainerStyle={{ padding: 18 }}>
        <View style={s.panel}>
          <Text style={s.brand}>ABASE</Text>
          <Text style={s.title}>Status do Cadastro</Text>

          <View style={s.card}>
            <Text style={s.cardTitle}>
              {`Olá${user?.name ? `, ${user.name.split(' ')[0]}` : ''}!`}
            </Text>
            <Text style={s.statusRow}>
              {'Status atual: '}
              <Text style={[s.badgeInline, { borderColor: statusColor, color: statusColor }]}>
                {statusTxt}
              </Text>
            </Text>
            <Text style={s.muted}>
              Seu cadastro foi enviado e permanecerá nesta tela até a conclusão da análise.
            </Text>
          </View>

          <View style={s.card}>
            <Text style={s.cardTitle}>Condições definidas</Text>
            <View style={s.rowItem}>
              <Text style={s.label}>Auxílio disponível</Text>
              <Text style={s.value}>{moneyBR(dados?.limiteDisponivel)}</Text>
            </View>
            <View style={s.sep} />
            <View style={s.rowItem}>
              <Text style={s.label}>Mensalidade</Text>
              <Text style={s.value}>{moneyBR(dados?.mensalidade)}</Text>
            </View>
            <View style={s.rowItem}>
              <Text style={s.label}>1ª mensalidade</Text>
              <Text style={s.value}>{m1}</Text>
            </View>
            <View style={s.rowItem}>
              <Text style={s.label}>2ª mensalidade</Text>
              <Text style={s.value}>{m2}</Text>
            </View>
            <View style={s.rowItem}>
              <Text style={s.label}>3ª mensalidade</Text>
              <Text style={s.value}>{m3}</Text>
            </View>
            {!!dados?.mesAverbacaoLabel && (
              <>
                <View style={s.sep} />
                <View style={s.rowItem}>
                  <Text style={s.label}>Mês de Averbação</Text>
                  <Text style={s.value}>{safe(dados.mesAverbacaoLabel)}</Text>
                </View>
              </>
            )}
          </View>

          <TouchableOpacity
            style={[s.btnAgree, { marginTop: 12, opacity: contactDisabled ? 0.5 : 1 }]}
            onPress={onContato}
            disabled={contactDisabled}
          >
            <Text style={s.btnAgreeTxt}>Estou de acordo entre em contato comigo</Text>
          </TouchableOpacity>

          <View style={s.card}>
            <Text style={s.cardTitle}>Termos do contrato</Text>
            <View style={s.rowItem}>
              <View style={{ flex: 1 }}>
                <Text style={s.label}>Termo de Adesão</Text>
                <Text style={[s.muted, { marginTop: 2 }]}>
                  {accepted ? 'Aceito' : (resumo?.termos?.adesaoUrl ? 'Disponível para leitura' : 'Aguardando')}
                </Text>
              </View>
              <View style={[s.okPill, { opacity: accepted ? 1 : 0.35 }]}>
                <Text style={s.okPillIcon}>✓</Text>
              </View>
            </View>
            <View style={s.rowItem}>
              <View style={{ flex: 1 }}>
                <Text style={s.label}>Termo de Antecipação</Text>
                <Text style={[s.muted, { marginTop: 2 }]}>
                  {accepted ? 'Aceito' : (resumo?.termos?.antecipacaoUrl ? 'Disponível para leitura' : 'Aguardando')}
                </Text>
              </View>
              <View style={[s.okPill, { opacity: accepted ? 1 : 0.35 }]}>
                <Text style={s.okPillIcon}>✓</Text>
              </View>
            </View>
            <TouchableOpacity
              style={[s.btnAgree, { opacity: canAccept ? 1 : 0.5 }]}
              onPress={onAceitar}
              disabled={!canAccept}
            >
              <Text style={s.btnAgreeTxt}>{resumo?.aceiteTermos ? 'Aceito' : 'Aceitar termos'}</Text>
            </TouchableOpacity>
          </View>

          {showPendenciasCard && (
            <View style={s.card}>
              <Text style={s.cardTitle}>Pendências</Text>
              {resumo?.hasOpenIssues ? (
                <>
                  <Text style={s.muted}>Você tem {resumo.openIssues.length} pendência(s) aberta(s).</Text>
                  <View style={{ marginTop: 10, gap: 10 }}>
                    {resumo.openIssues.map((it) => {
                      const st = String(it.status || '').toLowerCase();
                      const color = OPEN_ISSUE_STATUSES.has(st) ? BRAND : MUTED;
                      return (
                        <View key={it.id} style={s.issueItem}>
                          <Text style={s.issueTitle} numberOfLines={1}>{it.title || `Pendência #${it.id}`}</Text>
                          {!!it.message && <Text style={s.issueMsg}>{it.message}</Text>}
                          <Text style={{ color }}>
                            Status: <Text style={{ fontWeight: '800', color }}>{it.status}</Text>
                          </Text>
                        </View>
                      );
                    })}
                  </View>
                  <TouchableOpacity style={s.btnGhost} onPress={() => router.push('/(app)/pendencias-documentos')}>
                    <Text style={s.btnGhostTxt}>Enviar documentos</Text>
                  </TouchableOpacity>
                </>
              ) : (
                <Text style={s.muted}>Nenhuma pendência encontrada.</Text>
              )}
            </View>
          )}

          {!resumo?.complete && (
            <TouchableOpacity style={[s.btnPrimary, { marginTop: 12 }]} onPress={() => router.push('/(app)/cadastro-associado')}>
              <Text style={s.btnPrimaryTxt}>Preencher cadastro</Text>
            </TouchableOpacity>
          )}
        </View>
      </ScrollView>
    </View>
  );
}

const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: BG },
  panel: { backgroundColor: 'rgba(11,18,32,0.96)', borderRadius: 16, padding: 14, borderWidth: 1, borderColor: BORDER },
  brand: { color: BRAND, fontSize: 26, fontWeight: '900', letterSpacing: 6, textAlign: 'center' },
  title: { color: INK, fontSize: 18, fontWeight: '800', marginTop: 4, marginBottom: 10, textAlign: 'center', letterSpacing: 0.2 },
  card: { backgroundColor: CARD, borderWidth: 1, borderColor: BORDER, borderRadius: 12, padding: 12, marginTop: 12, elevation: 3 },
  cardTitle: { color: INK, fontWeight: '900', fontSize: 16, marginBottom: 6, letterSpacing: 0.2 },
  muted: { color: MUTED },
  statusRow: { color: MUTED, marginBottom: 6 },
  badgeInline: { borderWidth: 1, paddingHorizontal: 8, paddingVertical: 3, borderRadius: 999, fontWeight: '900', overflow: 'hidden', marginLeft: 6 },
  rowItem: { paddingVertical: 8, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12 },
  label: { color: MUTED, flex: 1 },
  value: { color: INK, fontWeight: '800', flex: 1, textAlign: 'right' },
  sep: { height: 1, backgroundColor: BORDER, marginVertical: 8 },
  issueItem: { borderWidth: 1, borderColor: BORDER, borderRadius: 10, padding: 10, backgroundColor: '#0d1424' },
  issueTitle: { color: INK, fontWeight: '900', letterSpacing: 0.2 },
  issueMsg: { color: MUTED, marginTop: 4, marginBottom: 6 },
  btnPrimary: { backgroundColor: BRAND, borderRadius: 12, alignItems: 'center', paddingVertical: 14, elevation: 2 },
  btnPrimaryTxt: { color: '#06121f', fontSize: 16, fontWeight: '900', letterSpacing: 0.3 },
  btnGhost: { marginTop: 10, backgroundColor: 'rgba(148,163,184,0.12)', borderRadius: 12, borderWidth: 1, borderColor: 'rgba(148,163,184,0.35)', alignItems: 'center', paddingVertical: 12 },
  btnGhostTxt: { color: INK, fontWeight: '800' },
  btnAgree: { marginTop: 12, backgroundColor: BRAND, borderRadius: 12, alignItems: 'center', paddingVertical: 14, opacity: 0.95, elevation: 2 },
  btnAgreeTxt: { color: '#00121a', fontSize: 16, fontWeight: '900', letterSpacing: 0.3 },
  okPill: { borderWidth: 1, borderColor: 'rgba(16,185,129,0.35)', backgroundColor: 'rgba(16,185,129,0.12)', borderRadius: 999, paddingHorizontal: 10, paddingVertical: 6, minWidth: 36, alignItems: 'center', justifyContent: 'center' },
  okPillIcon: { color: OK, fontWeight: '900', fontSize: 16, letterSpacing: 0.2 },
});
