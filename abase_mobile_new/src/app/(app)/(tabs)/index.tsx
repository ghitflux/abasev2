import React, { useEffect, useMemo, useState, useCallback } from 'react';
import {
  ActivityIndicator,
  Linking,
  Modal,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
  Alert,
} from 'react-native';
import { useRouter } from 'expo-router';
import { useFocusEffect } from '@react-navigation/native';
import * as SecureStore from 'expo-secure-store';
import {
  MessageCircle, Lock, ChevronRight, X, Scale,
} from 'lucide-react-native';

import ProgressBar from '@/components/ProgressBar';
import { moneyBR } from '@/utils/format';
import { useAuth } from '@/context/AuthContext';
import { fetchHome } from '@/services/api/authService';
import type { Bootstrap } from '@/types';
import { getHomeIssues, OPEN_ISSUE_STATUSES } from '@/services/api/homeService';
import { getCadastroStatus } from '@/services/api/cadastroService';
import { getAuxilioDoisStatus } from '@/services/api/auxilioDoisService';

/* ===== Helpers de status ===== */
type MaybeStatus = string | null | undefined;
const norm = (s: MaybeStatus) =>
  (s ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();

const isPendingStatus = (s: MaybeStatus) => {
  const t = norm(s);
  return (
    t.includes('pendente') || t.includes('em analise') || t.includes('aguard') ||
    t.includes('process') || t.includes('receb') || t.includes('sem contrato')
  );
};
const isCompleteLike = (s: MaybeStatus) => {
  const x = norm(s);
  return x.includes('liber') || x.includes('conclu') || x.includes('finaliz') ||
    x.includes('aprov') || x.includes('ativ');
};
const isBlocked = (s: MaybeStatus) => {
  const x = norm(s);
  return x.includes('bloque') || x.includes('block') || x.includes('suspens') ||
    x.includes('desativ') || x.includes('cancel');
};
const isSemContrato = (s: MaybeStatus) => norm(s).includes('sem contrato');

const toBoolLike = (v: any): boolean => {
  if (v === true || v === 1 || v === '1') return true;
  if (typeof v === 'string') {
    const t = v.trim().toLowerCase();
    return t === 'true' || t === 'yes' || t === 'sim';
  }
  return false;
};

const pickPath = (obj: any, paths: string[]) => {
  for (const p of paths) {
    try {
      const val = p.split('.').reduce((acc, k) => (acc == null ? acc : acc[k]), obj);
      if (val !== undefined && val !== null) return val;
    } catch {}
  }
  return undefined;
};

const toNumber = (v: any): number => {
  if (v == null) return 0;
  if (typeof v === 'number') return Number.isFinite(v) ? v : 0;
  let s = String(v).trim();
  if (s === '') return 0;
  if (s.includes('.') && s.includes(',')) s = s.replace(/\./g, '').replace(',', '.');
  else if (s.includes(',')) s = s.replace(',', '.');
  else s = s.replace(/,/g, '');
  const n = Number(s);
  return Number.isFinite(n) ? n : 0;
};

const pickMoney = (...vals: any[]) => {
  for (const v of vals) {
    const n = toNumber(v);
    if (n > 0) return n;
  }
  return 0;
};

export default function HomeScreen() {
  const { token, roles } = useAuth();
  const router = useRouter();

  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<Bootstrap | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [sheetOpen, setSheetOpen] = useState(false);

  const [basicDone, setBasicDone] = useState(false);
  const [cadComplete, setCadComplete] = useState(false);
  const [loadingBasic, setLoadingBasic] = useState(true);
  const [aceiteTermos, setAceiteTermos] = useState(false);
  const [auxilio2Active, setAuxilio2Active] = useState(false);
  const [aux1LiberadoByStatus, setAux1LiberadoByStatus] = useState(false);
  const [aux2LiberadoByStatus, setAux2LiberadoByStatus] = useState(false);

  const [issuesLoading, setIssuesLoading] = useState(true);
  const [hasOpenIssues, setHasOpenIssues] = useState(false);
  const [openIssues, setOpenIssues] = useState<
    Array<{ id: number; title?: string | null; message?: string | null; status: string }>
  >([]);

  const [auxilioChecking, setAuxilioChecking] = useState(false);
  const [auxilio2Checking, setAuxilio2Checking] = useState(false);

  useFocusEffect(
    useCallback(() => {
      setAuxilioChecking(false);
      setAuxilio2Checking(false);
      (async () => {
        const keys = ['auxilio2:forceEsperaOnce', 'auxilio1:forceEsperaOnce', 'auxilio:forceEsperaOnce'];
        await Promise.all(keys.map((k) => SecureStore.setItemAsync(k, '0').catch(() => {})));
      })();
      return () => {
        setAuxilioChecking(false);
        setAuxilio2Checking(false);
      };
    }, []),
  );

  // carrega /home
  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        if (!token) throw new Error('Não autenticado.');
        const h = await fetchHome();
        if (mounted) { setData(h); setErr(null); }
      } catch (e: any) {
        if (mounted) setErr(e?.message || 'Erro ao carregar.');
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => { mounted = false; };
  }, [token]);

  // status básico
  const fetchBasicStatus = useCallback(async () => {
    if (!token) {
      setBasicDone(false); setCadComplete(false); setLoadingBasic(false);
      setAceiteTermos(false); setAux1LiberadoByStatus(false); setAux2LiberadoByStatus(false);
      return;
    }
    try {
      setLoadingBasic(true);
      const st: any = await getCadastroStatus();
      const hasBasic = st.basic_complete === true ? true : st.basic_complete === undefined ? !!st.exists : false;
      const allow = st.complete === true && !isPendingStatus(st.status);
      const aceite = !!(st?.aceite_termos ?? st?.aceiteTermos);

      const a1Text = (pickPath(st, [
        'cadastro.auxilio1_status', 'auxilio1_status', 'auxilios.auxilio1.status',
      ]) as string) ?? '';
      const a2Text = (pickPath(st, [
        'cadastro.auxilio2_status', 'auxilio2_status', 'auxilios.auxilio2.status',
      ]) as string) ?? '';

      const a1Bool = toBoolLike(pickPath(st, [
        'cadastro.auxilio1_liberado', 'auxilios.auxilio1.liberado', 'auxilios.auxilio1.active',
      ]));
      const a2Bool = toBoolLike(pickPath(st, [
        'cadastro.auxilio2_liberado', 'auxilios.auxilio2.liberado', 'auxilios.auxilio2.active',
      ]));

      setBasicDone(hasBasic);
      setCadComplete(allow);
      setAceiteTermos(aceite);
      setAux1LiberadoByStatus(a1Bool || isCompleteLike(a1Text));
      setAux2LiberadoByStatus(a2Bool || isCompleteLike(a2Text));
    } catch {
      setBasicDone(false); setCadComplete(false); setAceiteTermos(false);
      setAux1LiberadoByStatus(false); setAux2LiberadoByStatus(false);
    } finally {
      setLoadingBasic(false);
    }
  }, [token]);

  useEffect(() => { fetchBasicStatus(); }, [fetchBasicStatus]);
  useFocusEffect(useCallback(() => { fetchBasicStatus(); }, [fetchBasicStatus]));

  // pendências
  const fetchIssues = useCallback(async () => {
    if (!token) { setHasOpenIssues(false); setOpenIssues([]); setIssuesLoading(false); return; }
    try {
      setIssuesLoading(true);
      const res = await getHomeIssues();
      setHasOpenIssues(res.hasOpenIssues);
      setOpenIssues(res.openIssues.map((it) => ({ id: it.id, title: it.title, message: it.message, status: it.status })));
    } catch {
      setHasOpenIssues(false); setOpenIssues([]);
    } finally {
      setIssuesLoading(false);
    }
  }, [token]);

  useEffect(() => { fetchIssues(); }, [fetchIssues]);
  useFocusEffect(useCallback(() => { fetchIssues(); }, [fetchIssues]));

  // resumo Auxílio 2
  const refreshAuxilio2 = useCallback(async () => {
    if (!token) { setAuxilio2Active(false); return; }
    try {
      const st2: any = await getAuxilioDoisStatus().catch(() => null);
      const statusTextRaw = (pickPath(st2, [
        'status', 'status_contrato', 'status_label', 'situacao', 'current_status',
        'resumo.status', 'contrato.status_contrato', 'auxilio2_status',
      ]) as string) ?? '';
      const blocked = isBlocked(statusTextRaw) ||
        /bloque/.test(String(pickPath(st2, ['auxilio2_status'])).toLowerCase());
      const explicit = toBoolLike(pickPath(st2, [
        'complete', 'completed', 'is_complete', 'active', 'ativo', 'is_active', 'liberado', 'aprovado',
      ]) as any);
      setAuxilio2Active((explicit || isCompleteLike(statusTextRaw)) && !blocked);
    } catch {
      setAuxilio2Active(false);
    }
  }, [token]);

  useEffect(() => { refreshAuxilio2(); }, [refreshAuxilio2]);
  useFocusEffect(useCallback(() => { refreshAuxilio2(); }, [refreshAuxilio2]));

  const firstName = useMemo(() => {
    const full = data?.pessoa?.nome_razao_social?.trim() || 'Associado';
    return full.split(/\s+/)[0].toUpperCase();
  }, [data]);

  const isAssociado = useMemo(() => {
    const asStr = (x: any) => String(x ?? '').toLowerCase();
    const rolesLower = (roles || []).map(asStr);
    if (rolesLower.some(r => /associadodois|associado\s*dois|associado[_\s]*2/.test(r))) return false;
    if (rolesLower.some(r => /\bassociado\b/.test(r))) return true;
    return false;
  }, [roles]);

  const mensal = useMemo(() => {
    const d: any = data || {};
    return pickMoney(
      d?.contrato_mensalidade, d?.cadastro?.contrato_mensalidade,
      d?.contrato?.mensalidade, d?.contrato?.parcela_valor,
      d?.resumo?.mensalidade, d?.resumo?.parcela_valor,
    );
  }, [data]);

  const prazo = data?.resumo?.prazo ?? 0;
  const pagas = data?.resumo?.parcelas_pagas ?? 0;

  const pct = useMemo(() => {
    const p = data?.resumo?.percentual_pago ?? 0;
    if (p > 0) return p;
    return prazo > 0 ? (pagas * 100) / prazo : 0;
  }, [data, prazo, pagas]);

  const pill = useMemo(() => {
    if (!data) return { text: '—', style: s.pillInfo, textStyle: s.pillTextInfo };
    if ((data.resumo?.atraso ?? 0) > 0) return { text: 'EM ATRASO', style: s.pillDanger, textStyle: s.pillTextDanger };
    if ((data.resumo?.parcelas_pagas ?? 0) >= (data.resumo?.prazo ?? 0) && (data.resumo?.prazo ?? 0) > 0) {
      return { text: 'CONCLUÍDO', style: s.pillSuccess, textStyle: s.pillTextSuccess };
    }
    return { text: 'A DESCONTAR', style: s.pillWarning, textStyle: s.pillTextWarning };
  }, [data]);

  function openWhatsApp(digits?: string | null, preset?: string) {
    if (!digits) return;
    const url = `https://wa.me/${digits}?text=${encodeURIComponent(preset || '')}`;
    Linking.openURL(url).catch(() => {});
  }

  const aux1StatusHome = norm((pickPath(data, ['auxilio1_status', 'cadastro.auxilio1_status']) as string) ?? '');
  const aux2StatusHome = norm((pickPath(data, ['auxilio2_status', 'cadastro.auxilio2_status']) as string) ?? '');
  const aux1LiberadoHome = aux1StatusHome.includes('liber') || isCompleteLike(aux1StatusHome);
  const aux2LiberadoHome = aux2StatusHome.includes('liber') || isCompleteLike(aux2StatusHome);
  const aux1LiberadoAny = aux1LiberadoHome || aux1LiberadoByStatus;
  const aux2LiberadoAny = aux2LiberadoHome || aux2LiberadoByStatus;

  const hasBlockingIssues = hasOpenIssues && !(aux1LiberadoAny || aux2LiberadoAny);
  const showIssuesCard = hasBlockingIssues;

  const auxilio1Enabled = (aux1LiberadoAny || cadComplete) && !loadingBasic && !hasBlockingIssues;
  const auxilio2Enabled = (aux2LiberadoAny || cadComplete) && !loadingBasic && !hasBlockingIssues;

  const onEnviarDocs = useCallback(() => {
    router.push('/(app)/pendencias-documentos');
  }, [router]);

  const onAuxilioPress = useCallback(() => {
    if (!token || auxilioChecking) return;
    if (hasBlockingIssues) { onEnviarDocs(); return; }
    if (!auxilio1Enabled) {
      Alert.alert('Em análise', 'Dados enviados e em análise. Em breve você terá um retorno.');
      return;
    }
    setAuxilioChecking(true);
    router.push('/(app)/espera');
  }, [token, auxilioChecking, hasBlockingIssues, auxilio1Enabled, router, onEnviarDocs]);

  const onAuxilio2Press = useCallback(async () => {
    if (!token || auxilio2Checking) return;
    if (hasBlockingIssues) { onEnviarDocs(); return; }
    if (!auxilio2Enabled) {
      Alert.alert('Em análise', 'Dados enviados e em análise. Em breve você terá um retorno.');
      return;
    }
    try {
      setAuxilio2Checking(true);
      const status2: any = await getAuxilioDoisStatus().catch(() => null);
      const statusTextRaw = (pickPath(status2, [
        'status', 'status_contrato', 'status_label', 'situacao', 'current_status',
        'resumo.status', 'contrato.status_contrato', 'auxilio2_status',
      ]) as string) ?? '';
      const blocked = isBlocked(statusTextRaw) ||
        /bloque/.test(String(pickPath(status2, ['auxilio2_status'])).toLowerCase());

      if (blocked) {
        Alert.alert('Indisponível', 'O Auxílio 2 está bloqueado para o seu cadastro no momento.');
        return;
      }

      const serverSaysComplete2 =
        Boolean((status2 as any)?.complete) || Boolean((status2 as any)?.completed) ||
        Boolean((status2 as any)?.is_complete) || isCompleteLike(statusTextRaw);

      const flag2 = await SecureStore.getItemAsync('auxilio2:forceEsperaOnce').catch(() => null);

      if (serverSaysComplete2 || flag2 === '1') {
        if (flag2 === '1') await SecureStore.setItemAsync('auxilio2:forceEsperaOnce', '0').catch(() => {});
        router.push('/(app)/espera');
        return;
      }

      router.push('/(app)/auxilio-emergencial');
    } catch {
      router.push('/(app)/auxilio-emergencial');
    } finally {
      setAuxilio2Checking(false);
    }
  }, [token, auxilio2Checking, auxilio2Enabled, router, hasBlockingIssues, onEnviarDocs]);

  if (loading) return <View style={s.center}><ActivityIndicator /></View>;

  if (err) {
    return (
      <View style={[s.center, { paddingHorizontal: 16 }]}>
        <Text style={s.title}>Início</Text>
        <Text style={s.errorText}>{err}</Text>
      </View>
    );
  }

  const aceite = aceiteTermos || (data as any)?.aceite_termos === true;
  const rawContractStatus = data?.resumo?.status_contrato ?? (data as any)?.contrato?.status_contrato ?? '—';
  const contractStatusLabel =
    aceite && (!rawContractStatus || isSemContrato(rawContractStatus)) ? 'COM CONTRATO' : rawContractStatus;

  const activeAux1 = !!aceite;
  const activeAux2 = !!auxilio2Active;

  const bannerText = activeAux2
    ? 'Você está ativo no Auxílio Emergencial 2'
    : activeAux1 ? 'Você está ativo no Auxílio Emergencial 1' : null;

  const renewText = activeAux2 ? 'Solicitar renovação do Auxílio 2' : 'Solicitar renovação do Auxílio 1';

  return (
    <>
      <ScrollView style={s.container} contentContainerStyle={{ padding: 16, gap: 16 }}>
        {/* Header */}
        <View style={s.header}>
          <View style={{ flex: 1 }}>
            <Text style={s.hello}>OLÁ, {firstName}!</Text>
            <Text style={s.helloSub}>Bem-vinda de volta</Text>
          </View>
          <View style={s.headerIcons}>
            <TouchableOpacity onPress={() => setSheetOpen(true)} style={s.iconBtn}>
              <MessageCircle size={22} color="#22c55e" />
            </TouchableOpacity>
          </View>
        </View>

        {/* Valor da contribuição */}
        <View style={s.bigCard}>
          <Text style={s.bigCardTitle}>Valor da Contribuição</Text>
          <Text style={s.money}>{moneyBR(mensal)}</Text>
          <Text style={s.muted}>Valor mensal do seu ciclo</Text>
        </View>

        {/* Mensalidades */}
        <View style={s.card}>
          <View style={s.rowBetween}>
            <Text style={s.cardTitle}>Mensalidades do Ciclo</Text>
            <Text style={s.mutedSmall}>({prazo} mensalidades)</Text>
          </View>
          <View style={{ marginTop: 6 }}>
            <Text style={s.muted}>
              {pagas}/{prazo} concluídas <Text style={s.bold}>{Math.round(pct)}%</Text>
            </Text>
          </View>
          <View style={{ marginTop: 8 }}>
            <ProgressBar progress={pct} />
          </View>
          <View style={{ marginTop: 10, flexDirection: 'row', alignItems: 'center', gap: 10 }}>
            {isAssociado ? (
              <>
                {pagas > 0 && (
                  <View style={[s.pillBase, s.pillSuccess]}>
                    <Text style={[s.pillTextBase, s.pillTextSuccess]}>DESCONTADA</Text>
                  </View>
                )}
                {Math.max((prazo || 0) - (pagas || 0), 0) > 0 && (
                  <View style={[s.pillBase, s.pillWarning]}>
                    <Text style={[s.pillTextBase, s.pillTextWarning]}>A DESCONTAR</Text>
                  </View>
                )}
              </>
            ) : (
              <View style={[s.pillBase, pill.style as any]}>
                <Text style={[s.pillTextBase, pill.textStyle as any]}>{pill.text}</Text>
              </View>
            )}
          </View>
          <View style={{ marginTop: 10, gap: 6 }}>
            <Text style={s.line}>
              📅 Próxima: {data?.proximaRef?.mesLabel ?? '—'}{' '}
              {data?.proximaRef?.dataLabel ? `- ${data?.proximaRef?.dataLabel}` : ''}
            </Text>
            <View style={s.rowBetween}>
              <Text style={s.line}>Status do contrato</Text>
              <Text style={s.bold}>{contractStatusLabel}</Text>
            </View>
          </View>
        </View>

        {/* Área de Auxílio */}
        {activeAux1 || activeAux2 ? (
          <>
            {!!bannerText && (
              <View style={s.infoBanner}>
                <Text style={s.infoBannerTitle}>{bannerText}</Text>
                <Text style={s.infoBannerSub}>Se precisar de atendimento, fale conosco no WhatsApp.</Text>
              </View>
            )}
            <TouchableOpacity
              disabled
              style={[s.btnDisabled, { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }]}
            >
              <Text style={s.btnDisabledText}>{renewText}</Text>
              <Lock size={18} color="#9aa3af" />
            </TouchableOpacity>
          </>
        ) : (
          <>
            {auxilio1Enabled ? (
              <TouchableOpacity
                style={[s.btnAuxilio, { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', opacity: auxilioChecking ? 0.8 : 1 }]}
                onPress={onAuxilioPress}
                disabled={auxilioChecking}
              >
                <Text style={s.btnAuxilioText}>Solicitar Auxílio Emergencial 1</Text>
                {auxilioChecking ? <ActivityIndicator size="small" color="#fff" /> : <ChevronRight size={18} color="#fff" />}
              </TouchableOpacity>
            ) : (
              <TouchableOpacity
                disabled
                style={[s.btnDisabled, { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }]}
              >
                <Text style={s.btnDisabledText}>Solicitar Auxílio Emergencial 1</Text>
                <Lock size={18} color="#9aa3af" />
              </TouchableOpacity>
            )}

            {auxilio2Enabled ? (
              <TouchableOpacity
                style={[s.btnAuxilio, { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', opacity: auxilio2Checking ? 0.8 : 1 }]}
                onPress={onAuxilio2Press}
                disabled={auxilio2Checking}
              >
                <Text style={s.btnAuxilioText}>Solicitar Auxílio Emergencial 2</Text>
                {auxilio2Checking ? <ActivityIndicator size="small" color="#fff" /> : <ChevronRight size={18} color="#fff" />}
              </TouchableOpacity>
            ) : (
              <TouchableOpacity
                disabled
                style={[s.btnDisabled, { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }]}
              >
                <Text style={s.btnDisabledText}>Solicitar Auxílio Emergencial 2</Text>
                <Lock size={18} color="#9aa3af" />
              </TouchableOpacity>
            )}
          </>
        )}

        {/* Pendências */}
        {showIssuesCard && (
          <View style={s.card}>
            <View style={s.rowBetween}>
              <Text style={s.cardTitle}>Pendências</Text>
              <Text style={s.mutedSmall}>
                {issuesLoading ? 'Carregando…' : `${openIssues.length} aberta(s)`}
              </Text>
            </View>
            <View style={{ marginTop: 10, gap: 10 }}>
              {openIssues.slice(0, 3).map((it) => {
                const st = String(it.status || '').toLowerCase();
                const color = OPEN_ISSUE_STATUSES.has(st) ? '#22d3ee' : '#94a3b8';
                return (
                  <View key={it.id} style={s.issueItem}>
                    <Text style={s.issueTitle} numberOfLines={1}>{it.title || `Pendência #${it.id}`}</Text>
                    {!!it.message && <Text style={s.issueMsg}>{it.message}</Text>}
                    <Text style={{ color }}>Status: <Text style={{ fontWeight: '800', color }}>{it.status}</Text></Text>
                  </View>
                );
              })}
              {openIssues.length > 3 && (
                <Text style={[s.mutedSmall, { marginTop: -4 }]}>…e mais {openIssues.length - 3} pendência(s)</Text>
              )}
            </View>
            <TouchableOpacity style={[s.btnPrimary, { marginTop: 12 }]} onPress={onEnviarDocs}>
              <Text style={s.btnPrimaryTxt}>Reenviar documentos</Text>
            </TouchableOpacity>
          </View>
        )}
      </ScrollView>

      {/* Bottom sheet WhatsApp */}
      <Modal visible={sheetOpen} transparent animationType="fade" onRequestClose={() => setSheetOpen(false)}>
        <View style={s.modalBackdrop}>
          <View style={s.sheet}>
            <View style={s.sheetHeader}>
              <Text style={s.sheetTitle}>Como podemos ajudar?</Text>
              <TouchableOpacity onPress={() => setSheetOpen(false)} style={s.iconBtn}>
                <X size={22} color="#cbd5e1" />
              </TouchableOpacity>
            </View>

            <TouchableOpacity
              style={[s.waBtn, { marginTop: 8 }]}
              onPress={() => openWhatsApp((data as any)?.whatsapps?.geral, 'Olá! Preciso de atendimento.')}
              disabled={!(data as any)?.whatsapps?.geral}
            >
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
                <MessageCircle size={20} color="#fff" />
                <View>
                  <Text style={s.waBtnTitle}>Entre em contato com ABASE</Text>
                  <Text style={s.waBtnSub}>Atendimento geral e dúvidas</Text>
                </View>
              </View>
            </TouchableOpacity>

            <TouchableOpacity
              style={s.sheetItem}
              onPress={() => openWhatsApp((data as any)?.whatsapps?.juridico, 'Olá! Preciso falar com o jurídico.')}
              disabled={!(data as any)?.whatsapps?.juridico}
            >
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
                <Scale size={20} color="#cbd5e1" />
                <View style={{ flex: 1 }}>
                  <Text style={s.sheetItemTitle}>Contate Nosso Jurídico</Text>
                  <Text style={s.sheetItemSub}>Questões legais e contratos</Text>
                </View>
                <ChevronRight size={18} color="#94a3b8" />
              </View>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0b0f14' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: '#0b0f14' },
  header: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  headerIcons: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  iconBtn: { padding: 8, borderRadius: 999, backgroundColor: '#0f172a' },
  hello: { color: '#e5e7eb', fontWeight: '800', fontSize: 18 },
  helloSub: { color: '#94a3b8', marginTop: 2 },
  title: { color: '#e5e7eb', fontSize: 22, fontWeight: '700', marginBottom: 8 },
  bigCard: { backgroundColor: '#a83f51', padding: 16, borderRadius: 16 },
  bigCardTitle: { color: '#f3f4f6', fontWeight: '700' },
  money: { color: '#fff', fontSize: 28, fontWeight: '900', marginVertical: 4 },
  muted: { color: '#9aa3af' },
  mutedSmall: { color: '#9aa3af', fontSize: 12 },
  card: { backgroundColor: '#111827', padding: 16, borderRadius: 16 },
  cardTitle: { color: '#e5e7eb', fontWeight: '700', fontSize: 16 },
  rowBetween: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  bold: { color: '#e5e7eb', fontWeight: '700' },
  line: { color: '#94a3b8' },
  pillBase: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: 999, borderWidth: 1 },
  pillTextBase: { fontWeight: '800', fontSize: 12 },
  pillWarning: { backgroundColor: '#f59e0b22', borderColor: '#f59e0b55' },
  pillTextWarning: { color: '#f59e0b' },
  pillDanger: { backgroundColor: '#ef444422', borderColor: '#ef444455' },
  pillTextDanger: { color: '#ef4444' },
  pillSuccess: { backgroundColor: '#22c55e22', borderColor: '#22c55e55' },
  pillTextSuccess: { color: '#22c55e' },
  pillInfo: { backgroundColor: '#3b82f622', borderColor: '#3b82f655' },
  pillTextInfo: { color: '#3b82f6' },
  issueItem: { borderWidth: 1, borderColor: 'rgba(148,163,184,0.25)', borderRadius: 10, padding: 10 },
  issueTitle: { color: '#e5e7eb', fontWeight: '800' },
  issueMsg: { color: '#94a3b8', marginTop: 4, marginBottom: 6 },
  btnPrimary: { backgroundColor: '#22d3ee', borderRadius: 12, alignItems: 'center', paddingVertical: 14 },
  btnPrimaryTxt: { color: '#00121a', fontSize: 16, fontWeight: '900', letterSpacing: 0.3 },
  btnAuxilio: { backgroundColor: '#a83f51', padding: 16, borderRadius: 14 },
  btnAuxilioText: { color: '#fff', fontWeight: '800' },
  btnDisabled: { backgroundColor: '#1f2937', padding: 16, borderRadius: 14, opacity: 0.7 },
  btnDisabledText: { color: '#9aa3af', fontWeight: '700' },
  infoBanner: { backgroundColor: '#0f172a', borderRadius: 14, padding: 16, borderWidth: 1, borderColor: 'rgba(34,211,238,0.35)' },
  infoBannerTitle: { color: '#22d3ee', fontWeight: '900' },
  infoBannerSub: { color: '#94a3b8', marginTop: 4 },
  modalBackdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'flex-end' },
  sheet: { backgroundColor: '#0f172a', padding: 16, borderTopLeftRadius: 20, borderTopRightRadius: 20 },
  sheetHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  sheetTitle: { color: '#e5e7eb', fontWeight: '800', fontSize: 16 },
  waBtn: { backgroundColor: '#22c55e', borderRadius: 12, padding: 14 },
  waBtnTitle: { color: '#fff', fontWeight: '800' },
  waBtnSub: { color: '#fff', opacity: 0.9 },
  sheetItem: { backgroundColor: '#111827', borderRadius: 12, padding: 14, marginTop: 10 },
  sheetItemTitle: { color: '#e5e7eb', fontWeight: '700' },
  sheetItemSub: { color: '#94a3b8' },
  errorText: { color: '#ef4444', marginTop: 8 },
});
